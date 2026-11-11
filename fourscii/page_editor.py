"""Atelier : éditeur de dessin ASCII (crayon, lignes intelligentes, cadres, formes, pot, texte…)."""
import math

import numpy as np
from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFontMetricsF, QKeySequence, QPainter, QPen, QShortcut
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QColorDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QScrollArea, QSpinBox, QVBoxLayout, QWidget)

from . import render
from .engine import AsciiArt
from .page_base import Page
from .widgets import combo, section

TOOLS = [("pen", "pencil", "Crayon (P)"), ("eraser", "eraser", "Gomme (E)"), ("line", "line", "Ligne (L)"),
         ("rect", "rect", "Cadre (R)"), ("ellipse", "ellipse", "Ellipse (O)"), ("fill", "fill", "Pot de remplissage (F)"),
         ("text", "textcursor", "Texte (T)"), ("picker", "picker", "Pipette (I)")]

BOXES = {
    "ascii": ("ASCII  + - |", "+-+|+-+|"),
    "single": ("Simple ┌─┐", "┌─┐│┘─└│"),
    "double": ("Double ╔═╗", "╔═╗║╝═╚║"),
    "round": ("Arrondi ╭─╮", "╭─╮│╯─╰│"),
    "heavy": ("Épais ┏━┓", "┏━┓┃┛━┗┃"),
    "block": ("Blocs █", "████████"),
    "brush": ("Caractère du pinceau", None),
}

PALETTE = list("█▓▒░#@%*+=-:.·oO0/\\|_~^<>()[]{}") + list("─│┌┐└┘├┤┬┴┼═║╔╗╚╝●○◆◇■□▲▼◀▶★☆♥")


def _line_cells(x0, y0, x1, y1):
    """Bresenham : cases traversées entre deux points."""
    pts = []
    dx, dy = abs(x1 - x0), -abs(y1 - y0)
    sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
    err = dx + dy
    while True:
        pts.append((x0, y0))
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy
    return pts


def smart_char(dx, dy, aspect):
    """Caractère qui suit le mieux la pente d'une ligne (tient compte des cases plus hautes que larges)."""
    if dx == 0 and dy == 0:
        return "*"
    ang = math.degrees(math.atan2(-dy / aspect, dx)) % 180
    if ang < 22.5 or ang >= 157.5:
        return "-"
    if ang < 67.5:
        return "/"
    if ang < 112.5:
        return "|"
    return "\\"


