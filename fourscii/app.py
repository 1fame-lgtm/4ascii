"""Point d'entrée de l'application."""
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from .config import APP_NAME


def run():
    if sys.platform == "win32":
        try:  # icône propre dans la barre des tâches Windows
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("4scii.app")
        except Exception:
            pass
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyle("Fusion")

    from .main_window import MainWindow
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
