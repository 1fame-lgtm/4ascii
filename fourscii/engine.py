"""Moteur ASCII de 4scii — algorithme « 4SHAPE ».

L'idée : au lieu de choisir un caractère seulement selon la luminosité (comme la plupart des
convertisseurs), 4SHAPE compare la *forme* de chaque case de l'image à la forme réelle de chaque
caractère, mesurée en dessinant la police à l'écran.

1. Atlas de glyphes : chaque caractère est dessiné dans la police choisie puis découpé en une
   petite grille (ex. 2×4 sous-cases). On obtient un « vecteur d'encre » par caractère.
2. L'image est réduite à (colonnes × sous-cases) en tenant compte du rapport largeur/hauteur
   réel des caractères (mesuré lui aussi sur la police).
3. Pré-traitement : niveaux automatiques, luminosité, contraste, gamma, netteté.
4. Pour chaque case, on choisit le glyphe dont le vecteur est le plus proche
   (distance de forme + distance de ton pondérée), calculé en une seule opération matricielle.
5. Contours optionnels : tenseur de structure (Sobel) → orientation → | / - \\ par-dessus.

D'autres modes réutilisent le même pipeline : densité (avec tramage), braille 2×4,
quadrants 2×2 et demi-blocs couleur.
"""
import math
from bisect import bisect_right

import numpy as np
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QImage, QPainter

# --------------------------------------------------------------------------- jeux de caractères
ASCII_ALL = "".join(chr(c) for c in range(32, 127))
CHARSETS = {
    "ASCII complet": ASCII_ALL,
    "4scii équilibré": " .'`^\",:;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$",
    "Classique 10": " .:-=+*#%@",
    "Doux": " .,:;ox%#@",
    "Minimal": " .oO@",
    "Code": " .,:;i1tfLCG08@",
    "Binaire": " 01",
    "Blocs": " ░▒▓█",
    "Points": " ·•●",
    "Lignes": " _-=≡/\\|",
    "Étoiles": " .+*✦★",
    "Matrix (katakana)": " ｦｱｳｴｵｶｷｹｺｻｼｽｾｿﾀﾂﾃﾅﾆﾇﾈﾊﾋﾎﾏﾐﾑﾒﾓﾔﾕﾗﾘﾜ0123456789",
    "Personnalisé": "",
}

MODES = {
    "shape": "4SHAPE (formes)",
    "density": "Densité",
    "edges": "Contours seuls",
    "braille": "Braille ⣿ (haute déf.)",
    "blocks": "Quadrants ▚",
    "halfblock": "Pixels ▀ (demi-blocs)",
}

PRECISIONS = {"Rapide": (2, 2), "Normale": (2, 4), "Fine": (3, 6), "Ultra": (4, 8)}

DITHERS = {"none": "Aucun", "fs": "Floyd–Steinberg", "atkinson": "Atkinson", "bayer": "Bayer (ordonné)"}

EDGE_STYLES = {"ascii": "| / - \\", "unicode": "│ ╱ ─ ╲", "bold": "┃ ╱ ━ ╲"}
_EDGE_CHARS = {"ascii": "|/-\\", "unicode": "│╱─╲", "bold": "┃╱━╲"}

QUADRANTS = " ▘▝▀▖▌▞▛▗▚▐▜▄▙▟█"  # index = tl | tr<<1 | bl<<2 | br<<3
HALF = " ▀▄█"                   # index = top | bottom<<1

DEFAULTS = dict(
    mode="shape", cols=120, charset="ASCII complet", custom_chars="", auto_order=True,
    precision="Normale", brightness=0, contrast=0, gamma=1.0, sharpen=0, autolevels=True,
    invert=False, dark_bg=True, dither="none", edges=0, edge_style="ascii", tone=35, boost=20,
    saturation=100, aspect=100, font="Consolas",
)


