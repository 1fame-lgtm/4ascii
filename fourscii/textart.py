"""Bannières de texte : n'importe quelle police installée → art ASCII.

Le texte est dessiné en haute résolution, puis passe dans le moteur 4SHAPE (ou dans un des
styles de blocs). Ombres, relief 3D et contours sont calculés sur la grille de cases.
"""
import numpy as np
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QImage, QPainter

from . import engine
from .engine import AsciiArt

STYLES = {
    "shape": "4SHAPE (lettres ASCII)",
    "outline": "Contour ASCII",
    "blocks": "Blocs pleins █",
    "shadow": "Blocs + ombre",
    "relief": "Relief 3D",
    "half": "Demi-blocs ▀▄",
    "quad": "Quadrants ▚ (fin)",
    "braille": "Braille ⣿ (très fin)",
    "fill": "Rempli avec un mot",
}


def render_text_image(text, family, bold=True, italic=False, spacing=0, align="left"):
    font = QFont(family)
    font.setPixelSize(160)
    font.setBold(bold)
    font.setItalic(italic)
    font.setLetterSpacing(QFont.AbsoluteSpacing, spacing * 4)
    fm = QFontMetricsF(font)
    lines = (text or " ").split("\n")
    widths = [fm.horizontalAdvance(l) for l in lines]
    W = int(max(widths) + 80)
    H = int(fm.lineSpacing() * len(lines) + 80)
    img = QImage(W, H, QImage.Format_Grayscale8)
    img.fill(0)
    p = QPainter(img)
    p.setRenderHint(QPainter.TextAntialiasing)
    p.setFont(font)
    p.setPen(QColor(255, 255, 255))
    for i, (l, w) in enumerate(zip(lines, widths)):
        x = 40 + {"left": 0, "center": (max(widths) - w) / 2, "right": max(widths) - w}[align]
        p.drawText(QPointF(x, 40 + fm.ascent() + i * fm.lineSpacing()), l)
    p.end()
    a = engine.gray_to_array(img)
    ys, xs = np.nonzero(a > 0.08)
    if len(xs) == 0:
        return img.copy(0, 0, 8, 8)
    m = 6
    x0, x1 = max(0, xs.min() - m), min(W, xs.max() + m)
    y0, y1 = max(0, ys.min() - m), min(H, ys.max() + m)
    return img.copy(int(x0), int(y0), int(x1 - x0), int(y1 - y0))


def _dilate(a, r):
    out = a.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dx * dx + dy * dy <= r * r:
                out = np.maximum(out, np.roll(np.roll(a, dy, 0), dx, 1))
    return out


def _cells(img, rows, font, charset=" █"):
    art = engine.convert(img, dict(mode="density", charset="Personnalisé", custom_chars=charset,
                                   auto_order=False, autolevels=False, font=font, precision="Normale"),
                         rows=rows)
    return np.array([[c != " " for c in l] for l in art.lines], dtype=bool)


def make_banner(text, family, rows=8, style="shape", charset="ASCII complet", bold=True, italic=False,
                spacing=0, align="left", shadow_char="░", fill_word="4SCII", thickness=2, ascii_font="Consolas"):
    img = render_text_image(text, family, bold, italic, spacing, align)
    rows = max(2, int(rows))
    base = dict(autolevels=False, font=ascii_font, dark_bg=True, edges=0, contrast=20)

    if style == "shape":
        return engine.convert(img, dict(base, mode="shape", charset=charset, tone=25, boost=40), rows=rows)
    if style == "half":
        return engine.convert(img, dict(base, mode="halfblock"), rows=rows)
    if style == "quad":
        return engine.convert(img, dict(base, mode="blocks"), rows=rows)
    if style == "braille":
        return engine.convert(img, dict(base, mode="braille"), rows=rows)
    if style == "outline":
        a = engine.gray_to_array(img) > 0.5
        r = max(1, int(img.height() / max(1, rows) / 6 * thickness))
        a = np.pad(a, r + 2)
        ring = _dilate(a.astype(np.float32), r) - a
        out = engine.array_to_qimage(ring)
        return engine.convert(out, dict(base, mode="shape", charset=charset, tone=10, boost=80), rows=rows)

    mask = _cells(img, rows, ascii_font)
    R, C = mask.shape
    if style == "blocks":
        lines = ["".join("█" if v else " " for v in r) for r in mask]
        return AsciiArt(lines, ink=mask.astype(np.float32))
    if style == "fill":
        word = fill_word or "#"
        lines, k = [], 0
        for r in mask:
            s = []
            for v in r:
                if v:
                    s.append(word[k % len(word)])
                    k += 1
                else:
                    s.append(" ")
            lines.append("".join(s))
        return AsciiArt(lines, ink=mask.astype(np.float32))
    if style == "shadow":
        g = np.full((R + 1, C + 2), " ", dtype="<U1")
        ink = np.zeros((R + 1, C + 2), np.float32)
        sh = np.zeros_like(ink, dtype=bool)
        sh[1:, 2:] = mask
        g[sh] = shadow_char or "░"
        ink[sh] = 0.35
        g[:R, :C][mask] = "█"
        ink[:R, :C][mask] = 1.0
        return AsciiArt(["".join(r) for r in g.tolist()], ink=ink)
    if style == "relief":
        depth = max(1, min(4, thickness))
        g = np.full((R + depth, C + depth * 2), " ", dtype="<U1")
        ink = np.zeros(g.shape, np.float32)
        layers = "▓▒░"
        for d in range(depth, 0, -1):
            ch = layers[min(len(layers) - 1, d - 1)]
            sl = (slice(d, d + R), slice(d * 2, d * 2 + C))
            g[sl][mask] = ch
            ink[sl][mask] = 1.0 - d / (depth + 1.5)
        g[:R, :C][mask] = "█"
        ink[:R, :C][mask] = 1.0
        return AsciiArt(["".join(r) for r in g.tolist()], ink=ink)
    return engine.convert(img, dict(base, mode="shape", charset=charset), rows=rows)
