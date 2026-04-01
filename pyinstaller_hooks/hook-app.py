"""PyInstaller hook for the Quant Terminal app package.

All UI modules in MODULE_SECTIONS are loaded dynamically via importlib,
so PyInstaller cannot discover them through static analysis.
We use collect_submodules to ensure every submodule under app/ is included.
"""

import sys
from PyInstaller.utils.hooks import collect_submodules

# Collect all app submodules (covers the 59+ dynamically-loaded UI modules)
hiddenimports = collect_submodules("app")

# Third-party modules that PyInstaller sometimes misses
hiddenimports += [
    # SSL certificates (critical for yfinance/FRED HTTPS requests)
    "certifi",
    # dotenv
    "dotenv",
    # scipy submodules used by analysis modules
    "scipy.optimize",
    "scipy.stats",
    "scipy.linalg",
    # pyarrow (pandas parquet backend)
    "pyarrow.pandas_compat",
    "pyarrow.lib",
    # yfinance internals
    "yfinance.scrapers",
    "yfinance.scrapers.history",
    "yfinance.data",
    # numpy submodules
    "numpy.random._generator",
]

# Windows-only: Excel COM automation
if sys.platform == "win32":
    hiddenimports += ["win32com", "win32com.client", "pythoncom", "pywintypes"]