class AsciiArt:
    """Résultat d'une conversion : lignes de texte + couches optionnelles pour la couleur."""

    def __init__(self, lines, rgb=None, ink=None, top=None, bottom=None):
        self.lines = lines
        self.rgb = rgb          # (rows, cols, 3) uint8 : couleur moyenne de chaque case
        self.ink = ink          # (rows, cols) float 0..1 : densité d'encre
        self.top = top          # demi-blocs : couleur du pixel du haut
        self.bottom = bottom    # … et du bas
        self.elapsed = 0.0

    @property
    def rows(self):
        return len(self.lines)

    @property
    def cols(self):
        return max((len(l) for l in self.lines), default=0)

    @property
    def text(self):
        return "\n".join(l.rstrip() for l in self.lines)

    def copy(self):
        c = lambda a: None if a is None else a.copy()  # noqa: E731
        return AsciiArt(list(self.lines), c(self.rgb), c(self.ink), c(self.top), c(self.bottom))

    @classmethod
    def from_text(cls, text):
        lines = text.replace("\t", "    ").split("\n")
        w = max((len(l) for l in lines), default=0)
        return cls([l.ljust(w) for l in lines])


# --------------------------------------------------------------------------- atlas de glyphes
_ATLAS_CACHE = {}


class GlyphAtlas:
    """Forme mesurée de chaque caractère d'un jeu, dans une police donnée."""

    def __init__(self, family, chars, sx, sy):
        chars = "".join(dict.fromkeys(chars)) or " "
        font = QFont(family)
        font.setStyleHint(QFont.Monospace)
        font.setPixelSize(48)
        fm = QFontMetricsF(font)
        cw = max(1.0, fm.horizontalAdvance("M"))
        ch = max(1.0, fm.height())
        self.aspect = cw / ch                      # largeur / hauteur d'une case
        W, H = int(math.ceil(cw)), int(math.ceil(ch))
        vecs = []
        for c in chars:
            img = QImage(W, H, QImage.Format_Grayscale8)
            img.fill(0)
            p = QPainter(img)
            p.setRenderHint(QPainter.TextAntialiasing)
            p.setFont(font)
            p.setPen(QColor(255, 255, 255))
            p.drawText(QPointF(0, fm.ascent()), c)
            p.end()
            small = img.scaled(sx * 6, sy * 6, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            a = gray_to_array(small)
            vecs.append(a.reshape(sy, 6, sx, 6).mean(axis=(1, 3)).reshape(-1))
        G = np.array(vecs, dtype=np.float32)
        dens = G.mean(axis=1)
        top = float(dens.max()) or 1.0
        self.chars = chars
        self.vectors = G / top                     # le caractère le plus dense vaut 1 en moyenne
        self.density = dens / top
        self.sq = (self.vectors ** 2).sum(axis=1)
        self.k = sx * sy

    @classmethod
    def get(cls, family, chars, sx, sy):
        key = (family, chars, sx, sy)
        if key not in _ATLAS_CACHE:
            if len(_ATLAS_CACHE) > 24:
                _ATLAS_CACHE.clear()
            _ATLAS_CACHE[key] = cls(family, chars, sx, sy)
        return _ATLAS_CACHE[key]


def char_aspect(family):
    return GlyphAtlas.get(family, " ", 1, 1).aspect


# --------------------------------------------------------------------------- conversions d'images
def gray_to_array(img):
    img = img.convertToFormat(QImage.Format_Grayscale8)
    w, h, bpl = img.width(), img.height(), img.bytesPerLine()
    a = np.frombuffer(img.constBits(), np.uint8, count=bpl * h).reshape(h, bpl)[:, :w]
    return a.astype(np.float32) / 255.0


def rgb_to_array(img):
    img = img.convertToFormat(QImage.Format_RGB888)
    w, h, bpl = img.width(), img.height(), img.bytesPerLine()
    return np.frombuffer(img.constBits(), np.uint8, count=bpl * h).reshape(h, bpl)[:, :w * 3] \
        .reshape(h, w, 3).astype(np.float32)


def array_to_qimage(a):
    """(H, W) float 0..1 → QImage niveaux de gris."""
    g = np.ascontiguousarray((np.clip(a, 0, 1) * 255).astype(np.uint8))
    h, w = g.shape
    return QImage(g.data, w, h, w, QImage.Format_Grayscale8).copy()


def flatten_alpha(img, dark_bg=True):
    if not img.hasAlphaChannel():
        return img
    out = QImage(img.size(), QImage.Format_RGB888)
    out.fill(QColor(0, 0, 0) if dark_bg else QColor(255, 255, 255))
    p = QPainter(out)
    p.drawImage(0, 0, img)
    p.end()
    return out


def _blocks(a, rows, sy, cols, sx):
    """(rows*sy, cols*sx[, c]) → (rows, cols, sy*sx[, c]) : sous-cases de chaque case."""
    if a.ndim == 2:
        return a.reshape(rows, sy, cols, sx).transpose(0, 2, 1, 3).reshape(rows, cols, sy * sx)
    return a.reshape(rows, sy, cols, sx, -1).transpose(0, 2, 1, 3, 4).reshape(rows, cols, sy * sx, -1)


def _box_blur(a):
    p = np.pad(a, 1, mode="edge")
    return (p[:-2, :-2] + p[:-2, 1:-1] + p[:-2, 2:] + p[1:-1, :-2] + p[1:-1, 1:-1] + p[1:-1, 2:]
            + p[2:, :-2] + p[2:, 1:-1] + p[2:, 2:]) / 9.0


def adjust(lum, P):
    """Pré-traitement de la luminance (0..1)."""
    v = lum
    if P["autolevels"]:
        lo, hi = np.percentile(v, (1, 99))
        if hi - lo > 1e-3:
            v = (v - lo) / (hi - lo)
    if P["sharpen"]:
        v = v + (v - _box_blur(v)) * (P["sharpen"] / 100.0) * 2.5
    if P["contrast"]:
        k = math.tan((P["contrast"] / 100.0 + 1) * math.pi / 4)
        v = (v - 0.5) * k + 0.5
    if P["brightness"]:
        v = v + P["brightness"] / 100.0
    v = np.clip(v, 0, 1)
    if P["gamma"] != 1.0:
        v = v ** (1.0 / max(0.05, P["gamma"]))
    return v


# --------------------------------------------------------------------------- tramage
_BAYER = np.array([[0, 32, 8, 40, 2, 34, 10, 42], [48, 16, 56, 24, 50, 18, 58, 26],
                   [12, 44, 4, 36, 14, 46, 6, 38], [60, 28, 52, 20, 62, 30, 54, 22],
                   [3, 35, 11, 43, 1, 33, 9, 41], [51, 19, 59, 27, 49, 17, 57, 25],
                   [15, 47, 7, 39, 13, 45, 5, 37], [63, 31, 55, 23, 61, 29, 53, 21]],
                  dtype=np.float32) / 64.0 - 0.5 + 1 / 128


def quantize(v, levels, method="none"):
    """Associe chaque valeur au niveau le plus proche (niveaux triés, non uniformes) → indices."""
    levels = np.asarray(levels, dtype=np.float32)
    mids = (levels[1:] + levels[:-1]) / 2
    if method == "bayer":
        h, w = v.shape
        step = 1.0 / max(1, len(levels) - 1)
        t = np.tile(_BAYER, (h // 8 + 1, w // 8 + 1))[:h, :w]
        return np.searchsorted(mids, v + t * step)
    if method in ("fs", "atkinson"):
        return _diffuse(v, levels, mids, method)
    return np.searchsorted(mids, v)


def _diffuse(v, levels, mids, method):
    h, w = v.shape
    buf = v.astype(np.float64).tolist()
    lv = levels.tolist()
    md = mids.tolist()
    out = []
    atk = method == "atkinson"
    for y in range(h):
        row = buf[y]
        r1 = buf[y + 1] if y + 1 < h else None
        r2 = buf[y + 2] if atk and y + 2 < h else None
        res = [0] * w
        for x in range(w):
            old = row[x]
            i = bisect_right(md, old)
            res[x] = i
            e = old - lv[i]
            if atk:
                e /= 8.0
                if x + 1 < w:
                    row[x + 1] += e
                if x + 2 < w:
                    row[x + 2] += e
                if r1 is not None:
                    if x:
                        r1[x - 1] += e
                    r1[x] += e
                    if x + 1 < w:
                        r1[x + 1] += e
                if r2 is not None:
                    r2[x] += e
            else:
                if x + 1 < w:
                    row[x + 1] += e * 0.4375
                if r1 is not None:
                    if x:
                        r1[x - 1] += e * 0.1875
                    r1[x] += e * 0.3125
                    if x + 1 < w:
                        r1[x + 1] += e * 0.0625
        out.append(res)
    return np.array(out, dtype=np.int64)


# --------------------------------------------------------------------------- contours
def _sobel(a):
    p = np.pad(a, 1, mode="edge")
    gx = (p[:-2, 2:] + 2 * p[1:-1, 2:] + p[2:, 2:]) - (p[:-2, :-2] + 2 * p[1:-1, :-2] + p[2:, :-2])
    gy = (p[2:, :-2] + 2 * p[2:, 1:-1] + p[2:, 2:]) - (p[:-2, :-2] + 2 * p[:-2, 1:-1] + p[:-2, 2:])
    return gx, gy


def edge_layer(lum, rows, cols, sx, sy, strength, style):
    """Orientation des contours par case (tenseur de structure) → tableau de caractères ou ''."""
    gx, gy = _sobel(lum)
    jxx = _blocks(gx * gx, rows, sy, cols, sx).sum(-1)
    jyy = _blocks(gy * gy, rows, sy, cols, sx).sum(-1)
    jxy = _blocks(gx * gy, rows, sy, cols, sx).sum(-1)
    mag = np.sqrt(jxx + jyy) / (sx * sy)
    theta = 0.5 * np.degrees(np.arctan2(2 * jxy, jxx - jyy))   # direction du gradient
    keep = 100 - strength * 0.6
    thr = max(float(np.percentile(mag, keep)), 0.04)
    chars = _EDGE_CHARS.get(style, _EDGE_CHARS["ascii"])
    idx = np.full(theta.shape, 2)                                # gradient vertical → ligne horizontale
    a = np.abs(theta)
    idx[a < 22.5] = 0                                            # gradient horizontal → ligne verticale
    idx[(theta >= 22.5) & (theta <= 67.5)] = 1
    idx[(theta <= -22.5) & (theta >= -67.5)] = 3
    return mag > thr, idx, chars


# --------------------------------------------------------------------------- conversion principale
def charset_of(P):
    if P["charset"] == "Personnalisé":
        return P["custom_chars"] or " .:#"
    return CHARSETS.get(P["charset"], ASCII_ALL)


def grid_size(w, h, P, aspect, cols=None, rows=None):
    k = P["aspect"] / 100.0
    if cols is None and rows is not None:
        cols = max(1, round(rows * (w / max(1, h)) / (aspect * k)))
    cols = max(1, int(cols or P["cols"]))
    rows = max(1, round(cols * (h / max(1, w)) * aspect * k))
    return cols, rows


def convert(img, params=None, cols=None, rows=None):
    """QImage → AsciiArt selon les réglages (voir DEFAULTS)."""
    import time
    t0 = time.perf_counter()
    P = dict(DEFAULTS)
    if params:
        P.update(params)
    if img is None or img.isNull():
        return AsciiArt([""])
    mode = P["mode"]
    img = flatten_alpha(img, P["dark_bg"])
    aspect = char_aspect(P["font"])
    cols, rows = grid_size(img.width(), img.height(), P, aspect, cols, rows)

    if mode == "braille":
        sx, sy = 2, 4
    elif mode == "blocks":
        sx, sy = 2, 2
    elif mode == "halfblock":
        sx, sy = 1, 2
    else:
        sx, sy = PRECISIONS.get(P["precision"], (2, 4))

    small = img.scaled(cols * sx, rows * sy, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    rgb = rgb_to_array(small)
    lum = (rgb[..., 0] * 0.2126 + rgb[..., 1] * 0.7152 + rgb[..., 2] * 0.0722) / 255.0
    lum = adjust(lum, P)
    ink = lum if P["dark_bg"] else 1.0 - lum
    if P["invert"]:
        ink = 1.0 - ink

    cell_rgb = _blocks(rgb, rows, sy, cols, sx).mean(axis=2)
    if P["saturation"] != 100:
        g = cell_rgb.mean(axis=-1, keepdims=True)
        cell_rgb = g + (cell_rgb - g) * (P["saturation"] / 100.0)
    cell_rgb = np.clip(cell_rgb, 0, 255).astype(np.uint8)
    cell_ink = _blocks(ink, rows, sy, cols, sx).mean(axis=-1)
    top = bottom = None

    if mode == "braille":
        bits = quantize(ink, [0.0, 1.0], P["dither"]).astype(np.uint8)
        b = _blocks(bits, rows, 4, cols, 2)            # ordre : (y, x) ligne par ligne
        weights = np.array([0x01, 0x08, 0x02, 0x10, 0x04, 0x20, 0x40, 0x80], dtype=np.int64)
        codes = (b.astype(np.int64) * weights).sum(-1)
        table = np.array([chr(0x2800 + i) for i in range(256)])
        grid = table[codes]
        if P["edges"] == 0:
            grid[codes == 0] = " "
    elif mode == "blocks":
        bits = quantize(ink, [0.0, 1.0], P["dither"]).astype(np.int64)
        b = _blocks(bits, rows, 2, cols, 2)
        codes = b[..., 0] | (b[..., 1] << 1) | (b[..., 2] << 2) | (b[..., 3] << 3)
        grid = np.array(list(QUADRANTS))[codes]
    elif mode == "halfblock":
        bits = quantize(ink, [0.0, 1.0], P["dither"]).astype(np.int64)
        b = _blocks(bits, rows, 2, cols, 1)
        grid = np.array(list(HALF))[b[..., 0] | (b[..., 1] << 1)]
        px = _blocks(rgb, rows, 2, cols, 1)
        if P["saturation"] != 100:
            g = px.mean(axis=-1, keepdims=True)
            px = g + (px - g) * (P["saturation"] / 100.0)
        px = np.clip(px, 0, 255).astype(np.uint8)
        top, bottom = px[:, :, 0], px[:, :, 1]
    else:
        atlas = GlyphAtlas.get(P["font"], charset_of(P), sx, sy)
        if mode == "edges":
            grid = np.full((rows, cols), " ", dtype="<U1")
        elif mode == "density":
            grid = _density(cell_ink, atlas, P, charset_of(P))
        else:
            grid = _shape(_blocks(ink, rows, sy, cols, sx), atlas, P)

    if P["edges"] > 0 or mode == "edges":
        strength = P["edges"] if P["edges"] > 0 else 60
        mask, idx, chars = edge_layer(lum, rows, cols, sx, sy, strength, P["edge_style"])
        grid = grid.astype("<U1")
        grid[mask] = np.array(list(chars))[idx[mask]]

    lines = ["".join(r) for r in grid.tolist()]
    art = AsciiArt(lines, cell_rgb, cell_ink, top, bottom)
    art.elapsed = time.perf_counter() - t0
    return art


def _density(cell_ink, atlas, P, given):
    if P["auto_order"]:
        order = np.argsort(atlas.density, kind="stable")
        chars = np.array(list(atlas.chars))[order]
        levels = atlas.density[order]
        # supprime les doublons de densité (garde le premier)
        keep = np.concatenate(([True], np.diff(levels) > 1e-4))
        chars, levels = chars[keep], levels[keep]
    else:
        chars = np.array(list(dict.fromkeys(given)))
        levels = np.linspace(0, 1, len(chars))
    idx = quantize(cell_ink, levels, P["dither"])
    return chars[np.clip(idx, 0, len(chars) - 1)]


def _shape(cells, atlas, P):
    """Cœur de 4SHAPE : distance forme + ton entre chaque case et chaque glyphe."""
    rows, cols, k = cells.shape
    C = cells.reshape(-1, k).astype(np.float32)
    m = C.mean(axis=1, keepdims=True)
    boost = P["boost"] / 100.0
    if boost:
        C = np.clip(m + (C - m) * (1 + boost * 2), 0, 1)
    if P["dither"] != "none":
        # le tramage s'applique au ton moyen ; la forme reste celle de la case
        lv = np.unique(np.round(atlas.density, 3))
        q = quantize(m.reshape(rows, cols), lv, P["dither"])
        target = lv[np.clip(q, 0, len(lv) - 1)].reshape(-1, 1)
        C = np.clip(C + (target - m), 0, 1)
        m = target
    G = atlas.vectors
    lam = (P["tone"] / 100.0) * 4.0
    out = np.empty(len(C), dtype=np.int64)
    step = 8192
    gm = atlas.density[None, :]
    for s in range(0, len(C), step):
        c = C[s:s + step]
        d = ((c * c).sum(1, keepdims=True) - 2 * c @ G.T + atlas.sq[None, :]) / k
        if lam:
            d += lam * (c.mean(1, keepdims=True) - gm) ** 2
        out[s:s + step] = d.argmin(axis=1)
    return np.array(list(atlas.chars))[out].reshape(rows, cols)
