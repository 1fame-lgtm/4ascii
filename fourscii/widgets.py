"""Widgets réutilisables : visionneuse d'art ASCII zoomable, curseurs étiquetés, mise en page fluide…"""
from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (QComboBox, QFrame, QHBoxLayout, QLabel, QLayout, QScrollArea, QSizePolicy,
                               QSlider, QVBoxLayout, QWidget)

from . import render


# --------------------------------------------------------------------------- visionneuse
class _Canvas(QWidget):
    def __init__(self, viewer):
        super().__init__()
        self.viewer = viewer
        self.img = None

    def sizeHint(self):
        return self.img.size() / max(1.0, self.devicePixelRatioF()) if self.img else QSize(10, 10)

    def paintEvent(self, _):
        if self.img is None:
            return
        p = QPainter(self)
        p.drawImage(0, 0, self.img)
        p.end()


class ArtViewer(QScrollArea):
    """Affiche des lignes ASCII (avec couleurs optionnelles) ; Ctrl + molette pour zoomer."""
    zoomed = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.NoFrame)
        self.setAlignment(Qt.AlignCenter)
        self.canvas = _Canvas(self)
        self.setWidget(self.canvas)
        self.setWidgetResizable(False)
        self.lines, self.fg, self.bg = [""], None, None
        self.family = "Consolas"
        self.px = 9.0
        self.text_color = "#ffffff"
        self.background = None
        self.auto_fit = True

    def set_style(self, family, text_color, background):
        self.family, self.text_color, self.background = family, text_color, background
        self._rebuild()

    def set_layers(self, lines, fg=None, bg=None):
        self.lines, self.fg, self.bg = lines or [""], fg, bg
        if self.auto_fit:
            self._fit_px()
        self._rebuild()

    def _fit_px(self):
        cols = max((len(l) for l in self.lines), default=1) or 1
        rows = len(self.lines) or 1
        cw, ch, _ = render.cell_size(self.family, 100)
        avail_w = max(50, self.viewport().width() - 16)
        avail_h = max(50, self.viewport().height() - 16)
        px = max(2.0, min(28.0, 100 * avail_w / (cols * cw), 100 * avail_h / (rows * ch)))
        dpr = self.devicePixelRatioF()
        for _ in range(40):  # la police est rendue en tailles entières : on vérifie la taille réelle
            rcw, rch, _ = render.cell_size(self.family, int(px * dpr))
            if (cols * rcw / dpr <= avail_w and rows * rch / dpr <= avail_h) or px <= 2.0:
                break
            px = max(2.0, px * 0.97)
        self.px = px

    def fit(self):
        self.auto_fit = True
        self._fit_px()
        self._rebuild()

    def zoom(self, factor):
        self.auto_fit = False
        self.px = max(2.0, min(64.0, self.px * factor))
        self._rebuild()

    def _rebuild(self):
        dpr = self.devicePixelRatioF()
        img = render.render_image(self.lines, self.fg, self.bg, self.family, self.px * dpr, self.text_color,
                                  self.background)
        img.setDevicePixelRatio(dpr)
        self.canvas.img = img
        self.canvas.resize(int(img.width() / dpr), int(img.height() / dpr))
        self.canvas.update()
        self.zoomed.emit(self.px)

    def wheelEvent(self, e):
        if e.modifiers() & Qt.ControlModifier:
            self.zoom(1.12 if e.angleDelta().y() > 0 else 1 / 1.12)
            e.accept()
            return
        super().wheelEvent(e)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.auto_fit and self.lines:
            self._fit_px()
            self._rebuild()


# --------------------------------------------------------------------------- contrôles
class LabeledSlider(QWidget):
    """Nom à gauche, curseur, valeur à droite. `scale` permet des valeurs décimales."""
    valueChanged = Signal(float)

    def __init__(self, text, lo, hi, value, scale=1, suffix="", tip=""):
        super().__init__()
        self.scale = scale
        self.suffix = suffix
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 2, 0, 2)
        lay.setSpacing(2)
        top = QHBoxLayout()
        self.label = QLabel(text)
        self.label.setObjectName("sub")
        top.addWidget(self.label)
        top.addStretch()
        self.val = QLabel()
        self.val.setObjectName("value")
        self.val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        top.addWidget(self.val)
        lay.addLayout(top)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(int(lo * scale), int(hi * scale))
        self.slider.setValue(int(round(value * scale)))
        self.slider.valueChanged.connect(self._changed)
        lay.addWidget(self.slider)
        if tip:
            self.setToolTip(tip)
        self._show()

    def _show(self):
        v = self.value()
        self.val.setText((f"{v:.2f}" if self.scale != 1 else f"{int(v)}") + self.suffix)

    def _changed(self, _):
        self._show()
        self.valueChanged.emit(self.value())

    def value(self):
        return self.slider.value() / self.scale

    def setValue(self, v):
        self.slider.blockSignals(True)
        self.slider.setValue(int(round(v * self.scale)))
        self.slider.blockSignals(False)
        self._show()


def combo(items, current=None):
    """QComboBox à partir d'un dict {clé: libellé} ou d'une liste ; la clé est dans userData."""
    c = QComboBox()
    c.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
    c.setMinimumContentsLength(8)
    pairs = items.items() if isinstance(items, dict) else [(i, i) for i in items]
    for k, v in pairs:
        c.addItem(v, k)
    if current is not None:
        set_combo(c, current)
    return c


def set_combo(c, key):
    i = c.findData(key)
    if i >= 0:
        c.blockSignals(True)
        c.setCurrentIndex(i)
        c.blockSignals(False)


def section(text):
    l = QLabel(text.upper())
    l.setObjectName("section")
    l.setContentsMargins(2, 10, 0, 2)
    return l


def hline():
    f = QFrame()
    f.setObjectName("sep")
    return f


def caption(text):
    l = QLabel(text)
    l.setObjectName("sub")
    return l


# --------------------------------------------------------------------------- mise en page fluide
class FlowLayout(QLayout):
    def __init__(self, parent=None, spacing=14):
        super().__init__(parent)
        self.items = []
        self.setSpacing(spacing)
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item):
        self.items.append(item)

    def count(self):
        return len(self.items)

    def itemAt(self, i):
        return self.items[i] if 0 <= i < len(self.items) else None

    def takeAt(self, i):
        return self.items.pop(i) if 0 <= i < len(self.items) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, w):
        return self._do(QRect(0, 0, w, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        s = QSize()
        for it in self.items:
            s = s.expandedTo(it.minimumSize())
        return s

    def _do(self, rect, test):
        x, y, line_h = rect.x(), rect.y(), 0
        sp = self.spacing()
        for it in self.items:
            hint = it.sizeHint()
            nx = x + hint.width() + sp
            if nx - sp > rect.right() and line_h > 0:
                x, y = rect.x(), y + line_h + sp
                nx = x + hint.width() + sp
                line_h = 0
            if not test:
                it.setGeometry(QRect(QPoint(x, y), hint))
            x = nx
            line_h = max(line_h, hint.height())
        return y + line_h - rect.y()


def clear_layout(layout):
    while layout.count():
        it = layout.takeAt(0)
        w = it.widget()
        if w is not None:
            w.setParent(None)
            w.deleteLater()


def expanding(w):
    w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    return w


def qcolor(c):
    return QColor(c)
