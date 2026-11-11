"""Page Webcam : ASCII en direct depuis la caméra."""
import time

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtWidgets import QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton, QStackedWidget, QVBoxLayout

from . import engine, icons
from .controls import ControlPanel
from .page_base import Page

try:
    from PySide6.QtMultimedia import QCamera, QMediaCaptureSession, QMediaDevices, QVideoSink
    HAVE_MM = True
except Exception:  # Qt Multimedia absent
    HAVE_MM = False


class LivePage(Page):
    title = "Webcam en direct"
    color_key = "live_color"

    def __init__(self, win):
        super().__init__(win)
        self.camera = None
        self.session = None
        self.sink = None
        self.frame = None
        self.new_frame = False
        self.frozen = False
        self._fps_t = time.perf_counter()
        self._fps_n = 0

        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        left = QVBoxLayout()
        left.setContentsMargins(22, 4, 18, 16)
        left.setSpacing(10)
        bar = QHBoxLayout()
        bar.setSpacing(6)
        self.devices = QComboBox()
        self.devices.setMinimumWidth(220)
        bar.addWidget(self.devices)
        self.start_btn = QPushButton("Démarrer")
        self.start_btn.setObjectName("accent")
        self.start_btn.setCursor(Qt.PointingHandCursor)
        self.start_btn.clicked.connect(self.toggle)
        bar.addWidget(self.start_btn)
        self.mirror = QCheckBox("Miroir")
        self.mirror.setChecked(True)
        bar.addWidget(self.mirror)
        bar.addWidget(self.icon_btn("snapshot", "Figer / reprendre l'image", self.freeze, text="  Figer"))
        bar.addWidget(self.icon_btn("image", "Envoyer l'image figée vers la page Image", self.to_image_page,
                                    text="  Vers Image"))
        bar.addStretch()
        self.fps = QLabel("")
        self.fps.setObjectName("stat")
        bar.addWidget(self.fps)
        frame, self.viewer = self.make_viewer()
        bar.addLayout(self.zoom_row(self.viewer))
        left.addLayout(bar)

        self.stack = QStackedWidget()
        self.empty = QFrame()
        self.empty.setObjectName("drop")
        ev = QVBoxLayout(self.empty)
        ev.addStretch()
        self.empty_icon = QLabel()
        self.empty_icon.setAlignment(Qt.AlignCenter)
        ev.addWidget(self.empty_icon)
        self.empty_title = QLabel("Ta webcam en ASCII, en direct")
        self.empty_title.setObjectName("h2")
        self.empty_title.setAlignment(Qt.AlignCenter)
        ev.addWidget(self.empty_title)
        self.empty_sub = QLabel("Choisis une caméra puis clique sur Démarrer")
        self.empty_sub.setObjectName("sub")
        self.empty_sub.setAlignment(Qt.AlignCenter)
        ev.addWidget(self.empty_sub)
        ev.addStretch()
        self.stack.addWidget(self.empty)
        self.stack.addWidget(frame)
        left.addWidget(self.stack, 1)
        h.addLayout(left, 1)

        side = QFrame()
        side.setObjectName("controls")
        sv = QVBoxLayout(side)
        sv.setContentsMargins(0, 0, 0, 0)
        P = dict(dict(cols=110, mode="density", charset="4scii équilibré", dither="none"), **win.settings["live_params"])
        self.panel = ControlPanel(P, win.settings["live_color"], max_cols=220, live=True)
        self.panel.set_font(win.settings["ascii_font"])
        self.panel.changed.connect(self._save_params)
        self.panel.color_changed.connect(self._save_params)
        sv.addWidget(self.panel)
        h.addWidget(side)

        self.tick = QTimer(self, interval=55, timeout=self._render)
        self.refresh_devices()
        if not HAVE_MM:
            self.start_btn.setEnabled(False)
            self.empty_sub.setText("Qt Multimedia n'est pas disponible dans cette installation de PySide6")

    def refresh_devices(self):
        self.devices.clear()
        if not HAVE_MM:
            return
        for d in QMediaDevices.videoInputs():
            self.devices.addItem(d.description(), d)
        if self.devices.count() == 0:
            self.devices.addItem("Aucune caméra détectée", None)
            self.start_btn.setEnabled(False)

    # ------------------------------------------------------------------ caméra
    def toggle(self):
        if self.camera:
            self.stop()
        else:
            self.start()

    def start(self):
        dev = self.devices.currentData()
        if dev is None:
            return
        self.camera = QCamera(dev)
        self.session = QMediaCaptureSession()
        self.sink = QVideoSink()
        self.session.setCamera(self.camera)
        self.session.setVideoSink(self.sink)
        self.sink.videoFrameChanged.connect(self._on_frame)
        self.camera.errorOccurred.connect(lambda *_: self.win.toast("Erreur caméra : " + self.camera.errorString()))
        self.camera.start()
        self.frozen = False
        self.start_btn.setText("Arrêter")
        self.stack.setCurrentIndex(1)
        self.tick.start()

    def stop(self):
        self.tick.stop()
        if self.camera:
            self.camera.stop()
            self.camera.deleteLater()
        self.camera = self.session = self.sink = None
        self.start_btn.setText("Démarrer")
        self.fps.setText("")

    def _on_frame(self, vf):
        if self.frozen:
            return
        img = vf.toImage()
        if not img.isNull():
            self.frame = img
            self.new_frame = True

    def _render(self):
        if not self.new_frame or self.frame is None:
            return
        self.new_frame = False
        img = self.frame.mirrored(True, False) if self.mirror.isChecked() else self.frame
        if img.width() > 640:  # la conversion n'a pas besoin de la pleine résolution
            img = img.scaledToWidth(640, Qt.FastTransformation)
        self.art = engine.convert(img, self.panel.params())
        self.refresh_view()
        self._fps_n += 1
        now = time.perf_counter()
        if now - self._fps_t >= 1:
            self.fps.setText(f"{self._fps_n / (now - self._fps_t):.0f} img/s")
            self._fps_t, self._fps_n = now, 0

    def freeze(self):
        self.frozen = not self.frozen
        self.win.toast("Image figée" if self.frozen else "Reprise du direct")

    def to_image_page(self):
        if self.frame is None:
            self.win.toast("Démarre la caméra d'abord")
            return
        img = self.frame.mirrored(True, False) if self.mirror.isChecked() else self.frame
        self.win.image_page.set_image(img.copy(), "Webcam")
        self.win.show_page("image")

    # ------------------------------------------------------------------
    def _save_params(self):
        self.win.settings["live_params"] = {k: v for k, v in self.panel.params().items() if k != "font"}
        self.win.settings["live_color"] = self.panel.color_mode
        if self.frame is not None:
            self.new_frame = True
            if self.frozen or not self.camera:
                self._render()

    def color_mode(self):
        return self.panel.color_mode

    def refresh_view(self):
        L = self.current_layers()
        if L:
            self.viewer.set_layers(*L)
        self.win.update_stats()

    def apply_theme(self):
        self.style_viewer(self.viewer)
        self.panel.apply_theme(self.win.settings.colors["text"])
        self.empty_icon.setPixmap(icons.icon("camera", self.win.settings.colors["accent"], 128)
                                  .pixmap(QSize(64, 64), self.devicePixelRatioF()))
        self.panel.set_font(self.win.settings["ascii_font"])

    def deactivate(self):
        self.stop()
