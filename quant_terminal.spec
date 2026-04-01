# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for Quant Terminal.

Build with:  pyinstaller quant_terminal.spec --noconfirm
Output:       dist/QuantTerminal/  (onedir)
              dist/Quant Terminal.app  (macOS bundle)
"""

import sys
from pathlib import Path

block_cipher = None

IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform == "win32"

# --- Icon (optional -- build works without it) ---
icon_mac = "assets/icons/quant_terminal.icns"
icon_win = "assets/icons/quant_terminal.ico"
icon = icon_mac if IS_MAC else icon_win if IS_WIN else None
if icon and not Path(icon).exists():
    icon = None  # Skip if icon file not yet created

# --- Data files to bundle ---
datas = [
    ("src/app/assets/screenshots", "app/assets/screenshots"),
    ("src/app/services/bitcoin_historical_prices.csv", "app/services"),
]

# Bundle custom indicator plugin directory if it exists
custom_ind = Path("src/app/ui/modules/chart/custom_indicators")
if custom_ind.exists():
    datas.append((str(custom_ind), "app/ui/modules/chart/custom_indicators"))

# --- Hidden imports (see pyinstaller_hooks/hook-app.py for details) ---
hiddenimports = []

# Platform-specific hidden imports
if IS_WIN:
    hiddenimports += ["win32com", "win32com.client", "pythoncom", "pywintypes"]

# --- Excludes (reduce bundle size) ---
excludes = [
    "tkinter",
    "_tkinter",
    "matplotlib",
    "IPython",
    "jupyter",
    "notebook",
    "test",
    "unittest",
    "PySide6.QtWebEngine",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtMultimedia",
]

# --- Analysis ---
a = Analysis(
    ["src/app/main.py"],
    pathex=["src"],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=["pyinstaller_hooks"],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,  # onedir mode
    name="QuantTerminal",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # UPX can break Qt libraries on macOS
    console=False,  # GUI app -- no terminal window
    icon=icon,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="QuantTerminal",
)

# --- macOS .app bundle ---
if IS_MAC:
    app = BUNDLE(
        coll,
        name="Quant Terminal.app",
        icon=icon,
        bundle_identifier="com.quantapp.quantterminal",
        info_plist={
            "CFBundleName": "Quant Terminal",
            "CFBundleDisplayName": "Quant Terminal",
            "CFBundleVersion": "0.2.0",
            "CFBundleShortVersionString": "0.2.0",
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "11.0",
            "NSRequiresAquaSystemAppearance": False,
        },
    )
