"""Lance 4scii :  python main.py   (ou double-clic sur 4scii.pyw pour ne voir que l'interface)"""
import importlib.util
import os
import runpy

if __name__ == "__main__":
    if importlib.util.find_spec("PySide6") is None or importlib.util.find_spec("numpy") is None:
        runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), "4scii.pyw"), run_name="__main__")
    else:
        from fourscii.app import run
        run()
