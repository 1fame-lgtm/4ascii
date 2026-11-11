"""Fenêtre principale de 4scii : barre latérale, pages, barre d'export (même structure que 4tafy)."""
import time
from pathlib import Path

import numpy as np
from PySide6.QtCore import QEvent, QMimeData, QPointF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QKeySequence, QPainter, QShortcut
from PySide6.QtWidgets import (QApplication, QButtonGroup, QFileDialog, QFrame, QHBoxLayout, QInputDialog, QLabel,
                               QMainWindow, QMenu, QPushButton, QStackedWidget, QVBoxLayout, QWidget)

from . import icons, render
from .chrome import DragArea, TrafficLights, WindowBackground, WindowOutline
from .config import EXPORT_DIR, Settings, ensure_dirs
from .page_editor import EditorPage
from .page_gallery import GalleryPage, save_item
from .page_image import ImagePage
from .page_live import LivePage
from .page_settings import SettingsPage
from .page_text import TextPage
from .themes import build_qss, on_color


class AsciiPlasma(QWidget):
    """Petit plasma ASCII animé en bas de la barre latérale (pour le style)."""
    CHARS = " .:-=+*#%@"

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.t = 0.0
        self.setFixedHeight(96)
        self.timer = QTimer(self, interval=90, timeout=self._tick)
        self.timer.start()

    def _tick(self):
        if self.isVisible() and self.window().isActiveWindow():
            self.t += 0.12
            self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.TextAntialiasing)
        font = render.mono_font("Consolas", 11)
        p.setFont(font)
        cw, ch, asc = render.cell_size("Consolas", 11)
        cols, rows = int(self.width() // cw), int(self.height() // ch)
        if cols <= 0 or rows <= 0:
            return
        y, x = np.mgrid[0:rows, 0:cols].astype(np.float32)
        t = self.t
        v = (np.sin(x / 3.1 + t) + np.sin(y / 1.7 - t * 1.3) + np.sin((x + y * 2) / 5.0 + t * 0.7)
             + np.sin(np.sqrt((x - cols / 2) ** 2 + (y * 2 - rows) ** 2) / 2.2 - t * 1.6))
        v = (v + 4) / 8
        c = self.win.settings.colors
        a, b = QColor(c["accent"]), QColor(self.win.settings["color2"])
        n = len(self.CHARS) - 1
        for j in range(rows):
            for i in range(cols):
                k = float(v[j, i])
                ch_ = self.CHARS[min(n, int(k * k * n * 1.25))]
                if ch_ == " ":
                    continue
                col = QColor(int(a.red() + (b.red() - a.red()) * k), int(a.green() + (b.green() - a.green()) * k),
                             int(a.blue() + (b.blue() - a.blue()) * k), int(70 + 150 * k))
                p.setPen(col)
                p.drawText(QPointF(i * cw, j * ch + asc), ch_)
        p.end()


class MainWindow(QMainWindow):
    NAV = [
        ("Créer", [("image", "Image", "image"), ("text", "Texte", "text"), ("live", "Webcam", "camera"),
                   ("editor", "Atelier", "pencil")]),
        ("Bibliothèque", [("gallery", "Galerie", "gallery")]),
        ("Outils", [("settings", "Personnaliser", "brush")]),
    ]

    def __init__(self):
        super().__init__()
        ensure_dirs()
        self.settings = Settings()
        self._icon_bindings = []
        self.current = None

        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle("4scii")
        self.resize(1440, 900)
        self.setMinimumSize(1080, 680)
        self.setAcceptDrops(True)

        self.bg = WindowBackground(self.settings)
        self.setCentralWidget(self.bg)
        root = QVBoxLayout(self.bg)
        root.setSpacing(0)
        top = QHBoxLayout()
        top.setSpacing(0)
        top.addWidget(self._build_sidebar())
        self.main_panel = QFrame()
        self.main_panel.setObjectName("content")
        ml = QVBoxLayout(self.main_panel)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(0)
        ml.addWidget(self._build_toolbar())
        self.stack = QStackedWidget()
        ml.addWidget(self.stack, 1)
        top.addWidget(self.main_panel, 1)
        root.addLayout(top, 1)
        root.addWidget(self._build_export_bar())
        self.outline = WindowOutline(self.bg)

        self.image_page = ImagePage(self)
        self.text_page = TextPage(self)
        self.live_page = LivePage(self)
        self.editor_page = EditorPage(self)
        self.gallery_page = GalleryPage(self)
        self.settings_page = SettingsPage(self)
        self.pages = {"image": self.image_page, "text": self.text_page, "live": self.live_page,
                      "editor": self.editor_page, "gallery": self.gallery_page, "settings": self.settings_page}
        for p in self.pages.values():
            self.stack.addWidget(p)

        self.toast_lbl = QLabel(self.bg)
        self.toast_lbl.hide()
        self._toast_timer = QTimer(self, singleShot=True, interval=2600, timeout=self.toast_lbl.hide)
        self._theme_timer = QTimer(self, singleShot=True, interval=60, timeout=self.apply_theme)

        self._shortcuts()
        self.apply_theme()
        self.show_page("image")

    # ================================================================ construction
    def bind_icon(self, button, name, color_key="subtext", size=None, refresh=False):
        self._icon_bindings = [b for b in self._icon_bindings if b[0] is not button] if refresh else self._icon_bindings
        self._icon_bindings.append((button, name, color_key))
        if size:
            button.setIconSize(QSize(size, size))
        if refresh:
            button.setIcon(icons.icon(name, self._color(color_key)))

    def _color(self, key):
        c = self.settings.colors
        return on_color(c["accent"]) if key == "on_accent" else c[key]

    def _build_sidebar(self):
        side = QFrame()
        side.setObjectName("side")
        side.setFixedWidth(232)
        v = QVBoxLayout(side)
        v.setContentsMargins(10, 0, 10, 10)
        v.setSpacing(1)
        head = DragArea()
        head.setFixedHeight(52)
        hl = QHBoxLayout(head)
        hl.setContentsMargins(8, 0, 4, 0)
        self.lights = TrafficLights()
        hl.addWidget(self.lights)
        hl.addStretch()
        self.logo_icon = QLabel()
        self.logo_icon.setFixedSize(28, 28)
        hl.addWidget(self.logo_icon)
        self.logo_text = QLabel("4scii")
        self.logo_text.setObjectName("logo")
        self.logo_text.setTextFormat(Qt.RichText)
        hl.addWidget(self.logo_text)
        v.addWidget(head)
        v.addSpacing(8)

        self.nav_group = QButtonGroup(self)
        self.nav_btns = {}
        n = 1
        for section, keys in self.NAV:
            t = QLabel(section)
            t.setObjectName("section")
            t.setContentsMargins(10, 6, 0, 4)
            v.addWidget(t)
            for key, text, ic in keys:
                b = QPushButton(f"  {text}")
                b.setObjectName("nav")
                b.setCheckable(True)
                b.setIconSize(QSize(18, 18))
                b.setToolTip(f"{text}  (Ctrl+{n})")
                b.clicked.connect(lambda _=False, k=key: self.show_page(k))
                self.bind_icon(b, ic, "accent")
                self.nav_group.addButton(b)
                self.nav_btns[key] = b
                v.addWidget(b)
                n += 1
            v.addSpacing(12)
        v.addStretch()
        self.plasma = AsciiPlasma(self)
        v.addWidget(self.plasma)
        ver = QLabel("4scii · moteur 4SHAPE")
        ver.setObjectName("small")
        ver.setContentsMargins(10, 4, 0, 0)
        v.addWidget(ver)
        return side

    def _build_toolbar(self):
        bar = DragArea()
        bar.setFixedHeight(52)
        h = QHBoxLayout(bar)
        h.setContentsMargins(22, 0, 16, 0)
        self.toolbar_title = QLabel("")
        self.toolbar_title.setObjectName("toolbartitle")
        h.addWidget(self.toolbar_title)
        h.addStretch()
        hint = QLabel("Ctrl+Maj+C copier  ·  Ctrl+S galerie  ·  Ctrl+E Atelier")
        hint.setObjectName("small")
        h.addWidget(hint)
        return bar

    def _build_export_bar(self):
        bar = QFrame()
        bar.setObjectName("bar")
        bar.setFixedHeight(64)
        h = QHBoxLayout(bar)
        h.setContentsMargins(18, 8, 18, 8)
        h.setSpacing(6)
        left = QVBoxLayout()
        left.setSpacing(0)
        self.stat_main = QLabel("—")
        self.stat_main.setObjectName("nowtitle")
        self.stat_sub = QLabel("")
        self.stat_sub.setObjectName("stat")
        left.addStretch()
        left.addWidget(self.stat_main)
        left.addWidget(self.stat_sub)
        left.addStretch()
        lw = QWidget()
        lw.setFixedWidth(300)
        lw.setLayout(left)
        h.addWidget(lw)
        h.addStretch()

        def btn(text, ic, tip, slot, obj="export"):
            b = QPushButton(f"  {text}" if text else "")
            b.setObjectName(obj)
            b.setToolTip(tip)
            b.setCursor(Qt.PointingHandCursor)
            b.setIconSize(QSize(16, 16))
            self.bind_icon(b, ic, "on_accent" if obj == "accent" else "text")
            b.clicked.connect(slot)
            h.addWidget(b)
            return b

        btn("Copier", "copy", "Copier le texte (et la version colorée pour Word / mails)", self.copy_art, "accent")
        btn("TXT", "save", "Enregistrer en texte brut", lambda: self.export("txt"))
        btn("HTML", "save", "Page web avec les couleurs", lambda: self.export("html"))
        btn("PNG", "image", "Image PNG", lambda: self.export("png"))
        btn("SVG", "save", "Image vectorielle SVG", lambda: self.export("svg"))
        btn("ANSI", "save", "Texte coloré pour terminal (.ans)", lambda: self.export("ans"))
        h.addStretch()
        btn("Atelier", "pencil", "Retoucher dans l'Atelier (Ctrl+E)", self.send_to_editor)
        btn("Galerie", "star", "Ajouter à la galerie (Ctrl+S)", self.save_to_gallery)
        return bar

    def _shortcuts(self):
        for i, key in enumerate(self.pages, start=1):
            QShortcut(QKeySequence(f"Ctrl+{i}"), self, activated=lambda k=key: self.show_page(k))
        QShortcut(QKeySequence("Ctrl+O"), self, activated=lambda: (self.show_page("image"), self.image_page.open_file()))
        QShortcut(QKeySequence("Ctrl+Shift+C"), self, activated=self.copy_art)
        QShortcut(QKeySequence("Ctrl+S"), self, activated=self.save_to_gallery)
        QShortcut(QKeySequence("Ctrl+E"), self, activated=self.send_to_editor)
        paste = QShortcut(QKeySequence("Ctrl+V"), self.image_page, activated=self.image_page.paste)
        paste.setContext(Qt.WidgetWithChildrenShortcut)

    # ================================================================ navigation
    def show_page(self, key):
        page = self.pages[key]
        if self.current is not None and self.current is not page:
            self.current.deactivate()
        self.current = page
        self.stack.setCurrentWidget(page)
        self.nav_btns[key].setChecked(True)
        self.toolbar_title.setText(page.title)
        page.activate()
        self.update_stats()

    # ================================================================ thème
    def schedule_theme(self):
        self._theme_timer.start()

    def view_style(self):
        s = self.settings
        mode = s["preview_bg"]
        if mode == "black":
            return s["ascii_font"], "#f2f2f2", "#000000"
        if mode == "white":
            return s["ascii_font"], "#111111", "#ffffff"
        return s["ascii_font"], s.colors["text"], None

    def current_icon(self):
        return icons.app_icon(self.settings.colors["accent"], self.settings["color2"])

    def apply_theme(self):
        s = self.settings
        app = QApplication.instance()
        app.setFont(QFont(s["font_family"], s["font_size"]))
        app.setStyleSheet(build_qss(s, self.isMaximized()))
        for btn, name, key in self._icon_bindings:
            btn.setIcon(icons.icon(name, self._color(key)))
        ic = self.current_icon()
        self.setWindowIcon(ic)
        app.setWindowIcon(ic)
        self.logo_icon.setPixmap(ic.pixmap(QSize(28, 28), self.devicePixelRatioF()))
        self.logo_text.setText(f'<span style="color:{s.colors["accent"]}">4</span>scii')
        c = s.colors
        self.toast_lbl.setStyleSheet(
            f"background:{c['text']}; color:{c['bg']}; border-radius:10px; padding:10px 18px; font-weight:700;")
        self.bg.set_maximized(self.isMaximized())
        self._place_outline()
        for p in self.pages.values():
            p.apply_theme()
        s.save()
        self.update_stats()

    # ================================================================ export
    def _layers(self):
        page = self.current
        L = page.current_layers() if page else None
        if not L or not any(l.strip() for l in L[0]):
            self.toast("Rien à exporter sur cette page")
            return None
        return L

    def update_stats(self):
        page = self.current
        if page is None:
            return
        L = page.current_layers()
        art = page.current_art()
        if not L:
            self.stat_main.setText("—")
            self.stat_sub.setText("Aucune création sur cette page")
            return
        lines = L[0]
        cols = max((len(l) for l in lines), default=0)
        n = sum(len(l) - l.count(" ") for l in lines)
        self.stat_main.setText(f"{cols} × {len(lines)} caractères")
        extra = f"  ·  {art.elapsed * 1000:.0f} ms" if art is not None and art.elapsed else ""
        self.stat_sub.setText(f"{n} visibles{extra}")

    def copy_art(self):
        L = self._layers()
        if not L:
            return
        lines, fg, bg = L
        family, tfg, tbg = self.view_style()
        md = QMimeData()
        md.setText(render.to_txt(lines))
        md.setHtml(f'<pre style="font-family:{family},monospace;line-height:1.1;color:{tfg};'
                   f'background:{tbg or self.settings.colors["bg"]}">{render.html_pre(lines, fg, bg)}</pre>')
        QApplication.clipboard().setMimeData(md)
        self.toast("Copié dans le presse-papiers !")

    def save_text_file(self, content, default_name, filt):
        ensure_dirs()
        path, _ = QFileDialog.getSaveFileName(self, "Enregistrer", str(EXPORT_DIR / default_name), filt)
        if not path:
            return None
        Path(path).write_text(content, encoding="utf-8", newline="\n")
        self.toast(f"Enregistré : {Path(path).name}")
        return path

    def export(self, kind):
        L = self._layers()
        if not L:
            return
        lines, fg, bg = L
        family, tfg, tbg = self.view_style()
        back = tbg or self.settings.colors["bg"]
        name = "4scii-" + time.strftime("%Y%m%d-%H%M%S")
        if kind == "txt":
            self.save_text_file(render.to_txt(lines), name + ".txt", "Texte (*.txt)")
        elif kind == "html":
            self.save_text_file(render.to_html(lines, fg, bg, family, tfg, back), name + ".html", "Page web (*.html)")
        elif kind == "ans":
            self.save_text_file(render.to_ansi(lines, fg, bg), name + ".ans", "ANSI (*.ans *.txt)")
        elif kind == "svg":
            self.save_text_file(render.to_svg(lines, fg, bg, family, tfg, back), name + ".svg", "SVG (*.svg)")
        elif kind == "png":
            ensure_dirs()
            path, _ = QFileDialog.getSaveFileName(self, "Enregistrer l'image", str(EXPORT_DIR / (name + ".png")),
                                                  "Image PNG (*.png)")
            if not path:
                return
            size, ok = QInputDialog.getInt(self, "Taille du texte", "Taille d'un caractère (px) :", 16, 4, 64)
            if not ok:
                return
            img = render.render_image(lines, fg, bg, family, size, tfg, back, padding=size)
            if img.save(path):
                self.toast(f"Image enregistrée : {Path(path).name}  ({img.width()}×{img.height()})")
            else:
                self.toast("Impossible d'enregistrer l'image")

    def send_to_editor(self):
        if self.current is self.editor_page:
            return
        L = self._layers()
        if not L:
            return
        lines, fg, bg = L
        if bg is not None:  # demi-blocs couleur : l'Atelier ne gère que la couleur du caractère
            fg = None
        self.editor_page.load_layers(lines, fg)
        self.show_page("editor")
        self.toast("Envoyé dans l'Atelier")

    def save_to_gallery(self):
        L = self._layers()
        if not L:
            return
        name, ok = QInputDialog.getText(self, "Ajouter à la galerie", "Nom de la création :",
                                        text=f"{self.current.title} — {time.strftime('%H:%M')}")
        if not ok:
            return
        save_item(name.strip() or "Sans titre", *L)
        self.toast("Ajouté à la galerie ★")

    # ================================================================ divers
    def toast(self, msg):
        self.toast_lbl.setText(msg if len(msg) < 140 else msg[:137] + "…")
        self.toast_lbl.adjustSize()
        w = min(self.toast_lbl.width(), self.bg.width() - 40)
        self.toast_lbl.resize(w, self.toast_lbl.height())
        self.toast_lbl.move((self.bg.width() - w) // 2, self.bg.height() - self.bg.margin - 64 - 20 - self.toast_lbl.height())
        self.toast_lbl.show()
        self.toast_lbl.raise_()
        self._toast_timer.start()

    def new_menu(self, title=""):
        m = QMenu(title, self)
        m.setWindowFlags(m.windowFlags() | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        m.setAttribute(Qt.WA_TranslucentBackground)
        return m

    def _place_outline(self):
        self.outline.setGeometry(self.bg.rect())
        self.outline.raise_()
        self.toast_lbl.raise_()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._place_outline()

    def changeEvent(self, e):
        if e.type() == QEvent.WindowStateChange:
            self.bg.set_maximized(self.isMaximized())
            QApplication.instance().setStyleSheet(build_qss(self.settings, self.isMaximized()))
            self._place_outline()
        super().changeEvent(e)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls() or e.mimeData().hasImage():
            e.acceptProposedAction()

    def dropEvent(self, e):
        self.show_page("image")
        self.image_page.dropEvent(e)

    def closeEvent(self, e):
        self.live_page.stop()
        self.settings.save()
        super().closeEvent(e)
