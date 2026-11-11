"""Icônes vectorielles dessinées à la main (même style que 4tafy) + icône de l'application.

Aucune image externe : tout est dessiné avec QPainter, donc les icônes prennent les couleurs du thème.
"""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QPolygonF


def _pen(c, w=2.0):
    return QPen(c, w, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)


def _poly(*pts):
    return QPolygonF([QPointF(x, y) for x, y in pts])


def _draw(name, p, c):
    p.setBrush(Qt.NoBrush)
    p.setPen(_pen(c))
    L = lambda x1, y1, x2, y2: p.drawLine(QPointF(x1, y1), QPointF(x2, y2))  # noqa: E731
    if name == "image":
        p.drawRoundedRect(QRectF(3, 4.5, 18, 15), 3, 3)
        p.drawPolyline(_poly((3.5, 17), (9, 11.5), (13, 15.5), (15.5, 13), (20.5, 18)))
        p.setBrush(c); p.drawEllipse(QPointF(15.5, 9), 1.6, 1.6)
    elif name == "text":
        p.setPen(_pen(c, 2.4))
        L(5, 5, 19, 5); L(12, 5, 12, 20); L(9, 20, 15, 20)
    elif name == "camera":
        p.drawRoundedRect(QRectF(3, 7, 13, 11), 2.5, 2.5)
        p.drawPolygon(_poly((16, 10.5), (21, 7.5), (21, 17.5), (16, 14.5)))
    elif name == "pencil":
        path = QPainterPath(); path.moveTo(4, 20); path.lineTo(5, 15.5); path.lineTo(16, 4.5)
        path.lineTo(19.5, 8); path.lineTo(8.5, 19); path.closeSubpath()
        p.drawPath(path); L(13.5, 7, 17, 10.5)
    elif name == "gallery":
        for x, y in ((3.5, 3.5), (13, 3.5), (3.5, 13), (13, 13)):
            p.drawRoundedRect(QRectF(x, y, 7.5, 7.5), 2, 2)
    elif name == "brush":
        path = QPainterPath(); path.moveTo(20, 3.5); path.lineTo(10.5, 13); path.lineTo(12.5, 15); path.lineTo(21, 5); path.closeSubpath()
        p.setBrush(c); p.drawPath(path)
        tip = QPainterPath(); tip.moveTo(9.5, 14); tip.cubicTo(5, 13.5, 6, 19, 3, 20.5); tip.cubicTo(8, 21, 12, 19.5, 11.5, 16)
        p.drawPath(tip)
    elif name == "copy":
        p.drawRoundedRect(QRectF(8, 8, 12, 12), 2.5, 2.5)
        p.drawPolyline(_poly((16, 5), (16, 4), (4, 4), (4, 16), (5, 16)))
    elif name == "save":
        L(12, 3, 12, 15); p.drawPolyline(_poly((7, 10.5), (12, 15.5), (17, 10.5)))
        p.drawPolyline(_poly((4, 15), (4, 20), (20, 20), (20, 15)))
    elif name == "folder":
        p.drawPolyline(_poly((3, 19), (3, 5), (9, 5), (11, 7.5), (21, 7.5), (21, 19), (3, 19)))
    elif name == "clipboard":
        p.drawRoundedRect(QRectF(5, 5, 14, 16), 2.5, 2.5)
        p.setBrush(c); p.drawRoundedRect(QRectF(9, 3, 6, 4), 1.5, 1.5)
    elif name == "screen":
        p.drawRoundedRect(QRectF(3, 4, 18, 12), 2, 2); L(12, 16, 12, 20); L(8, 20, 16, 20)
    elif name == "play":
        p.setPen(_pen(c, 1.5)); p.setBrush(c)
        p.drawPolygon(_poly((7.5, 4.5), (19.5, 12), (7.5, 19.5)))
    elif name == "pause":
        p.setPen(Qt.NoPen); p.setBrush(c)
        p.drawRoundedRect(QRectF(6, 4.5, 4.2, 15), 1.2, 1.2)
        p.drawRoundedRect(QRectF(13.8, 4.5, 4.2, 15), 1.2, 1.2)
    elif name == "undo":
        path = QPainterPath(); path.moveTo(5, 10); path.lineTo(15, 10); path.cubicTo(21, 10, 21, 19, 15, 19); path.lineTo(9, 19)
        p.drawPath(path); p.drawPolyline(_poly((9, 6), (5, 10), (9, 14)))
    elif name == "redo":
        path = QPainterPath(); path.moveTo(19, 10); path.lineTo(9, 10); path.cubicTo(3, 10, 3, 19, 9, 19); path.lineTo(15, 19)
        p.drawPath(path); p.drawPolyline(_poly((15, 6), (19, 10), (15, 14)))
    elif name == "trash":
        L(4, 6.5, 20, 6.5); p.drawPolyline(_poly((9, 6), (9.5, 3.5), (14.5, 3.5), (15, 6)))
        p.drawPolyline(_poly((6, 7), (7, 20.5), (17, 20.5), (18, 7))); L(10, 10, 10, 17); L(14, 10, 14, 17)
    elif name in ("zoom_in", "zoom_out"):
        p.drawEllipse(QRectF(3.5, 3.5, 12, 12)); p.setPen(_pen(c, 2.4)); L(14, 14, 20.5, 20.5)
        p.setPen(_pen(c, 1.8)); L(6.8, 9.5, 12.2, 9.5)
        if name == "zoom_in":
            L(9.5, 6.8, 9.5, 12.2)
    elif name == "fit":
        for (x, y, dx, dy) in ((4, 4, 1, 1), (20, 4, -1, 1), (4, 20, 1, -1), (20, 20, -1, -1)):
            p.drawPolyline(_poly((x, y + 5 * dy), (x, y), (x + 5 * dx, y)))
    elif name == "eraser":
        path = QPainterPath(); path.moveTo(8, 20); path.lineTo(3.5, 15.5); path.lineTo(14, 5); path.lineTo(20.5, 11.5)
        path.lineTo(12, 20); path.closeSubpath(); p.drawPath(path); L(9, 10, 15, 16); L(8, 20, 20, 20)
    elif name == "line":
        p.setPen(_pen(c, 2.4)); L(5, 19, 19, 5)
    elif name == "rect":
        p.drawRect(QRectF(4.5, 6, 15, 12))
    elif name == "ellipse":
        p.drawEllipse(QRectF(3.5, 5.5, 17, 13))
    elif name == "fill":
        path = QPainterPath(); path.moveTo(11, 3.5); path.lineTo(19, 11.5); path.lineTo(11.5, 19); path.lineTo(3.5, 11)
        path.closeSubpath(); p.drawPath(path)
        p.setBrush(c); p.drawEllipse(QRectF(17.5, 15, 4, 5))
    elif name == "picker":
        p.drawPolyline(_poly((4, 20), (5, 16), (13, 8))); p.setPen(_pen(c, 3)); L(12, 7, 17, 12)
        p.setBrush(c); p.setPen(_pen(c, 1.5)); p.drawEllipse(QPointF(17.5, 6.5), 2.6, 2.6)
    elif name == "textcursor":
        L(8, 4, 16, 4); L(8, 20, 16, 20); L(12, 4, 12, 20)
    elif name == "send":
        p.drawPolygon(_poly((3.5, 11), (20.5, 4), (14, 20.5), (11.5, 13)))
        L(11.5, 13, 20.5, 4)
    elif name == "plus":
        p.setPen(_pen(c, 2.2)); L(12, 4, 12, 20); L(4, 12, 20, 12)
    elif name == "close":
        L(6, 6, 18, 18); L(18, 6, 6, 18)
    elif name == "star":
        pts = []
        import math
        for i in range(10):
            r = 9 if i % 2 == 0 else 4
            a = -math.pi / 2 + i * math.pi / 5
            pts.append((12 + r * math.cos(a), 12.5 + r * math.sin(a)))
        p.drawPolygon(_poly(*pts))
    elif name == "dice":
        p.drawRoundedRect(QRectF(4, 4, 16, 16), 3.5, 3.5)
        p.setPen(Qt.NoPen); p.setBrush(c)
        for x, y in ((8.5, 8.5), (15.5, 15.5), (12, 12), (15.5, 8.5), (8.5, 15.5)):
            p.drawEllipse(QPointF(x, y), 1.5, 1.5)
    elif name == "chevron_left":
        p.setPen(_pen(c, 2.4)); p.drawPolyline(_poly((15, 5), (8, 12), (15, 19)))
    elif name == "chevron_right":
        p.setPen(_pen(c, 2.4)); p.drawPolyline(_poly((9, 5), (16, 12), (9, 19)))
    elif name == "grid":
        p.drawRect(QRectF(4, 4, 16, 16)); L(9.3, 4, 9.3, 20); L(14.6, 4, 14.6, 20); L(4, 9.3, 20, 9.3); L(4, 14.6, 20, 14.6)
    elif name == "snapshot":
        p.drawEllipse(QRectF(6, 6, 12, 12)); p.setBrush(c); p.drawEllipse(QRectF(9.5, 9.5, 5, 5))
    elif name == "mirror":
        L(12, 3, 12, 21)
        p.drawPolygon(_poly((9.5, 7), (3.5, 17), (9.5, 17))); p.drawPolygon(_poly((14.5, 7), (20.5, 17), (14.5, 17)))
    elif name == "dots":
        p.setPen(Qt.NoPen); p.setBrush(c)
        for x in (5, 12, 19):
            p.drawEllipse(QPointF(x, 12), 2, 2)


