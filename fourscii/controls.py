"""Panneau de réglages du moteur (partagé par les pages Image et Webcam)."""
import random

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtWidgets import (QCheckBox, QFrame, QHBoxLayout, QLineEdit, QPushButton, QScrollArea, QVBoxLayout,
                               QWidget)

from . import engine, render
from .widgets import LabeledSlider, caption, combo, section, set_combo

PRESETS = {
    "—": None,
    "Portrait net": dict(mode="shape", charset="ASCII complet", precision="Fine", contrast=25, sharpen=40,
                         tone=30, boost=35, edges=0, dither="none", autolevels=True),
    "Photo douce": dict(mode="density", charset="4scii équilibré", precision="Normale", contrast=10, sharpen=0,
                        dither="fs", edges=0, autolevels=True),
    "Croquis (contours)": dict(mode="shape", charset="Classique 10", contrast=40, sharpen=60, edges=55,
                               edge_style="ascii", tone=60, boost=10),
    "Contours seuls": dict(mode="edges", edges=0, edge_style="unicode", sharpen=40, contrast=20),
    "Braille HD": dict(mode="braille", dither="atkinson", contrast=15, edges=0),
    "Pixel art couleur": dict(mode="halfblock", dither="none", saturation=130, edges=0),
    "Quadrants tramés": dict(mode="blocks", dither="bayer", contrast=10, edges=0),
    "Terminal rétro": dict(mode="density", charset="Classique 10", dither="bayer", contrast=30, edges=0),
    "Matrix": dict(mode="density", charset="Matrix (katakana)", dither="none", contrast=35, edges=0),
    "Blocs ░▒▓": dict(mode="density", charset="Blocs", dither="fs", edges=0),
}


