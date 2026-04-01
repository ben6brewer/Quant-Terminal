@echo off
REM -------------------------------------------------------------------
REM Quant Terminal - Windows Build Script
REM
REM Produces:
REM   dist\QuantTerminal\QuantTerminal.exe  (standalone application)
REM
REM Usage:
REM   build_windows.bat
REM -------------------------------------------------------------------

cd /d "%~dp0"

echo ==> Creating build virtual environment...
python -m venv build_venv
call build_venv\Scripts\activate.bat

echo ==> Installing dependencies...
pip install --upgrade pip
pip install -e .
pip install "pyinstaller>=6.0" "pywin32>=306"

echo ==> Running PyInstaller...
pyinstaller quant_terminal.spec --noconfirm

echo ==> Build complete: dist\QuantTerminal\QuantTerminal.exe

call deactivate
echo ==> Done.
