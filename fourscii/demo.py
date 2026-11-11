"""Image de démonstration dessinée à la volée (planète, anneau, étoiles et logo)."""
import random

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QLinearGradient, QPainter, QPen, QRadialGradient


def demo_image(w=960, h=640):
    img = QImage(w, h, QImage.Format_RGB888)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    sky = QLinearGradient(0, 0, 0, h)
    sky.setColorAt(0, QColor("#120626"))
    sky.setColorAt(1, QColor("#02040c"))
    p.fillRect(img.rect(), sky)
    rnd = random.Random(4)
    p.setPen(Qt.NoPen)
    for _ in range(260):
        a = rnd.randint(60, 255)
        p.setBrush(QColor(255, 255, 255, a))
        r = rnd.choice((0.8, 1.0, 1.4, 2.2))
        p.drawEllipse(QPointF(rnd.uniform(0, w), rnd.uniform(0, h)), r, r)
    c = QPointF(w * 0.62, h * 0.48)
    R = h * 0.30
    # anneau arrière
    p.save()
    p.translate(c)
    p.rotate(-18)
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(QColor(250, 200, 120, 150), 16))
    p.drawArc(QRectF(-R * 1.75, -R * 0.42, R * 3.5, R * 0.84), 0, 180 * 16)
    p.restore()
    g = QRadialGradient(c + QPointF(-R * 0.4, -R * 0.45), R * 1.5)
    g.setColorAt(0, QColor("#ffe7a8"))
    g.setColorAt(0.35, QColor("#f08a4b"))
    g.setColorAt(0.75, QColor("#7b2d8f"))
    g.setColorAt(1, QColor("#14051f"))
    p.setPen(Qt.NoPen)
    p.setBrush(g)
    p.drawEllipse(c, R, R)
    # bandes
    p.save()
    p.setClipRect(QRectF(c.x() - R, c.y() - R, 2 * R, 2 * R))
    for i, y in enumerate((-0.35, -0.05, 0.3)):
        p.setBrush(QColor(255, 255, 255, 26 if i % 2 else 40))
        p.drawEllipse(QRectF(c.x() - R, c.y() + y * R, 2 * R, R * 0.16))
    p.restore()
    # anneau avant
    p.save()
    p.translate(c)
    p.rotate(-18)
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(QColor(255, 220, 150, 220), 16))
    p.drawArc(QRectF(-R * 1.75, -R * 0.42, R * 3.5, R * 0.84), 180 * 16, 180 * 16)
    p.restore()
    # logo
    f = QFont("Arial Black")
    f.setPixelSize(int(h * 0.2))
    f.setBold(True)
    p.setFont(f)
    tg = QLinearGradient(0, h * 0.62, 0, h * 0.86)
    tg.setColorAt(0, QColor("#ffffff"))
    tg.setColorAt(1, QColor("#c084fc"))
    p.setPen(QPen(tg, 1))
    p.drawText(QRectF(w * 0.05, h * 0.60, w * 0.6, h * 0.3), Qt.AlignLeft | Qt.AlignVCenter, "4scii")
    p.end()
    return img
