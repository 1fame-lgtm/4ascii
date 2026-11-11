"""Galerie : tes créations enregistrées dans ~/4scii/galerie."""
import json
import os
import time
from pathlib import Path

import numpy as np
from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QInputDialog, QLabel, QMenu, QMessageBox,
                               QScrollArea, QVBoxLayout, QWidget)

from . import render
from .config import GALLERY_DIR, ensure_dirs
from .engine import AsciiArt
from .page_base import Page
from .widgets import FlowLayout, clear_layout


def _enc(a):
    if a is None:
        return None
    return ["".join("%02x%02x%02x" % tuple(int(v) for v in px) for px in row) for row in a]


def _dec(rows):
    if not rows:
        return None
    return np.array([[[int(r[i:i + 2], 16), int(r[i + 2:i + 4], 16), int(r[i + 4:i + 6], 16)]
                      for i in range(0, len(r), 6)] for r in rows], dtype=np.uint8)


def save_item(name, lines, fg=None, bg=None):
    ensure_dirs()
    stamp = time.strftime("%Y%m%d-%H%M%S")
    path = GALLERY_DIR / f"{stamp}.json"
    i = 1
    while path.exists():
        path = GALLERY_DIR / f"{stamp}-{i}.json"
        i += 1
    data = {"name": name, "created": time.time(), "lines": lines, "fg": _enc(fg), "bg": _enc(bg)}
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def load_item(path):
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    return d.get("name", Path(path).stem), d.get("created", 0), d["lines"], _dec(d.get("fg")), _dec(d.get("bg"))


class Tile(QFrame):
    def __init__(self, page, path, name, created, lines, fg, bg):
        super().__init__()
        self.page, self.path = page, path
        self.lines, self.fg, self.bg = lines, fg, bg
        self.setObjectName("card")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedWidth(236)
        v = QVBoxLayout(self)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(4)
        thumb = QLabel()
        thumb.setFixedSize(220, 150)
        thumb.setAlignment(Qt.AlignCenter)
        family, tfg, tbg = page.win.view_style()
        cols = max((len(l) for l in lines), default=1) or 1
        cw, ch, _ = render.cell_size(family, 100)
        px = max(2.0, min(14.0, 100 * 212 / (cols * cw), 100 * 142 / (max(1, len(lines)) * ch)))
        dpr = page.devicePixelRatioF()
        img = render.render_image(lines, fg, bg, family, px * dpr, tfg, None)
        pm = QPixmap.fromImage(img)
        pm.setDevicePixelRatio(dpr)
        thumb.setPixmap(pm)
        thumb.setStyleSheet(f"background:{tbg or page.win.settings.colors['bg']}; border-radius:8px;")
        v.addWidget(thumb)
        t = QLabel(name)
        t.setObjectName("h3")
        v.addWidget(t)
        s = QLabel(time.strftime("%d/%m/%Y %H:%M", time.localtime(created)) + f"  ·  {cols}×{len(lines)}")
        s.setObjectName("small")
        v.addWidget(s)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.page.open_item(self)
        elif e.button() == Qt.RightButton:
            self.page.item_menu(self, e.globalPosition().toPoint())


class GalleryPage(Page):
    title = "Galerie"

    def __init__(self, win):
        super().__init__(win)
        self.selected = None
        v = QVBoxLayout(self)
        v.setContentsMargins(22, 4, 22, 16)
        v.setSpacing(10)
        top = QHBoxLayout()
        h = QLabel("Tes créations")
        h.setObjectName("h1")
        top.addWidget(h)
        top.addStretch()
        self.count = QLabel("")
        self.count.setObjectName("sub")
        top.addWidget(self.count)
        top.addWidget(self.icon_btn("folder", "Ouvrir le dossier de la galerie", self.open_folder, text="  Dossier"))
        v.addLayout(top)
        sub = QLabel("Clic : ouvrir dans l'Atelier  ·  clic droit : plus d'options. "
                     "Ajoute une création avec le bouton ★ de la barre du bas.")
        sub.setObjectName("sub")
        v.addWidget(sub)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        body = QWidget()
        self.flow = FlowLayout(body)
        scroll.setWidget(body)
        v.addWidget(scroll, 1)
        self.empty = QLabel("Ta galerie est vide pour l'instant.")
        self.empty.setObjectName("sub")
        self.empty.setAlignment(Qt.AlignCenter)
        v.addWidget(self.empty)

    def refresh(self):
        clear_layout(self.flow)
        ensure_dirs()
        files = sorted(GALLERY_DIR.glob("*.json"), key=os.path.getmtime, reverse=True)
        n = 0
        for f in files:
            try:
                name, created, lines, fg, bg = load_item(f)
            except (OSError, ValueError, KeyError):
                continue
            self.flow.addWidget(Tile(self, f, name, created, lines, fg, bg))
            n += 1
        self.count.setText(f"{n} création{'s' if n > 1 else ''}")
        self.empty.setVisible(n == 0)

    def open_item(self, tile):
        self.selected = tile
        self.win.editor_page.load_layers(tile.lines, tile.fg)
        self.win.show_page("editor")

    def item_menu(self, tile, pos):
        self.selected = tile
        m = self.win.new_menu()
        m.addAction("Ouvrir dans l'Atelier", lambda: self.open_item(tile))
        m.addAction("Copier le texte", lambda: (QApplication.clipboard().setText("\n".join(tile.lines)),
                                                self.win.toast("Copié !")))
        m.addAction("Renommer…", lambda: self.rename(tile))
        m.addSeparator()
        m.addAction("Supprimer", lambda: self.delete(tile))
        m.exec(pos)

    def rename(self, tile):
        d = json.loads(tile.path.read_text(encoding="utf-8"))
        name, ok = QInputDialog.getText(self, "Renommer", "Nom :", text=d.get("name", ""))
        if ok and name.strip():
            d["name"] = name.strip()
            tile.path.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
            self.refresh()

    def delete(self, tile):
        if QMessageBox.question(self, "Supprimer", "Supprimer cette création de la galerie ?") == QMessageBox.Yes:
            tile.path.unlink(missing_ok=True)
            self.refresh()

    def open_folder(self):
        ensure_dirs()
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(GALLERY_DIR)))

    def current_art(self):
        return AsciiArt(self.selected.lines) if self.selected else None

    def current_layers(self):
        return (self.selected.lines, self.selected.fg, self.selected.bg) if self.selected else None

    def activate(self):
        self.refresh()

    def apply_theme(self):
        if self.isVisible():
            self.refresh()
