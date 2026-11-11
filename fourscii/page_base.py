"""Base commune des pages : barre d'actions, visionneuse et accès à la fenêtre."""
from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from . import render
from .widgets import ArtViewer


class Page(QWidget):
    title = ""
    color_key = None  # réglage où est mémorisé le mode de couleur de la page

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.art = None

    # -- à surcharger
    def current_art(self):
        return self.art

    def current_layers(self):
        art = self.current_art()
        if art is None:
            return None
        c = self.win.settings.colors
        return render.layers(art, self.color_mode(), c["accent"], self.win.settings["color2"])

    def color_mode(self):
        return "mono"

    def apply_theme(self):
        pass

    def activate(self):
        pass

    def deactivate(self):
        pass

    # -- utilitaires
    def icon_btn(self, name, tip, slot=None, size=18, text=""):
        b = QPushButton(text)
        b.setObjectName("icon" if not text else "ghost")
        b.setToolTip(tip)
        b.setCursor(Qt.PointingHandCursor)
        b.setIconSize(QSize(size, size))
        self.win.bind_icon(b, name, "text")
        if slot:
            b.clicked.connect(slot)
        return b

    def make_viewer(self):
        """Visionneuse encadrée + boutons de zoom ; renvoie (cadre, visionneuse)."""
        frame = QFrame()
        frame.setObjectName("viewer")
        v = QVBoxLayout(frame)
        v.setContentsMargins(6, 6, 6, 6)
        viewer = ArtViewer()
        v.addWidget(viewer, 1)
        return frame, viewer

    def zoom_row(self, viewer):
        h = QHBoxLayout()
        h.setSpacing(2)
        lbl = QLabel("")
        lbl.setObjectName("stat")
        viewer.zoomed.connect(lambda px: lbl.setText(f"{px:.1f} px"))
        h.addWidget(lbl)
        h.addWidget(self.icon_btn("zoom_out", "Dézoomer (Ctrl + molette)", lambda: viewer.zoom(1 / 1.2)))
        h.addWidget(self.icon_btn("fit", "Ajuster à la fenêtre", viewer.fit))
        h.addWidget(self.icon_btn("zoom_in", "Zoomer (Ctrl + molette)", lambda: viewer.zoom(1.2)))
        return h

    def style_viewer(self, viewer):
        family, fg, bg = self.win.view_style()
        viewer.set_style(family, fg, bg)
