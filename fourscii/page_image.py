"""Page Image → ASCII : fichiers, presse-papiers, capture d'écran, GIF animés."""
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QGuiApplication, QImage, QImageReader, QMovie
from PySide6.QtWidgets import (QApplication, QFileDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QStackedWidget,
                               QVBoxLayout)

from . import engine, icons, render
from .config import IMAGE_FILTER
from .controls import ControlPanel
from .page_base import Page

MAX_FRAMES = 400


class ImagePage(Page):
    title = "Image → ASCII"
    color_key = "image_color"

    def __init__(self, win):
        super().__init__(win)
        self.source = None
        self.frames = []          # [(QImage, délai ms)] pour les GIF animés
        self.frame_i = 0
        self.cache = {}
        self.source_name = ""
        self.setAcceptDrops(True)

        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        left = QVBoxLayout()
        left.setContentsMargins(22, 4, 18, 16)
        left.setSpacing(10)

        # barre d'actions
        bar = QHBoxLayout()
        bar.setSpacing(6)
        bar.addWidget(self.icon_btn("folder", "Ouvrir une image (Ctrl+O)", self.open_file, text="  Ouvrir"))
        bar.addWidget(self.icon_btn("clipboard", "Coller une image (Ctrl+V)", self.paste, text="  Coller"))
        bar.addWidget(self.icon_btn("screen", "Capturer l'écran", self.capture_screen, text="  Capture"))
        bar.addSpacing(8)
        self.play_btn = self.icon_btn("pause", "Lecture / pause de l'animation", self.toggle_play)
        self.prev_btn = self.icon_btn("chevron_left", "Image précédente", lambda: self.step(-1))
        self.next_btn = self.icon_btn("chevron_right", "Image suivante", lambda: self.step(1))
        self.frame_lbl = QLabel("")
        self.frame_lbl.setObjectName("stat")
        self.anim_btn = self.icon_btn("save", "Exporter l'animation en page HTML", self.export_animation,
                                      text="  Animation HTML")
        for w in (self.prev_btn, self.play_btn, self.next_btn, self.frame_lbl, self.anim_btn):
            bar.addWidget(w)
        bar.addStretch()
        self.name_lbl = QLabel("")
        self.name_lbl.setObjectName("sub")
        bar.addWidget(self.name_lbl)
        frame, self.viewer = self.make_viewer()
        bar.addLayout(self.zoom_row(self.viewer))
        left.addLayout(bar)

        # zone vide (glisser-déposer) / visionneuse
        self.stack = QStackedWidget()
        self.drop = QFrame()
        self.drop.setObjectName("drop")
        dv = QVBoxLayout(self.drop)
        dv.addStretch()
        self.drop_icon = QLabel()
        self.drop_icon.setAlignment(Qt.AlignCenter)
        dv.addWidget(self.drop_icon)
        t = QLabel("Glisse une image ici")
        t.setObjectName("h2")
        t.setAlignment(Qt.AlignCenter)
        dv.addWidget(t)
        s = QLabel("PNG, JPG, WEBP, BMP, GIF animé…  ou colle-la avec Ctrl+V")
        s.setObjectName("sub")
        s.setAlignment(Qt.AlignCenter)
        dv.addWidget(s)
        row = QHBoxLayout()
        row.addStretch()
        b = QPushButton("Ouvrir une image")
        b.setObjectName("accent")
        b.setCursor(Qt.PointingHandCursor)
        b.clicked.connect(self.open_file)
        row.addWidget(b)
        demo = QPushButton("Essayer avec une démo")
        demo.setObjectName("ghost")
        demo.setCursor(Qt.PointingHandCursor)
        demo.clicked.connect(self.load_demo)
        row.addWidget(demo)
        row.addStretch()
        dv.addSpacing(10)
        dv.addLayout(row)
        dv.addStretch()
        self.stack.addWidget(self.drop)
        self.stack.addWidget(frame)
        left.addWidget(self.stack, 1)
        h.addLayout(left, 1)

        side = QFrame()
        side.setObjectName("controls")
        sv = QVBoxLayout(side)
        sv.setContentsMargins(0, 0, 0, 0)
        self.panel = ControlPanel(win.settings["image_params"], win.settings["image_color"])
        self.panel.set_font(win.settings["ascii_font"])
        self.panel.changed.connect(self.reconvert)
        self.panel.color_changed.connect(self.refresh_view)
        sv.addWidget(self.panel)
        h.addWidget(side)

        self.timer = QTimer(self, singleShot=True, timeout=self._next_frame)
        self.playing = True
        self._anim_widgets(False)

    # ------------------------------------------------------------------ chargement
    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Ouvrir une image", str(Path.home() / "Pictures"), IMAGE_FILTER)
        if path:
            self.load_path(path)

    def load_path(self, path):
        path = str(path)
        frames = []
        if path.lower().endswith((".gif", ".webp")):
            mv = QMovie(path)
            if mv.isValid() and mv.frameCount() != 1:
                mv.jumpToFrame(0)
                while len(frames) < MAX_FRAMES:
                    img = mv.currentImage()
                    if img.isNull():
                        break
                    frames.append((img.copy(), mv.nextFrameDelay() or 80))
                    if not mv.jumpToNextFrame() or mv.currentFrameNumber() == 0:
                        break
        if len(frames) > 1:
            self.set_frames(frames, Path(path).name)
            return
        reader = QImageReader(path)
        reader.setAutoTransform(True)
        img = reader.read()
        if img.isNull():
            self.win.toast("Impossible de lire cette image")
            return
        self.set_image(img, Path(path).name)

    def set_image(self, img, name=""):
        self.timer.stop()
        self.frames = []
        self.source = img
        self.source_name = name
        self._anim_widgets(False)
        self.reconvert()

    def set_frames(self, frames, name=""):
        self.frames = frames
        self.frame_i = 0
        self.source = frames[0][0]
        self.source_name = name
        self.playing = True
        self._anim_widgets(True)
        self.reconvert()

    def paste(self):
        cb = QApplication.clipboard()
        md = cb.mimeData()
        if md.hasImage():
            img = cb.image()
            if not img.isNull():
                self.set_image(img, "Presse-papiers")
                return
        if md.hasUrls():
            for u in md.urls():
                if u.isLocalFile():
                    self.load_path(u.toLocalFile())
                    return
        text = cb.text().strip().strip('"')
        if text and Path(text).is_file():
            self.load_path(text)
            return
        self.win.toast("Rien d'utilisable dans le presse-papiers")

    def capture_screen(self):
        self.win.hide()
        QTimer.singleShot(450, self._grab)

    def _grab(self):
        screen = QGuiApplication.primaryScreen()
        pm = screen.grabWindow(0)
        self.win.show()
        self.win.raise_()
        if not pm.isNull():
            self.set_image(pm.toImage(), "Capture d'écran")

    def load_demo(self):
        from .demo import demo_image
        self.set_image(demo_image(), "Démo")

    # ------------------------------------------------------------------ animation
    def _anim_widgets(self, on):
        for w in (self.prev_btn, self.play_btn, self.next_btn, self.frame_lbl, self.anim_btn):
            w.setVisible(on)

    def toggle_play(self):
        self.playing = not self.playing
        self.win.bind_icon(self.play_btn, "pause" if self.playing else "play", "text", refresh=True)
        if self.playing:
            self._schedule()
        else:
            self.timer.stop()

    def step(self, d):
        if not self.frames:
            return
        self.frame_i = (self.frame_i + d) % len(self.frames)
        self.source = self.frames[self.frame_i][0]
        self._show_frame()

    def _schedule(self):
        if self.frames and self.playing and self.isVisible():
            self.timer.start(max(20, self.frames[self.frame_i][1]))

    def _next_frame(self):
        self.step(1)
        self._schedule()

    def _show_frame(self):
        key = self.frame_i
        if key not in self.cache:
            self.cache[key] = engine.convert(self.source, self.panel.params())
        self.art = self.cache[key]
        self.frame_lbl.setText(f"{self.frame_i + 1}/{len(self.frames)}")
        self.refresh_view()

    def export_animation(self):
        if not self.frames:
            return
        self.timer.stop()
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            P = self.panel.params()
            c = self.win.settings.colors
            out = []
            for i, (img, _) in enumerate(self.frames):
                art = self.cache.get(i) or engine.convert(img, P)
                self.cache[i] = art
                out.append(render.layers(art, self.color_mode(), c["accent"], self.win.settings["color2"]))
            family, fg, bg = self.win.view_style()
            html = render.to_animated_html(out, [d for _, d in self.frames], family, fg, bg or c["bg"])
        finally:
            QApplication.restoreOverrideCursor()
        self.win.save_text_file(html, "animation.html", "Page web (*.html)")
        self._schedule()

    # ------------------------------------------------------------------ conversion
    def reconvert(self):
        P = self.panel.params()
        self.win.settings["image_params"] = {k: v for k, v in P.items() if k != "font"}
        self.cache = {}
        if self.source is None:
            self.stack.setCurrentIndex(0)
            return
        self.stack.setCurrentIndex(1)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            if self.frames:
                self._show_frame()
                self._schedule()
            else:
                self.art = engine.convert(self.source, P)
                self.refresh_view()
        finally:
            QApplication.restoreOverrideCursor()
        self.name_lbl.setText(f"{self.source_name}  ·  {self.source.width()}×{self.source.height()}")

    def color_mode(self):
        return self.panel.color_mode

    def refresh_view(self):
        self.win.settings["image_color"] = self.panel.color_mode
        L = self.current_layers()
        if L:
            self.viewer.set_layers(*L)
        self.win.update_stats()

    def apply_theme(self):
        self.style_viewer(self.viewer)
        self.panel.apply_theme(self.win.settings.colors["text"])
        self.drop_icon.setPixmap(icons.icon("image", self.win.settings.colors["accent"], 128)
                                 .pixmap(QSize(64, 64), self.devicePixelRatioF()))
        if self.panel.P["font"] != self.win.settings["ascii_font"]:
            self.panel.set_font(self.win.settings["ascii_font"])
        elif self.art is not None:
            self.refresh_view()

    def activate(self):
        self._schedule()

    def deactivate(self):
        self.timer.stop()

    # ------------------------------------------------------------------ glisser-déposer
    def dragEnterEvent(self, e):
        md = e.mimeData()
        if md.hasUrls() or md.hasImage():
            e.acceptProposedAction()
            self.drop.setProperty("hot", True)
            self.drop.style().polish(self.drop)

    def dragLeaveEvent(self, e):
        self.drop.setProperty("hot", False)
        self.drop.style().polish(self.drop)

    def dropEvent(self, e):
        self.dragLeaveEvent(e)
        md = e.mimeData()
        for u in md.urls():
            if u.isLocalFile():
                self.load_path(u.toLocalFile())
                return
        if md.hasImage():
            img = QImage(md.imageData())
            if not img.isNull():
                self.set_image(img, "Image déposée")
