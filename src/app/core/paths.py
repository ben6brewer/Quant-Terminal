"""Path resolution utilities for both development and PyInstaller frozen mode."""

from __future__ import annotations

import sys
from pathlib import Path


def is_frozen() -> bool:
    """Return True when running as a PyInstaller bundle."""
    return getattr(sys, "frozen", False)


def app_root() -> Path:
    """Return the root path for bundled data files.

    When frozen (PyInstaller onedir), this is sys._MEIPASS which maps to
    the _internal/ directory containing the package tree.
    When running from source, this is the 'src/' directory.
    """
    if is_frozen():
        return Path(sys._MEIPASS)
    return Path(__file__).parent.parent.parent  # src/app/core/paths.py -> src/


def assets_dir() -> Path:
    """Return path to bundled assets (screenshots, etc.)."""
    return app_root() / "app" / "assets"


def services_dir() -> Path:
    """Return path to services data files (CSVs, etc.)."""
    return app_root() / "app" / "services"


def user_data_dir() -> Path:
    """Return path to user-writable config/data directory."""
    return Path.home() / ".quant_terminal"


def env_file_path() -> Path:
    """Return path to the .env file.

    When frozen, the .env lives in ~/.quant_terminal/.env so it is
    user-writable and not bundled inside the app.
    When running from source, it lives at the project root.
    """
    if is_frozen():
        return user_data_dir() / ".env"
    return Path(__file__).parent.parent.parent.parent / ".env"
