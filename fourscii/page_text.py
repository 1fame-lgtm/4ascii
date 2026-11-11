"""Page Texte → bannière ASCII avec n'importe quelle police installée."""
import random

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import (QCheckBox, QFontComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit,
                               QPushButton, QScrollArea, QVBoxLayout, QWidget)

from . import engine, render, textart
from .page_base import Page
from .widgets import LabeledSlider, caption, combo, section, set_combo

DEFAULT_TEXT = {"text": "4scii", "font": "Arial Black", "style": "shape", "rows": 9, "charset": "ASCII complet",
                "bold": True, "italic": False, "spacing": 0, "align": "left", "fill_word": "4SCII",
                "shadow_char": "░", "thickness": 2}


class TextPage(Page):
    title = "Texte → Bannière"
    color_key = "text_color"

    def __init__(self, win):
        super().__init__(win)
        self.T = dict(DEFAULT_TEXT)
        self.T.update(win.settings["text_params"])
        self.color = win.settings["text_color"]
        self._timer = QTimer(self, singleShot=True, interval=70, timeout=self.rebuild)

        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        left = QVBoxLayout()
        left.setContentsMargins(22, 4, 18, 16)
        left.setSpacing(10)

        top = QHBoxLayout()
        lab = QLabel("Ton texte")
        lab.setObjectName("h3")
        top.addWidget(lab)
        top.addStretch()
        frame, self.viewer = self.make_viewer()
        top.addLayout(self.zoom_row(self.viewer))
        left.addLayout(top)
        self.input = QPlainTextEdit(self.T["text"])
        self.input.setFixedHeight(84)
        self.input.setPlaceholderText("Écris quelque chose… (plusieurs lignes possibles)")
        f = self.input.font()
        f.setPointSize(f.pointSize() + 4)
        self.input.setFont(f)
        self.input.textChanged.connect(lambda: self._set("text", self.input.toPlainText()))
        left.addWidget(self.input)
        left.addWidget(frame, 1)
        h.addLayout(left, 1)

        # ---- réglages
        side = QFrame()
        side.setObjectName("controls")
        sv = QVBoxLayout(side)
        sv.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedWidth(300)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        body = QWidget()
        scroll.setWidget(body)
        v = QVBoxLayout(body)
        v.setContentsMargins(14, 6, 14, 14)
        v.setSpacing(4)
        sv.addWidget(scroll)
        h.addWidget(side)

        v.addWidget(section("Police"))
        row = QHBoxLayout()
        self.font = QFontComboBox()
        self.font.setSizeAdjustPolicy(QFontComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.font.setMinimumContentsLength(8)
        self.font.setCurrentFont(QFont(self.T["font"]))
        self.font.currentFontChanged.connect(lambda f: self._set("font", f.family()))
        row.addWidget(self.font, 1)
        dice = QPushButton()
        dice.setObjectName("ghost")
        dice.setFixedWidth(42)
        win.bind_icon(dice, "dice", "text", 18)
        dice.setToolTip("Police au hasard")
        dice.clicked.connect(self.random_font)
        row.addWidget(dice)
        v.addLayout(row)
        st = QHBoxLayout()
        self.bold = QCheckBox("Gras")
        self.bold.setChecked(self.T["bold"])
        self.bold.toggled.connect(lambda b: self._set("bold", b))
        self.italic = QCheckBox("Italique")
        self.italic.setChecked(self.T["italic"])
        self.italic.toggled.connect(lambda b: self._set("italic", b))
        st.addWidget(self.bold)
        st.addWidget(self.italic)
        st.addStretch()
        v.addLayout(st)
        self.spacing = LabeledSlider("Espacement des lettres", -10, 30, self.T["spacing"])
        self.spacing.valueChanged.connect(lambda x: self._set("spacing", int(x)))
        v.addWidget(self.spacing)
        v.addWidget(caption("Alignement (plusieurs lignes)"))
        self.align = combo({"left": "Gauche", "center": "Centré", "right": "Droite"}, self.T["align"])
        self.align.currentIndexChanged.connect(lambda: self._set("align", self.align.currentData()))
        v.addWidget(self.align)

        v.addWidget(section("Style"))
        self.style = combo(textart.STYLES, self.T["style"])
        self.style.currentIndexChanged.connect(lambda: self._set("style", self.style.currentData()))
        v.addWidget(self.style)
        self.rows = LabeledSlider("Hauteur (lignes)", 3, 60, self.T["rows"])
        self.rows.valueChanged.connect(lambda x: self._set("rows", int(x)))
        v.addWidget(self.rows)
        self.charset_lbl = caption("Caractères")
        v.addWidget(self.charset_lbl)
        self.charset = combo([c for c in engine.CHARSETS if c != "Personnalisé"], self.T["charset"])
        self.charset.currentIndexChanged.connect(lambda: self._set("charset", self.charset.currentData()))
        v.addWidget(self.charset)
        self.fill_lbl = caption("Mot de remplissage")
        v.addWidget(self.fill_lbl)
        self.fill = QLineEdit(self.T["fill_word"])
        self.fill.textChanged.connect(lambda t: self._set("fill_word", t))
        v.addWidget(self.fill)
        self.shadow_lbl = caption("Caractère d'ombre")
        v.addWidget(self.shadow_lbl)
        self.shadow = QLineEdit(self.T["shadow_char"])
        self.shadow.setMaxLength(1)
        self.shadow.textChanged.connect(lambda t: self._set("shadow_char", t or "░"))
        v.addWidget(self.shadow)
        self.thick = LabeledSlider("Épaisseur / profondeur", 1, 4, self.T["thickness"])
        self.thick.valueChanged.connect(lambda x: self._set("thickness", int(x)))
        v.addWidget(self.thick)

        v.addWidget(section("Couleur"))
        self.colormode = combo({k: v for k, v in render.COLOR_MODES.items() if k != "color"}, self.color)
        self.colormode.currentIndexChanged.connect(self._color)
        v.addWidget(self.colormode)
        v.addStretch()
        self._visibility()

    def _set(self, k, val):
        self.T[k] = val
        if k == "style":
            self._visibility()
        self._timer.start()

    def _visibility(self):
        s = self.T["style"]
        for w in (self.charset_lbl, self.charset):
            w.setVisible(s in ("shape", "outline"))
        for w in (self.fill_lbl, self.fill):
            w.setVisible(s == "fill")
        for w in (self.shadow_lbl, self.shadow):
            w.setVisible(s == "shadow")
        self.thick.setVisible(s in ("outline", "relief"))

    def _color(self):
        self.color = self.colormode.currentData()
        self.win.settings["text_color"] = self.color
        self.refresh_view()

    def random_font(self):
        fams = [f for f in QFontDatabase.families() if not f.startswith("@")]
        if fams:
            self.font.setCurrentFont(QFont(random.choice(fams)))

    def rebuild(self):
        self.win.settings["text_params"] = dict(self.T)
        T = self.T
        self.art = textart.make_banner(T["text"], T["font"], T["rows"], T["style"], T["charset"], T["bold"],
                                       T["italic"], T["spacing"], T["align"], T["shadow_char"], T["fill_word"],
                                       T["thickness"], self.win.settings["ascii_font"])
        self.refresh_view()

    def color_mode(self):
        return self.color

    def refresh_view(self):
        L = self.current_layers()
        if L:
            self.viewer.set_layers(*L)
        self.win.update_stats()

    def apply_theme(self):
        self.style_viewer(self.viewer)
        set_combo(self.colormode, self.color)
        self.rebuild()
