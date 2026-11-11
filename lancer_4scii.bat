@echo off
rem Lance 4scii sans garder de terminal ouvert.
cd /d "%~dp0"
python -c "import PySide6, numpy" 2>nul || python -m pip install -q -r requirements.txt
start "" pythonw "%~dp0main.py"
exit /b
