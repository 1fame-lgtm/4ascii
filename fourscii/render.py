"""Mise en couleur, rendu en image et exports (TXT, HTML, ANSI, PNG, SVG, animation HTML)."""
import colorsys
import html

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QImage, QPainter

COLOR_MODES = {
    "mono": "Mono (thème)",
    "color": "Couleurs de l'image",
    "ink": "Dégradé selon l'encre",
    "h_grad": "Dégradé horizontal",
    "v_grad": "Dégradé vertical",
    "rainbow": "Arc-en-ciel",
    "matrix": "Matrix",
    "fire": "Feu",
    "ice": "Glace",
}


def _hex(c):
    c = QColor(c)
    return np.array([c.red(), c.green(), c.blue()], dtype=np.float32)


def _lerp(a, b, t):
    return (a[None, None, :] * (1 - t[..., None]) + b[None, None, :] * t[..., None])


def _palette(stops, t):
    """Interpole une palette de couleurs [(pos, '#hex'), ...] sur t (0..1)."""
    pos = np.array([s[0] for s in stops], dtype=np.float32)
    cols = np.array([_hex(s[1]) for s in stops])
    out = np.empty(t.shape + (3,), dtype=np.float32)
    for i in range(3):
        out[..., i] = np.interp(t, pos, cols[:, i])
    return out


def layers(art, mode="mono", c1="#a855f7", c2="#22d3ee"):
    """→ (lignes, fg (rows, cols, 3) uint8 ou None, bg idem ou None) prêtes à afficher / exporter."""
    lines = art.lines
    rows, cols = art.rows, art.cols
    if mode == "mono" or rows == 0 or cols == 0:
        return lines, None, None
    if mode == "color":
        if art.top is not None and art.bottom is not None:
            # pixels pleine couleur : ▀ avec le haut en encre et le bas en fond
            return ["▀" * len(l) for l in lines], art.top, art.bottom
        if art.rgb is not None:
            return lines, art.rgb, None
        mode = "ink"
    ink = art.ink
    if ink is None or ink.shape != (rows, cols):
        ink = np.array([[0.0 if ch == " " else 1.0 for ch in l.ljust(cols)] for l in lines], dtype=np.float32)
    yy, xx = np.mgrid[0:rows, 0:cols].astype(np.float32)
    a, b = _hex(c1), _hex(c2)
    if mode == "ink":
        fg = _lerp(b, a, np.clip(ink, 0, 1))
    elif mode == "h_grad":
        fg = _lerp(a, b, xx / max(1, cols - 1))
    elif mode == "v_grad":
        fg = _lerp(a, b, yy / max(1, rows - 1))
    elif mode == "rainbow":
        h = ((xx / max(1, cols)) * 0.8 + (yy / max(1, rows)) * 0.2) % 1.0
        fg = np.zeros((rows, cols, 3), np.float32)
        for hv in np.unique(np.round(h, 2)):
            r, g, bb = colorsys.hsv_to_rgb(float(hv), 0.75, 1.0)
            fg[np.round(h, 2) == hv] = (r * 255, g * 255, bb * 255)
    elif mode == "matrix":
        fg = _palette([(0, "#003b12"), (0.5, "#00c853"), (1, "#d6ffe0")], np.clip(ink, 0, 1))
    elif mode == "fire":
        fg = _palette([(0, "#3a0000"), (0.35, "#c62828"), (0.65, "#ff9100"), (1, "#fff59d")], np.clip(ink, 0, 1))
    elif mode == "ice":
        fg = _palette([(0, "#0d1b4c"), (0.5, "#2979ff"), (1, "#e0f7ff")], np.clip(ink, 0, 1))
    else:
        return lines, None, None
    return lines, np.clip(fg, 0, 255).astype(np.uint8), None


# --------------------------------------------------------------------------- rendu image
def mono_font(family, px):
    f = QFont(family)
    f.setStyleHint(QFont.Monospace)
    f.setPixelSize(max(2, int(px)))
    return f


def cell_size(family, px):
    fm = QFontMetricsF(mono_font(family, px))
    return fm.horizontalAdvance("M"), fm.height(), fm.ascent()


def render_image(lines, fg, bg, family, px, default_fg, background=None, padding=0):
    """Dessine l'art dans une QImage ; chaque caractère est placé sur sa case (police de secours alignée)."""
    font = mono_font(family, px)
    cw, ch, asc = cell_size(family, px)
    rows = len(lines)
    cols = max((len(l) for l in lines), default=0)
    W = max(1, int(cols * cw + 2 * padding + 0.999))
    H = max(1, int(rows * ch + 2 * padding + 0.999))
    img = QImage(W, H, QImage.Format_ARGB32_Premultiplied)
    img.fill(QColor(background) if background is not None else Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.TextAntialiasing)
    p.setFont(font)
    if bg is not None:
        p.setPen(Qt.NoPen)
        for y in range(min(rows, bg.shape[0])):
            row = bg[y]
            for x in range(min(len(lines[y]), row.shape[0])):
                r, g, b = row[x]
                p.fillRect(QRectF(padding + x * cw, padding + y * ch, cw + 0.6, ch + 0.6), QColor(int(r), int(g), int(b)))
    dfg = QColor(default_fg)
    p.setPen(dfg)
    last = None
    for y, line in enumerate(lines):
        by = padding + y * ch + asc
        for x, c in enumerate(line):
            if c == " ":
                continue
            if fg is not None and y < fg.shape[0] and x < fg.shape[1]:
                col = tuple(int(v) for v in fg[y, x])
                if col != last:
                    p.setPen(QColor(*col))
                    last = col
            p.drawText(QPointF(padding + x * cw, by), c)
    p.end()
    return img


