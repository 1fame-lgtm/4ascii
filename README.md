# 4scii ✦

Générateur d'**art ASCII** open source écrit en Python, avec la même interface que **4tafy**
(fenêtre façon macOS, barre latérale, thèmes 4tafy / Dracula / Matrix / Sakura…).

## Lancer

- double-clic sur **`4scii.pyw`** (installe PySide6 + numpy au premier lancement si besoin)
- ou `lancer_4scii.bat`
- ou `python main.py`

## Le moteur 4SHAPE

La plupart des convertisseurs choisissent un caractère seulement selon la luminosité.
**4SHAPE** dessine chaque caractère de ta police, le découpe en sous-cases (2×2 à 4×8) et mesure
où se trouve l'encre. L'image est découpée de la même façon et chaque case reçoit le caractère dont
la **forme** ressemble le plus (distance de forme + distance de ton, calculée en une opération matricielle).
Les bords, diagonales et courbes sont donc suivis par les bons caractères ( `/ \ | _ ( )` … ).

Autour du cœur :
- correction automatique du rapport largeur/hauteur des caractères (mesuré sur la police) ;
- niveaux automatiques, luminosité, contraste, gamma, netteté ;
- tramage **Floyd–Steinberg**, **Atkinson** ou **Bayer** sur des niveaux d'encre *mesurés* ;
- contours orientés (tenseur de structure / Sobel) → `| / - \` ou `│ ╱ ─ ╲` par-dessus ;
- modes **Densité**, **Contours seuls**, **Braille ⣿** (2×4 points), **Quadrants ▚** (2×2) et
  **Pixels ▀** (demi-blocs en vraies couleurs).

## Pages

| Page | Ce qu'elle fait |
|---|---|
| **Image** | fichier, glisser-déposer, Ctrl+V, capture d'écran, **GIF animés** (lecture + export HTML animé), 10 préréglages et un 🎲 |
| **Texte** | bannières avec **n'importe quelle police installée** : 4SHAPE, contour, blocs, ombre, relief 3D, demi-blocs, quadrants, braille, rempli avec un mot |
| **Webcam** | ASCII en direct depuis la caméra (miroir, figer, envoyer vers Image) |
| **Atelier** | éditeur de dessin : crayon, gomme, lignes intelligentes, cadres (simple, double, arrondi, épais…), ellipses, pot, texte, pipette, couleurs, annuler/rétablir |
| **Galerie** | tes créations enregistrées (`~/4scii/galerie`) |
| **Personnaliser** | les 12 thèmes de 4tafy, couleurs, police ASCII, fond des aperçus, coins, ombre… |

Couleurs : mono, couleurs de l'image, dégradés (encre / horizontal / vertical), arc-en-ciel, Matrix, feu, glace.

Exports (barre du bas) : **Copier** (texte + version colorée pour Word / mails), **TXT**, **HTML**, **PNG**,
**SVG**, **ANSI** (terminal en vraies couleurs), et envoi vers l'**Atelier** ou la **Galerie**.

## Raccourcis

`Ctrl+1…6` pages · `Ctrl+O` ouvrir · `Ctrl+V` coller une image · `Ctrl+Maj+C` copier l'art ·
`Ctrl+S` galerie · `Ctrl+E` Atelier · Ctrl + molette : zoom ·
Atelier : `P E L R O F T I` outils, `Ctrl+Z / Ctrl+Y`, clic droit = gommer, Alt + clic = pipette.
