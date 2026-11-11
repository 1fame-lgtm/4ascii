"""Chemins, constantes et réglages persistants de 4scii."""
import copy
import json
import os
from pathlib import Path

APP_NAME = "4scii"
VERSION = "1.0.0"

# Toutes les données vivent dans ~/4scii (modifiable avec la variable FOURSCII_HOME)
DATA_DIR = Path(os.environ.get("FOURSCII_HOME", Path.home() / "4scii"))
GALLERY_DIR = DATA_DIR / "galerie"
EXPORT_DIR = DATA_DIR / "exports"
SETTINGS_FILE = DATA_DIR / "settings.json"

IMAGE_FILTER = "Images (*.png *.jpg *.jpeg *.webp *.bmp *.gif *.tif *.tiff *.ico)"


def ensure_dirs():
    for d in (DATA_DIR, GALLERY_DIR, EXPORT_DIR):
        d.mkdir(parents=True, exist_ok=True)


DEFAULT_SETTINGS = {
    "preset": "4tafy",
    "colors": {
        "bg": "#0b0b10",
        "panel": "#15151d",
        "card": "#1f1f2b",
        "hover": "#2a2a3a",
        "accent": "#a855f7",
        "text": "#ffffff",
        "subtext": "#a7a7b3",
        "border": "#2e2e3e",
    },
    "color2": "#22d3ee",       # 2e couleur des dégradés
    "panel_opacity": 92,
    "radius": 12,
    "font_family": "Inter",
    "font_size": 10,
    "ascii_font": "Consolas",  # police des rendus ASCII (doit être à chasse fixe)
    "preview_bg": "theme",     # theme / black / white
    "window_shadow": True,
    "accent_glow": True,
    "image_params": {},
    "live_params": {},
    "text_params": {},
    "image_color": "mono",
    "live_color": "matrix",
    "text_color": "h_grad",
}


class Settings:
    def __init__(self, path=SETTINGS_FILE):
        self.path = Path(path)
        self.data = copy.deepcopy(DEFAULT_SETTINGS)
        self.load()

    def load(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                saved = json.load(f)
        except (OSError, ValueError):
            return
        colors = saved.pop("colors", {})
        self.data.update({k: v for k, v in saved.items() if k in DEFAULT_SETTINGS})
        self.data["colors"].update({k: v for k, v in colors.items() if k in DEFAULT_SETTINGS["colors"]})

    def save(self):
        ensure_dirs()
        tmp = self.path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, self.path)

    def reset_look(self):
        keep = {k: self.data[k] for k in ("image_params", "live_params", "text_params")}
        self.data = copy.deepcopy(DEFAULT_SETTINGS)
        self.data.update(keep)

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, value):
        self.data[key] = value

    def get(self, key, default=None):
        return self.data.get(key, default)

    @property
    def colors(self):
        return self.data["colors"]