# --------------------------------------------------------------------------- exports texte
def to_txt(lines):
    return "\n".join(l.rstrip() for l in lines) + "\n"


def _hexs(c):
    return "#%02x%02x%02x" % (int(c[0]), int(c[1]), int(c[2]))


def html_pre(lines, fg, bg):
    out = []
    for y, line in enumerate(lines):
        run, run_style, parts = "", None, []
        for x, c in enumerate(line):
            st = []
            if fg is not None and c != " ":
                st.append("color:" + _hexs(fg[y, x]))
            if bg is not None:
                st.append("background:" + _hexs(bg[y, x]))
            st = ";".join(st)
            if st != run_style and run:
                parts.append(f'<span style="{run_style}">{html.escape(run)}</span>' if run_style else html.escape(run))
                run = ""
            run_style = st
            run += c
        if run:
            parts.append(f'<span style="{run_style}">{html.escape(run)}</span>' if run_style else html.escape(run))
        out.append("".join(parts))
    return "\n".join(out)


def to_html(lines, fg, bg, family, text_color, background, title="4scii"):
    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><title>{html.escape(title)}</title>
<style>
body {{ margin:0; background:{background}; display:flex; justify-content:center; padding:24px; }}
pre {{ font-family:"{family}", Consolas, "DejaVu Sans Mono", monospace; font-size:10px; line-height:1.15;
       color:{text_color}; margin:0; }}
</style></head>
<body><pre>{html_pre(lines, fg, bg)}</pre></body></html>
"""


def to_ansi(lines, fg, bg):
    out = []
    for y, line in enumerate(lines):
        s, last = [], None
        for x, c in enumerate(line):
            code = ""
            if fg is not None:
                r, g, b = (int(v) for v in fg[y, x])
                code += f"\x1b[38;2;{r};{g};{b}m"
            if bg is not None:
                r, g, b = (int(v) for v in bg[y, x])
                code += f"\x1b[48;2;{r};{g};{b}m"
            if code != last:
                s.append(code)
                last = code
            s.append(c)
        s.append("\x1b[0m")
        out.append("".join(s))
    return "\n".join(out) + "\n"


def to_svg(lines, fg, bg, family, text_color, background, px=14):
    cw, ch, asc = cell_size(family, px)
    rows, cols = len(lines), max((len(l) for l in lines), default=0)
    W, H = cols * cw, rows * ch
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.0f}" height="{H:.0f}" '
             f'viewBox="0 0 {W:.1f} {H:.1f}">',
             f'<rect width="100%" height="100%" fill="{background}"/>',
             f'<g font-family="{html.escape(family)}, monospace" font-size="{px}" fill="{text_color}" '
             f'xml:space="preserve">']
    if bg is not None:
        for y in range(rows):
            for x in range(len(lines[y])):
                parts.append(f'<rect x="{x * cw:.1f}" y="{y * ch:.1f}" width="{cw + 0.5:.1f}" '
                             f'height="{ch + 0.5:.1f}" fill="{_hexs(bg[y, x])}"/>')
    for y, line in enumerate(lines):
        if fg is None:
            if line.strip():
                parts.append(f'<text x="0" y="{y * ch + asc:.1f}" textLength="{len(line) * cw:.1f}">'
                             f'{html.escape(line)}</text>')
            continue
        for x, c in enumerate(line):
            if c != " ":
                parts.append(f'<text x="{x * cw:.1f}" y="{y * ch + asc:.1f}" fill="{_hexs(fg[y, x])}">'
                             f'{html.escape(c)}</text>')
    parts.append("</g></svg>")
    return "\n".join(parts)


def to_animated_html(frames, delays, family, text_color, background, title="4scii — animation"):
    """frames : liste de (lignes, fg, bg)."""
    import json
    blocks = [html_pre(l, f, b) for l, f, b in frames]
    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><title>{html.escape(title)}</title>
<style>
body {{ margin:0; background:{background}; display:flex; justify-content:center; padding:24px; }}
pre {{ font-family:"{family}", Consolas, monospace; font-size:10px; line-height:1.15; color:{text_color}; margin:0; }}
</style></head>
<body><pre id="f"></pre>
<script>
const F = {json.dumps(blocks)};
const D = {json.dumps([max(20, int(d)) for d in delays])};
let i = 0; const el = document.getElementById('f');
function tick() {{ el.innerHTML = F[i]; const d = D[i]; i = (i + 1) % F.length; setTimeout(tick, d); }}
tick();
</script></body></html>
"""