class EditorCanvas(QWidget):
    cursor_moved = Signal(int, int)
    picked = Signal(str, object)

    def __init__(self, page):
        super().__init__()
        self.page = page
        self.cols, self.rows = 80, 30
        self.chars = [[" "] * self.cols for _ in range(self.rows)]
        self.colors = [[None] * self.cols for _ in range(self.rows)]
        self.undo_stack, self.redo_stack = [], []
        self.px = 16
        self.family = "Consolas"
        self.text_color = QColor("#ffffff")
        self.bg = QColor("#000000")
        self.grid_color = QColor(255, 255, 255, 18)
        self.show_grid = True
        self.hover = None
        self.drag_start = None
        self.preview = {}
        self.text_cursor = None
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self._metrics()

    # ------------------------------------------------------------------ données
    def _metrics(self):
        cw, ch, asc = render.cell_size(self.family, self.px)
        self.cw, self.ch, self.asc = cw, ch, asc
        self.setFixedSize(int(self.cols * cw) + 1, int(self.rows * ch) + 1)
        self.update()

    def set_zoom(self, px):
        self.px = max(6, min(48, px))
        self._metrics()

    def snapshot(self):
        return ([r[:] for r in self.chars], [r[:] for r in self.colors], self.cols, self.rows)

    def restore(self, snap):
        chars, colors, self.cols, self.rows = snap
        self.chars = [r[:] for r in chars]
        self.colors = [r[:] for r in colors]
        self._metrics()

    def push_undo(self):
        self.undo_stack.append(self.snapshot())
        if len(self.undo_stack) > 150:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def undo(self):
        if self.undo_stack:
            self.redo_stack.append(self.snapshot())
            self.restore(self.undo_stack.pop())

    def redo(self):
        if self.redo_stack:
            self.undo_stack.append(self.snapshot())
            self.restore(self.redo_stack.pop())

    def resize_grid(self, cols, rows):
        self.push_undo()
        chars = [[" "] * cols for _ in range(rows)]
        colors = [[None] * cols for _ in range(rows)]
        for y in range(min(rows, self.rows)):
            for x in range(min(cols, self.cols)):
                chars[y][x] = self.chars[y][x]
                colors[y][x] = self.colors[y][x]
        self.chars, self.colors, self.cols, self.rows = chars, colors, cols, rows
        self._metrics()

    def clear(self):
        self.push_undo()
        self.chars = [[" "] * self.cols for _ in range(self.rows)]
        self.colors = [[None] * self.cols for _ in range(self.rows)]
        self.update()

    def load(self, lines, fg=None):
        self.push_undo()
        rows = max(1, len(lines))
        cols = max(1, max((len(l) for l in lines), default=1))
        self.cols, self.rows = cols, rows
        self.chars = [list(l.ljust(cols)) for l in lines] or [[" "]]
        self.colors = [[None] * cols for _ in range(rows)]
        if fg is not None:
            for y in range(min(rows, fg.shape[0])):
                for x in range(min(cols, fg.shape[1])):
                    if self.chars[y][x] != " ":
                        self.colors[y][x] = tuple(int(v) for v in fg[y, x])
        self._metrics()

    def lines(self):
        return ["".join(r) for r in self.chars]

    def fg_array(self):
        if not any(c for row in self.colors for c in row):
            return None
        d = self.text_color
        default = (d.red(), d.green(), d.blue())
        return np.array([[c or default for c in row] for row in self.colors], dtype=np.uint8)

    def put(self, x, y, ch, color, target=None):
        if 0 <= x < self.cols and 0 <= y < self.rows:
            if target is not None:
                target[(x, y)] = (ch, color)
            else:
                self.chars[y][x] = ch
                self.colors[y][x] = color if ch != " " else None

    # ------------------------------------------------------------------ outils
    def cell_at(self, pos):
        return int(pos.x() // self.cw), int(pos.y() // self.ch)

    def shape_cells(self, tool, a, b, target):
        page = self.page
        ch, col = page.brush_char(), page.brush_color()
        (x0, y0), (x1, y1) = a, b
        if tool == "line":
            auto = page.smart_lines.isChecked()
            c = smart_char(x1 - x0, y1 - y0, self.cw / self.ch) if auto else ch
            for x, y in _line_cells(x0, y0, x1, y1):
                self.put(x, y, c, col, target)
        elif tool == "rect":
            xa, xb = sorted((x0, x1))
            ya, yb = sorted((y0, y1))
            style = BOXES[page.box.currentData()][1] or ch * 8
            tl, t, tr, r, br, bt, bl, l = style
            for x in range(xa + 1, xb):
                self.put(x, ya, t, col, target)
                self.put(x, yb, bt, col, target)
            for y in range(ya + 1, yb):
                self.put(xa, y, l, col, target)
                self.put(xb, y, r, col, target)
            if page.fill_shapes.isChecked():
                for y in range(ya + 1, yb):
                    for x in range(xa + 1, xb):
                        self.put(x, y, ch, col, target)
            self.put(xa, ya, tl, col, target)
            self.put(xb, ya, tr, col, target)
            self.put(xa, yb, bl, col, target)
            self.put(xb, yb, br, col, target)
        elif tool == "ellipse":
            xa, xb = sorted((x0, x1))
            ya, yb = sorted((y0, y1))
            cx, cy = (xa + xb) / 2, (ya + yb) / 2
            rx, ry = max(0.5, (xb - xa) / 2), max(0.5, (yb - ya) / 2)
            fill = page.fill_shapes.isChecked()
            for y in range(ya, yb + 1):
                for x in range(xa, xb + 1):
                    d = ((x - cx) / (rx + 0.5)) ** 2 + ((y - cy) / (ry + 0.5)) ** 2
                    if d <= 1.0:
                        inner = ((x - cx) / max(0.5, rx - 0.5)) ** 2 + ((y - cy) / max(0.5, ry - 0.5)) ** 2
                        if fill or inner > 1.0:
                            self.put(x, y, ch, col, target)

    def flood(self, x, y):
        if not (0 <= x < self.cols and 0 <= y < self.rows):
            return
        src = self.chars[y][x]
        ch, col = self.page.brush_char(), self.page.brush_color()
        if src == ch and self.colors[y][x] == col:
            return
        stack, seen = [(x, y)], set()
        while stack:
            cx, cy = stack.pop()
            if (cx, cy) in seen or not (0 <= cx < self.cols and 0 <= cy < self.rows):
                continue
            if self.chars[cy][cx] != src:
                continue
            seen.add((cx, cy))
            self.put(cx, cy, ch, col)
            stack += [(cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)]

    # ------------------------------------------------------------------ souris / clavier
    def mousePressEvent(self, e):
        self.setFocus()
        x, y = self.cell_at(e.position())
        tool = self.page.tool
        right = e.button() == Qt.RightButton
        if tool == "picker" or (e.modifiers() & Qt.AltModifier):
            if 0 <= x < self.cols and 0 <= y < self.rows:
                self.picked.emit(self.chars[y][x], self.colors[y][x])
            return
        if tool == "text":
            self.text_cursor = [x, y, x]
            self.update()
            return
        self.push_undo()
        if tool == "fill":
            self.flood(x, y)
        elif tool in ("pen", "eraser"):
            self.drag_start = (x, y)
            self._paint(x, y, erase=(tool == "eraser" or right))
        else:
            self.drag_start = (x, y)
            self.preview = {}
            self.shape_cells(tool, (x, y), (x, y), self.preview)
        self.update()

    def _paint(self, x, y, erase=False):
        size = int(self.page.brush_size.value())
        ch = " " if erase else self.page.brush_char()
        col = None if erase else self.page.brush_color()
        r = size - 1
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if dx * dx + dy * dy <= r * r + r:
                    self.put(x + dx, y + dy, ch, col)

    def mouseMoveEvent(self, e):
        x, y = self.cell_at(e.position())
        if (x, y) != self.hover:
            self.hover = (x, y)
            self.cursor_moved.emit(x, y)
        if self.drag_start and e.buttons():
            tool = self.page.tool
            if tool in ("pen", "eraser"):
                px, py = self.drag_start
                for cx, cy in _line_cells(px, py, x, y):
                    self._paint(cx, cy, erase=(tool == "eraser" or bool(e.buttons() & Qt.RightButton)))
                self.drag_start = (x, y)
            elif tool in ("line", "rect", "ellipse"):
                self.preview = {}
                self.shape_cells(tool, self.drag_start, (x, y), self.preview)
        self.update()

    def mouseReleaseEvent(self, e):
        if self.drag_start and self.page.tool in ("line", "rect", "ellipse"):
            for (x, y), (ch, col) in self.preview.items():
                self.put(x, y, ch, col)
        self.preview = {}
        self.drag_start = None
        self.update()
        self.page.changed()

    def leaveEvent(self, e):
        self.hover = None
        self.update()

    def keyPressEvent(self, e):
        if self.text_cursor is None or self.page.tool != "text":
            return super().keyPressEvent(e)
        x, y, x0 = self.text_cursor
        k = e.key()
        if k in (Qt.Key_Return, Qt.Key_Enter):
            self.text_cursor = [x0, y + 1, x0]
        elif k == Qt.Key_Backspace:
            if x > 0:
                self.push_undo()
                self.put(x - 1, y, " ", None)
                self.text_cursor = [x - 1, y, x0]
        elif k == Qt.Key_Left:
            self.text_cursor = [max(0, x - 1), y, x0]
        elif k == Qt.Key_Right:
            self.text_cursor = [min(self.cols - 1, x + 1), y, x0]
        elif k == Qt.Key_Up:
            self.text_cursor = [x, max(0, y - 1), x0]
        elif k == Qt.Key_Down:
            self.text_cursor = [x, min(self.rows - 1, y + 1), x0]
        elif k == Qt.Key_Escape:
            self.text_cursor = None
        elif e.text() and e.text().isprintable():
            self.push_undo()
            for c in e.text():
                self.put(x, y, c, self.page.brush_color())
                x += 1
            self.text_cursor = [min(x, self.cols - 1), y, x0]
        else:
            return super().keyPressEvent(e)
        self.update()
        self.page.changed()

    # ------------------------------------------------------------------ dessin
    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), self.bg)
        cw, ch = self.cw, self.ch
        if self.show_grid:
            p.setPen(QPen(self.grid_color, 1))
            for x in range(self.cols + 1):
                p.drawLine(QPointF(x * cw, 0), QPointF(x * cw, self.rows * ch))
            for y in range(self.rows + 1):
                p.drawLine(QPointF(0, y * ch), QPointF(self.cols * cw, y * ch))
        acc = QColor(self.page.win.settings.colors["accent"])
        if self.hover and 0 <= self.hover[0] < self.cols and 0 <= self.hover[1] < self.rows:
            a = QColor(acc)
            a.setAlpha(60)
            p.fillRect(QRectF(self.hover[0] * cw, self.hover[1] * ch, cw, ch), a)
        p.setFont(render.mono_font(self.family, self.px))
        p.setRenderHint(QPainter.TextAntialiasing)
        vis = self.visibleRegion().boundingRect()
        y0, y1 = max(0, int(vis.top() // ch)), min(self.rows, int(vis.bottom() // ch) + 1)
        x0, x1 = max(0, int(vis.left() // cw)), min(self.cols, int(vis.right() // cw) + 1)
        last = None
        for y in range(y0, y1):
            row, crow = self.chars[y], self.colors[y]
            for x in range(x0, x1):
                if (x, y) in self.preview:
                    c, col = self.preview[(x, y)]
                    qc = acc
                else:
                    c, col = row[x], crow[x]
                    qc = QColor(*col) if col else self.text_color
                if c == " ":
                    continue
                if qc != last:
                    p.setPen(qc)
                    last = qc
                p.drawText(QPointF(x * cw, y * ch + self.asc), c)
        if self.text_cursor and self.page.tool == "text":
            x, y, _ = self.text_cursor
            p.fillRect(QRectF(x * cw, y * ch + ch - 3, cw, 3), acc)
        p.end()


class EditorPage(Page):
    title = "Atelier"

    def __init__(self, win):
        super().__init__(win)
        self.tool = "pen"
        self._color = None
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        left = QVBoxLayout()
        left.setContentsMargins(22, 4, 18, 16)
        left.setSpacing(10)

        bar = QHBoxLayout()
        bar.setSpacing(2)
        self.tool_group = QButtonGroup(self)
        self.tool_btns = {}
        for key, ic, tip in TOOLS:
            b = QPushButton()
            b.setObjectName("tool")
            b.setCheckable(True)
            b.setToolTip(tip)
            b.setIconSize(QSize(20, 20))
            b.setCursor(Qt.PointingHandCursor)
            win.bind_icon(b, ic, "text")
            b.clicked.connect(lambda _=False, k=key: self.set_tool(k))
            self.tool_group.addButton(b)
            self.tool_btns[key] = b
            bar.addWidget(b)
        self.tool_btns["pen"].setChecked(True)
        bar.addSpacing(12)
        bar.addWidget(self.icon_btn("undo", "Annuler (Ctrl+Z)", lambda: (self.canvas.undo(), self.changed())))
        bar.addWidget(self.icon_btn("redo", "Rétablir (Ctrl+Y)", lambda: (self.canvas.redo(), self.changed())))
        bar.addWidget(self.icon_btn("trash", "Tout effacer", lambda: (self.canvas.clear(), self.changed())))
        bar.addStretch()
        self.pos_lbl = QLabel("")
        self.pos_lbl.setObjectName("stat")
        bar.addWidget(self.pos_lbl)
        bar.addWidget(self.icon_btn("zoom_out", "Dézoomer", lambda: self.canvas.set_zoom(self.canvas.px - 2)))
        bar.addWidget(self.icon_btn("zoom_in", "Zoomer", lambda: self.canvas.set_zoom(self.canvas.px + 2)))
        left.addLayout(bar)

        frame = QFrame()
        frame.setObjectName("viewer")
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(6, 6, 6, 6)
        self.scroll = QScrollArea()
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setAlignment(Qt.AlignCenter)
        self.canvas = EditorCanvas(self)
        self.canvas.cursor_moved.connect(lambda x, y: self.pos_lbl.setText(f"col {x + 1}  ·  ligne {y + 1}"))
        self.canvas.picked.connect(self._picked)
        self.scroll.setWidget(self.canvas)
        fl.addWidget(self.scroll)
        left.addWidget(frame, 1)
        h.addLayout(left, 1)

        # ---- panneau latéral
        side = QFrame()
        side.setObjectName("controls")
        sv = QVBoxLayout(side)
        sv.setContentsMargins(0, 0, 0, 0)
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setFixedWidth(300)
        sc.setFrameShape(QFrame.NoFrame)
        sc.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        body = QWidget()
        sc.setWidget(body)
        v = QVBoxLayout(body)
        v.setContentsMargins(14, 6, 14, 14)
        v.setSpacing(6)
        sv.addWidget(sc)
        h.addWidget(side)

        v.addWidget(section("Pinceau"))
        row = QHBoxLayout()
        self.char_edit = QLineEdit("#")
        self.char_edit.setMaxLength(1)
        self.char_edit.setFixedWidth(52)
        self.char_edit.setAlignment(Qt.AlignCenter)
        f = self.char_edit.font()
        f.setPointSize(f.pointSize() + 6)
        self.char_edit.setFont(f)
        row.addWidget(self.char_edit)
        from .widgets import LabeledSlider
        self.brush_size = LabeledSlider("Taille", 1, 6, 1)
        row.addWidget(self.brush_size, 1)
        v.addLayout(row)
        grid = QGridLayout()
        grid.setSpacing(4)
        self.char_group = QButtonGroup(self)
        for i, c in enumerate(PALETTE):
            b = QPushButton(c)
            b.setObjectName("charbtn")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, ch=c: self.char_edit.setText(ch))
            self.char_group.addButton(b)
            grid.addWidget(b, i // 7, i % 7)
        v.addLayout(grid)

        v.addWidget(section("Couleur"))
        crow = QHBoxLayout()
        self.use_color = QCheckBox("Colorer")
        crow.addWidget(self.use_color)
        self.color_btn = QPushButton()
        self.color_btn.setObjectName("swatch")
        self.color_btn.setFixedSize(46, 28)
        self.color_btn.setCursor(Qt.PointingHandCursor)
        self.color_btn.clicked.connect(self.pick_color)
        crow.addWidget(self.color_btn)
        crow.addStretch()
        v.addLayout(crow)

        v.addWidget(section("Formes"))
        self.smart_lines = QCheckBox("Lignes intelligentes  ( - / | \\ )")
        self.smart_lines.setChecked(True)
        v.addWidget(self.smart_lines)
        self.box = combo({k: v[0] for k, v in BOXES.items()}, "single")
        v.addWidget(self.box)
        self.fill_shapes = QCheckBox("Remplir les formes")
        v.addWidget(self.fill_shapes)

        v.addWidget(section("Toile"))
        srow = QHBoxLayout()
        self.cols_spin = QSpinBox()
        self.cols_spin.setRange(4, 600)
        self.cols_spin.setValue(80)
        self.cols_spin.setFixedWidth(72)
        self.rows_spin = QSpinBox()
        self.rows_spin.setRange(2, 400)
        self.rows_spin.setValue(30)
        self.rows_spin.setFixedWidth(72)
        srow.addWidget(self.cols_spin)
        srow.addWidget(QLabel("×"))
        srow.addWidget(self.rows_spin)
        ap = QPushButton("OK")
        ap.setObjectName("ghost")
        ap.clicked.connect(lambda: (self.canvas.resize_grid(self.cols_spin.value(), self.rows_spin.value()),
                                    self.changed()))
        srow.addWidget(ap)
        v.addLayout(srow)
        self.grid_chk = QCheckBox("Afficher la grille")
        self.grid_chk.setChecked(True)
        self.grid_chk.toggled.connect(lambda b: (setattr(self.canvas, "show_grid", b), self.canvas.update()))
        v.addWidget(self.grid_chk)
        tip = QLabel("Astuces : clic droit = gommer · Alt + clic = pipette · l'outil Texte se tape au clavier")
        tip.setObjectName("small")
        tip.setWordWrap(True)
        v.addSpacing(8)
        v.addWidget(tip)
        v.addStretch()

        for key, seq in (("pen", "P"), ("eraser", "E"), ("line", "L"), ("rect", "R"), ("ellipse", "O"),
                         ("fill", "F"), ("text", "T"), ("picker", "I")):
            sc_ = QShortcut(QKeySequence(seq), self)
            sc_.setContext(Qt.WidgetWithChildrenShortcut)
            sc_.activated.connect(lambda k=key: self.set_tool(k) if self.tool != "text" else None)
        for seq, fn in (("Ctrl+Z", self.canvas.undo), ("Ctrl+Y", self.canvas.redo), ("Ctrl+Shift+Z", self.canvas.redo)):
            s = QShortcut(QKeySequence(seq), self)
            s.setContext(Qt.WidgetWithChildrenShortcut)
            s.activated.connect(lambda f=fn: (f(), self.changed()))
        self._update_swatch()

    # ------------------------------------------------------------------
    def set_tool(self, key):
        self.tool = key
        self.tool_btns[key].setChecked(True)
        self.canvas.setCursor(Qt.IBeamCursor if key == "text" else Qt.CrossCursor)
        if key != "text":
            self.canvas.text_cursor = None
        self.canvas.update()

    def brush_char(self):
        return self.char_edit.text() or "#"

    def brush_color(self):
        if self.use_color.isChecked() and self._color:
            return self._color
        return None

    def pick_color(self):
        init = QColor(*self._color) if self._color else QColor(self.win.settings.colors["accent"])
        c = QColorDialog.getColor(init, self, "Couleur du pinceau")
        if c.isValid():
            self._color = (c.red(), c.green(), c.blue())
            self.use_color.setChecked(True)
            self._update_swatch()

    def _update_swatch(self):
        col = "#%02x%02x%02x" % self._color if self._color else self.win.settings.colors["accent"]
        if not self._color:
            c = QColor(col)
            self._color = (c.red(), c.green(), c.blue())
        self.color_btn.setStyleSheet(f"background:{col};")

    def _picked(self, ch, col):
        if ch.strip():
            self.char_edit.setText(ch)
        if col:
            self._color = col
            self.use_color.setChecked(True)
            self._update_swatch()

    def load_layers(self, lines, fg=None):
        self.canvas.load(lines, fg)
        self.cols_spin.setValue(self.canvas.cols)
        self.rows_spin.setValue(self.canvas.rows)
        self.changed()

    def changed(self):
        self.win.update_stats()

    def current_art(self):
        return AsciiArt(self.canvas.lines())

    def current_layers(self):
        return self.canvas.lines(), self.canvas.fg_array(), None

    def apply_theme(self):
        family, fg, bg = self.win.view_style()
        cv = self.canvas
        cv.family = family
        cv.text_color = QColor(fg)
        cv.bg = QColor(bg or self.win.settings.colors["bg"])
        g = QColor(fg)
        g.setAlpha(22)
        cv.grid_color = g
        cv._metrics()
