"""Lance 4scii SANS fenêtre de terminal (double-clic sur ce fichier).

S'il manque des composants (PySide6, numpy), propose de les installer en arrière-plan.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
REQUIRED = ("PySide6", "numpy")
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def message(text, flags=0x40):
    try:
        import ctypes
        return ctypes.windll.user32.MessageBoxW(None, text, "4scii", flags)
    except Exception:
        return 0


def missing_modules():
    import importlib.util
    return [m for m in REQUIRED if importlib.util.find_spec(m) is None]


missing = missing_modules()
if missing:
    if message("Premier lancement : 4scii va installer les composants manquants\n"
               f"({', '.join(missing)}).\n\nCela peut prendre une minute, sans fenêtre de terminal. "
               "4scii s'ouvrira tout seul à la fin.", flags=0x41) != 1:  # OK / Annuler
        sys.exit(0)
    python = os.path.join(os.path.dirname(sys.executable), "python.exe")
    if not os.path.exists(python):
        python = sys.executable
    result = subprocess.run([python, "-m", "pip", "install", "-q", "-r", os.path.join(HERE, "requirements.txt")],
                            capture_output=True, text=True, creationflags=NO_WINDOW)
    if result.returncode != 0 or missing_modules():
        message("L'installation des composants a échoué :\n\n" + (result.stderr or result.stdout)[-800:], flags=0x10)
        sys.exit(1)

os.chdir(HERE)
from fourscii.app import run  # noqa: E402

run()
