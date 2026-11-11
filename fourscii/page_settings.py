"""Page Personnaliser : thèmes (les mêmes que 4tafy), couleurs, police ASCII, fenêtre."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFontDatabase
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel,
                               QPushButton, QScrollArea, QVBoxLayout, QWidget)

from .page_base import Page
from .themes import COLOR_LABELS, PRESETS
from .widgets import LabeledSlider, combo, section, set_combo

ABOUT = """<b>Comment marche 4SHAPE ?</b><br><br>
La plupart des convertisseurs choisissent un caractère seulement selon la luminosité.
4SHAPE dessine chaque caractère de ta police, le découpe en petites sous-cases et mesure où se trouve
l'encre. Chaque case de l'image est découpée de la même façon, puis le caractère dont la <i>forme</i>
ressemble le plus est choisi (distance de forme + distance de ton, réglable avec « Forme ↔ Ton »).
Résultat : les bords, diagonales et courbes sont suivis par les bons caractères ( / \\ | _ ( ) … ).<br><br>
Autour du cœur : niveaux automatiques, gamma, netteté, tramage Floyd–Steinberg / Atkinson / Bayer sur
des niveaux d'encre mesurés, détection d'orientation des contours (tenseur de structure),
braille 2×4, quadrants 2×2 et demi-blocs en couleurs réelles."""


def mono_families():
    fams = []
    for f in QFontDatabase.families():
        if f.startswith("@"):
            continue
        if QFontDatabase.isFixedPitch(f):
            fams.append(f)
    for f in ("Consolas", "Cascadia Mono", "Cascadia Code", "Courier New", "Lucida Console"):
        if f in QFontDatabase.families() and f not in fams:
            fams.append(f)
    return sorted(set(fams))


class SettingsPage(Page):
    title = "Personnaliser"

    def __init__(self, win):
        super().__init__(win)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        outer.addWidget(scroll)
        body = QWidget()
        scroll.setWidget(body)
        v = QVBoxLayout(body)
        v.setContentsMargins(28, 4, 28, 28)
        v.setSpacing(8)
        h = QLabel("Personnaliser")
        h.setObjectName("h1")
        v.addWidget(h)

        v.addWidget(section("Thème"))
        grid = QGridLayout()
        grid.setSpacing(10)
        self.preset_btns = {}
        for i, (name, cols) in enumerate(PRESETS.items()):
            b = QPushButton(name.replace("&", "&&"))
            b.setObjectName("preset")
            b.setCheckable(True)
            b.setMinimumHeight(54)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(f"QPushButton#preset {{ background: {cols['bg']}; color: {cols['text']}; "
                            f"border-left: 6px solid {cols['accent']}; }}")
            b.clicked.connect(lambda _=False, n=name: self.set_preset(n))
            grid.addWidget(b, i // 4, i % 4)
            self.preset_btns[name] = b
        v.addLayout(grid)

        v.addWidget(section("Couleurs"))
        cg = QGridLayout()
        cg.setHorizontalSpacing(18)
        cg.setVerticalSpacing(8)
        self.swatches = {}
        keys = list(COLOR_LABELS) + ["color2"]
        for i, key in enumerate(keys):
            lab = QLabel(COLOR_LABELS.get(key, "2e couleur des dégradés"))
            lab.setObjectName("sub")
            b = QPushButton()
            b.setObjectName("swatch")
            b.setFixedSize(46, 26)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=key: self.pick(k))
            self.swatches[key] = b
            cell = QHBoxLayout()
            cell.setSpacing(10)
            cell.addWidget(b)
            cell.addWidget(lab)
            cell.addStretch()
            cg.addLayout(cell, i // 3, i % 3)
        v.addLayout(cg)

        v.addWidget(section("Rendu ASCII"))
        row = QHBoxLayout()
        lab = QLabel("Police à chasse fixe")
        lab.setObjectName("sub")
        row.addWidget(lab)
        self.ascii_font = QComboBox()
        self.ascii_font.addItems(mono_families())
        self.ascii_font.setCurrentText(win.settings["ascii_font"])
        self.ascii_font.currentTextChanged.connect(lambda t: self._set("ascii_font", t))
        row.addWidget(self.ascii_font)
        row.addSpacing(20)
        lab = QLabel("Fond des aperçus")
        lab.setObjectName("sub")
        row.addWidget(lab)
        self.preview_bg = combo({"theme": "Thème", "black": "Noir", "white": "Blanc (encre noire)"},
                                win.settings["preview_bg"])
        self.preview_bg.currentIndexChanged.connect(lambda: self._set("preview_bg", self.preview_bg.currentData()))
        row.addWidget(self.preview_bg)
        row.addStretch()
        v.addLayout(row)

        v.addWidget(section("Fenêtre"))
        sliders = QHBoxLayout()
        sliders.setSpacing(24)
        self.font_size = LabeledSlider("Taille du texte", 8, 14, win.settings["font_size"], suffix=" pt")
        self.font_size.valueChanged.connect(lambda x: self._set("font_size", int(x)))
        self.radius = LabeledSlider("Coins arrondis", 0, 24, win.settings["radius"], suffix=" px")
        self.radius.valueChanged.connect(lambda x: self._set("radius", int(x)))
        self.opacity = LabeledSlider("Opacité des panneaux", 40, 100, win.settings["panel_opacity"], suffix=" %")
        self.opacity.valueChanged.connect(lambda x: self._set("panel_opacity", int(x)))
        for w in (self.font_size, self.radius, self.opacity):
            sliders.addWidget(w)
        v.addLayout(sliders)
        checks = QHBoxLayout()
        self.shadow = QCheckBox("Ombre autour de la fenêtre")
        self.shadow.setChecked(win.settings["window_shadow"])
        self.shadow.toggled.connect(lambda b: self._set("window_shadow", b))
        self.glow = QCheckBox("Lueur colorée en haut")
        self.glow.setChecked(win.settings["accent_glow"])
        self.glow.toggled.connect(lambda b: self._set("accent_glow", b))
        checks.addWidget(self.shadow)
        checks.addWidget(self.glow)
        checks.addStretch()
        reset = QPushButton("Réinitialiser l'apparence")
        reset.setObjectName("ghost")
        reset.clicked.connect(self.reset)
        checks.addWidget(reset)
        v.addLayout(checks)

        v.addWidget(section("L'algorithme"))
        about = QLabel(ABOUT)
        about.setWordWrap(True)
        about.setTextFormat(Qt.RichText)
        about.setObjectName("sub")
        box = QFrame()
        box.setObjectName("group")
        bl = QVBoxLayout(box)
        bl.setContentsMargins(18, 16, 18, 16)
        bl.addWidget(about)
        v.addWidget(box)
        v.addStretch()

    def _set(self, key, val):
        self.win.settings[key] = val
        self.win.schedule_theme()

    def set_preset(self, name):
        s = self.win.settings
        s["preset"] = name
        s.colors.update(PRESETS[name])
        self.win.schedule_theme()

    def pick(self, key):
        s = self.win.settings
        cur = s["color2"] if key == "color2" else s.colors[key]
        c = QColorDialog.getColor(QColor(cur), self, "Choisir une couleur")
        if c.isValid():
            if key == "color2":
                s["color2"] = c.name()
            else:
                s.colors[key] = c.name()
                s["preset"] = ""
            self.win.schedule_theme()

    def reset(self):
        self.win.settings.reset_look()
        self.win.schedule_theme()

    def apply_theme(self):
        s = self.win.settings
        for name, b in self.preset_btns.items():
            b.setChecked(name == s["preset"])
        for key, b in self.swatches.items():
            col = s["color2"] if key == "color2" else s.colors[key]
            b.setStyleSheet(f"QPushButton#swatch {{ background: {col}; }}")
        self.ascii_font.blockSignals(True)
        self.ascii_font.setCurrentText(s["ascii_font"])
        self.ascii_font.blockSignals(False)
        set_combo(self.preview_bg, s["preview_bg"])
        self.font_size.setValue(s["font_size"])
        self.radius.setValue(s["radius"])
        self.opacity.setValue(s["panel_opacity"])
        for w, k in ((self.shadow, "window_shadow"), (self.glow, "accent_glow")):
            w.blockSignals(True)
            w.setChecked(s[k])
            w.blockSignals(False)

    def current_art(self):
        return None
