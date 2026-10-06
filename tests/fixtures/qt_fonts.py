"""Deterministic fonts for the offscreen Qt platform (test code only).

On Windows the offscreen QPA looks for fonts in ``PySide6/lib/fonts``
(absent), so without help the font database is EMPTY: every glyph is drawn as
a box and pyqtgraph menus/axes intermittently crash with access violations.
The root conftest therefore sets ``QT_QPA_FONTDIR`` to ``%WINDIR%\\Fonts`` at
import time (before any ``QApplication`` exists), and the session ``qapp``
fixture calls :func:`pin_app_font`, so that text metrics (axis widths, label
sizes) depend only on a few stock Windows fonts and not on whatever else is
installed (with the whole font directory loaded, the unpinned default font is
simply the alphabetically first family, e.g. an Office font).

* :func:`ensure_fonts` - fallback: register a fixed set of system fonts when
  the database is still empty (a no-op when ``QT_QPA_FONTDIR`` is set).
* :func:`pin_app_font` - default font Segoe UI 9pt (the Windows UI default)
  plus family substitutions; returns an ``undo`` callable.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, List, Tuple

# Font files for the families the app asks for ("Segoe UI", "Arial",
# "Consolas", "Courier New"); Menlo/Helvetica fall back to these.
_WINDOWS_FONT_FILES: Tuple[str, ...] = (
    "segoeui.ttf", "segoeuib.ttf", "arial.ttf", "arialbd.ttf",
    "consola.ttf", "consolab.ttf", "cour.ttf", "courbd.ttf",
)
_FONT_IDS: List[int] = []

# Families the app asks for that Windows does not have, mapped the way Windows
# itself maps them (Helvetica -> Arial) or to the next CSS fallback.
FONT_SUBSTITUTIONS: Tuple[Tuple[str, str], ...] = (
    ("Helvetica", "Arial"),
    ("Menlo", "Consolas"),
    ("Sans Serif", "Segoe UI"),
    ("sans-serif", "Segoe UI"),
    ("monospace", "Consolas"),
)
APP_FONT: Tuple[str, int] = ("Segoe UI", 9)  # the Windows default UI font


def ensure_fonts() -> List[str]:
    """Give the offscreen platform real fonts; return the available families.

    No-op when ``QT_QPA_FONTDIR`` is set (the root conftest sets it on
    Windows before the QApplication is created) or when the database already
    has families (e.g. fontconfig on Linux).  Otherwise, on Windows, registers
    a fixed set of system fonts as application fonts.  Fonts stay registered
    for the rest of the session (removing fonts that live widgets use is
    unsafe).
    """
    from PySide6.QtGui import QFontDatabase

    if os.environ.get("QT_QPA_FONTDIR") or QFontDatabase.families():
        return list(QFontDatabase.families())
    if os.name == "nt":
        font_dir = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
        for name in _WINDOWS_FONT_FILES:
            path = font_dir / name
            if path.exists():
                font_id = QFontDatabase.addApplicationFont(str(path))
                if font_id >= 0:
                    _FONT_IDS.append(font_id)
    return list(QFontDatabase.families())


def pin_app_font() -> Callable[[], None]:
    """Pin the default font (Segoe UI 9pt, as on Windows) and family fallbacks.

    Makes text metrics independent of whatever else is in the font database.
    Returns a callable that restores the previous font and substitutions.
    """
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication

    old_font = QApplication.font()
    old_subs = {family: list(QFont.substitutes(family)) for family, _ in FONT_SUBSTITUTIONS}
    for family, substitute in FONT_SUBSTITUTIONS:
        QFont.removeSubstitutions(family)
        QFont.insertSubstitution(family, substitute)
    QApplication.setFont(QFont(*APP_FONT))

    def undo() -> None:
        QApplication.setFont(old_font)
        for family, subs in old_subs.items():
            QFont.removeSubstitutions(family)
            if subs:
                QFont.insertSubstitutions(family, subs)

    return undo