class ControlPanel(QScrollArea):
    """Tous les réglages de conversion ; émet `changed` (avec un petit délai) quand l'un bouge."""
    changed = Signal()
    color_changed = Signal()

    def __init__(self, params=None, color_mode="mono", max_cols=400, live=False):
        super().__init__()
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFixedWidth(300)
        self.setFrameShape(QFrame.NoFrame)
        self.P = dict(engine.DEFAULTS)
        if params:
            self.P.update({k: v for k, v in params.items() if k in engine.DEFAULTS})
        self.color_mode = color_mode
        self._timer = QTimer(self, singleShot=True, interval=90, timeout=self.changed.emit)

        body = QWidget()
        self.setWidget(body)
        v = QVBoxLayout(body)
        v.setContentsMargins(14, 6, 14, 14)
        v.setSpacing(4)
        self.v = v

        # --- préréglages
        v.addWidget(section("Préréglages"))
        row = QHBoxLayout()
        self.preset = combo(list(PRESETS))
        self.preset.currentTextChanged.connect(self._apply_preset)
        row.addWidget(self.preset, 1)
        self.dice = QPushButton()
        self.dice.setToolTip("Réglages au hasard")
        self.dice.setObjectName("ghost")
        self.dice.setFixedWidth(42)
        self.dice.setIconSize(QSize(18, 18))
        self.dice.clicked.connect(self.randomize)
        row.addWidget(self.dice)
        v.addLayout(row)

        # --- algorithme
        v.addWidget(section("Algorithme"))
        self.mode = combo(engine.MODES, self.P["mode"])
        self.mode.currentIndexChanged.connect(lambda: self._set("mode", self.mode.currentData()))
        v.addWidget(self.mode)
        self.cols = LabeledSlider("Largeur (colonnes)", 16, max_cols, self.P["cols"])
        self.cols.valueChanged.connect(lambda x: self._set("cols", int(x)))
        v.addWidget(self.cols)
        self.charset_lbl = caption("Jeu de caractères")
        v.addWidget(self.charset_lbl)
        self.charset = combo(list(engine.CHARSETS), self.P["charset"])
        self.charset.currentIndexChanged.connect(lambda: self._set("charset", self.charset.currentData()))
        v.addWidget(self.charset)
        self.custom = QLineEdit(self.P["custom_chars"])
        self.custom.setPlaceholderText("Tes caractères, ex :  .:-=+*#%@")
        self.custom.textChanged.connect(lambda t: self._set("custom_chars", t))
        v.addWidget(self.custom)
        self.auto_order = QCheckBox("Trier selon l'encre mesurée")
        self.auto_order.setChecked(self.P["auto_order"])
        self.auto_order.toggled.connect(lambda b: self._set("auto_order", b))
        v.addWidget(self.auto_order)
        self.precision_lbl = caption("Précision des formes")
        v.addWidget(self.precision_lbl)
        self.precision = combo(list(engine.PRECISIONS), self.P["precision"])
        self.precision.currentIndexChanged.connect(lambda: self._set("precision", self.precision.currentData()))
        v.addWidget(self.precision)
        self.tone = LabeledSlider("Forme ↔ Ton", 0, 100, self.P["tone"],
                                  tip="0 = suit uniquement la forme, 100 = privilégie la luminosité")
        self.tone.valueChanged.connect(lambda x: self._set("tone", int(x)))
        v.addWidget(self.tone)
        self.boost = LabeledSlider("Accentuer les formes", 0, 100, self.P["boost"])
        self.boost.valueChanged.connect(lambda x: self._set("boost", int(x)))
        v.addWidget(self.boost)

        # --- image
        v.addWidget(section("Image"))
        self.brightness = LabeledSlider("Luminosité", -100, 100, self.P["brightness"])
        self.brightness.valueChanged.connect(lambda x: self._set("brightness", int(x)))
        v.addWidget(self.brightness)
        self.contrast = LabeledSlider("Contraste", -100, 100, self.P["contrast"])
        self.contrast.valueChanged.connect(lambda x: self._set("contrast", int(x)))
        v.addWidget(self.contrast)
        self.gamma = LabeledSlider("Gamma", 0.2, 3.0, self.P["gamma"], scale=100)
        self.gamma.valueChanged.connect(lambda x: self._set("gamma", x))
        v.addWidget(self.gamma)
        self.sharpen = LabeledSlider("Netteté", 0, 100, self.P["sharpen"])
        self.sharpen.valueChanged.connect(lambda x: self._set("sharpen", int(x)))
        v.addWidget(self.sharpen)
        self.aspect = LabeledSlider("Correction hauteur", 50, 200, self.P["aspect"], suffix=" %")
        self.aspect.valueChanged.connect(lambda x: self._set("aspect", int(x)))
        v.addWidget(self.aspect)
        self.autolevels = QCheckBox("Niveaux automatiques")
        self.autolevels.setChecked(self.P["autolevels"])
        self.autolevels.toggled.connect(lambda b: self._set("autolevels", b))
        v.addWidget(self.autolevels)
        self.invert = QCheckBox("Inverser")
        self.invert.setChecked(self.P["invert"])
        self.invert.toggled.connect(lambda b: self._set("invert", b))
        v.addWidget(self.invert)
        self.dark_bg = QCheckBox("Pensé pour un fond sombre")
        self.dark_bg.setChecked(self.P["dark_bg"])
        self.dark_bg.toggled.connect(lambda b: self._set("dark_bg", b))
        v.addWidget(self.dark_bg)

        # --- tramage & contours
        v.addWidget(section("Tramage & contours"))
        self.dither = combo(engine.DITHERS, self.P["dither"])
        self.dither.currentIndexChanged.connect(lambda: self._set("dither", self.dither.currentData()))
        v.addWidget(self.dither)
        self.edges = LabeledSlider("Contours par-dessus", 0, 100, self.P["edges"])
        self.edges.valueChanged.connect(lambda x: self._set("edges", int(x)))
        v.addWidget(self.edges)
        self.edge_style = combo(engine.EDGE_STYLES, self.P["edge_style"])
        self.edge_style.currentIndexChanged.connect(lambda: self._set("edge_style", self.edge_style.currentData()))
        v.addWidget(self.edge_style)

        # --- couleur
        v.addWidget(section("Couleur"))
        self.colormode = combo(render.COLOR_MODES, color_mode)
        self.colormode.currentIndexChanged.connect(self._color)
        v.addWidget(self.colormode)
        self.saturation = LabeledSlider("Saturation", 0, 250, self.P["saturation"], suffix=" %")
        self.saturation.valueChanged.connect(lambda x: self._set("saturation", int(x)))
        v.addWidget(self.saturation)
        v.addStretch()
        self._visibility()

    # ------------------------------------------------------------------
    def apply_theme(self, text_color):
        from .icons import icon
        self.dice.setIcon(icon("dice", text_color))

    def params(self):
        return dict(self.P)

    def _set(self, key, value):
        self.P[key] = value
        if key in ("mode", "charset"):
            self._visibility()
        self._timer.start()

    def _color(self):
        self.color_mode = self.colormode.currentData()
        self.color_changed.emit()

    def _visibility(self):
        m = self.P["mode"]
        glyphs = m in ("shape", "density", "edges")
        self.charset_lbl.setVisible(m in ("shape", "density"))
        self.charset.setVisible(m in ("shape", "density"))
        self.custom.setVisible(m in ("shape", "density") and self.P["charset"] == "Personnalisé")
        self.auto_order.setVisible(m == "density")
        self.precision_lbl.setVisible(glyphs)
        self.precision.setVisible(glyphs)
        self.tone.setVisible(m == "shape")
        self.boost.setVisible(m == "shape")
        self.edges.setVisible(m != "edges")

    def set_params(self, P, color_mode=None):
        self.P.update({k: v for k, v in P.items() if k in engine.DEFAULTS})
        for name in ("cols", "tone", "boost", "brightness", "contrast", "gamma", "sharpen", "aspect", "edges",
                     "saturation"):
            getattr(self, name).setValue(self.P[name])
        for name in ("mode", "charset", "precision", "dither", "edge_style"):
            set_combo(getattr(self, name), self.P[name])
        for name in ("auto_order", "autolevels", "invert", "dark_bg"):
            w = getattr(self, name)
            w.blockSignals(True)
            w.setChecked(self.P[name])
            w.blockSignals(False)
        self.custom.blockSignals(True)
        self.custom.setText(self.P["custom_chars"])
        self.custom.blockSignals(False)
        if color_mode:
            set_combo(self.colormode, color_mode)
            self.color_mode = color_mode
            self.color_changed.emit()
        self._visibility()
        self._timer.start()

    def set_font(self, family):
        self.P["font"] = family
        self._timer.start()

    def _apply_preset(self, name):
        P = PRESETS.get(name)
        if not P:
            return
        cm = "color" if P.get("mode") == "halfblock" else ("matrix" if name == "Matrix" else None)
        self.set_params(P, cm)

    def randomize(self):
        r = random.Random()
        P = dict(mode=r.choice(list(engine.MODES)), charset=r.choice([c for c in engine.CHARSETS if c != "Personnalisé"]),
                 contrast=r.randint(-10, 50), brightness=r.randint(-15, 15), gamma=round(r.uniform(0.7, 1.6), 2),
                 sharpen=r.choice([0, 20, 40, 70]), dither=r.choice(list(engine.DITHERS)),
                 edges=r.choice([0, 0, 25, 50]), tone=r.randint(10, 80), boost=r.randint(0, 70),
                 edge_style=r.choice(list(engine.EDGE_STYLES)))
        self.set_params(P, r.choice(list(render.COLOR_MODES)))