def icon(name, color="#ffffff", size=48):
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(size / 24.0, size / 24.0)
    _draw(name, p, QColor(color))
    p.end()
    return QIcon(pm)


def _squircle(rect, n=5.0, steps=160):
    import math
    path = QPainterPath()
    cx, cy = rect.center().x(), rect.center().y()
    a, b = rect.width() / 2, rect.height() / 2
    for i in range(steps + 1):
        t = 2 * math.pi * i / steps
        ct, st = math.cos(t), math.sin(t)
        x = cx + a * (abs(ct) ** (2 / n)) * (1 if ct >= 0 else -1)
        y = cy + b * (abs(st) ** (2 / n)) * (1 if st >= 0 else -1)
        path.moveTo(x, y) if i == 0 else path.lineTo(x, y)
    path.closeSubpath()
    return path


def app_icon(accent="#a855f7", second="#22d3ee"):
    """Icône 4scii : squircle dégradé avec une petite grille de caractères et un « 4 »."""
    icon_ = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        pm = QPixmap(size, size)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        s = size
        r = QRectF(s * 0.04, s * 0.04, s * 0.92, s * 0.92)
        g = QLinearGradient(r.topLeft(), r.bottomRight())
        g.setColorAt(0, QColor(accent).lighter(115))
        g.setColorAt(1, QColor(second).darker(120))
        p.setPen(Qt.NoPen)
        p.setBrush(g)
        p.drawPath(_squircle(r))
        # trame de caractères en filigrane
        if s >= 48:
            f = QFont("Consolas")
            f.setPixelSize(max(4, int(s * 0.11)))
            f.setBold(True)
            p.setFont(f)
            p.setPen(QColor(255, 255, 255, 55))
            rows = ["@#*+:.", ".:+*#@", "#*+:.@"]
            for i, row in enumerate(rows):
                p.drawText(QPointF(s * 0.16, s * (0.24 + i * 0.27)), "  ".join(row[:4]))
        f = QFont("Consolas")
        f.setPixelSize(int(s * 0.62))
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor(255, 255, 255))
        p.drawText(r, Qt.AlignCenter, "4")
        p.end()
        icon_.addPixmap(pm)
    return icon_
