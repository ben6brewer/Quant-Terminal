"""Mixin for settings managers that store Qt.PenStyle and color tuples."""

from typing import Any, Dict

from PySide6.QtCore import Qt


class QtSettingsSerializationMixin:
    """Mixin providing serialization of Qt.PenStyle and RGB color tuples.

    Use with BaseSettingsManager subclasses that need to persist
    Qt pen styles (solid, dash, dot, dashdot) and color tuples to JSON.
    """

    _PENSTYLE_TO_STR = {
        Qt.SolidLine: "solid",
        Qt.DashLine: "dash",
        Qt.DotLine: "dot",
        Qt.DashDotLine: "dashdot",
    }

    _STR_TO_PENSTYLE = {v: k for k, v in _PENSTYLE_TO_STR.items()}

    def _serialize_settings(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        """Convert settings to JSON-serializable format.

        - Qt.PenStyle → string ("solid", "dash", etc.)
        - Tuples → lists (for JSON compatibility)
        """
        serialized = {}
        for key, value in settings.items():
            if isinstance(value, Qt.PenStyle):
                serialized[key] = self._PENSTYLE_TO_STR.get(value, "solid")
            elif isinstance(value, tuple):
                serialized[key] = list(value)
            else:
                serialized[key] = value
        return serialized

    def _deserialize_settings(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert settings from JSON format to runtime format.

        - Keys ending in ``_line_style`` with string values → Qt.PenStyle
        - Keys ending in ``_color`` with list values → tuples
        """
        deserialized = {}
        for key, value in data.items():
            if key.endswith("_line_style") and isinstance(value, str):
                deserialized[key] = self._STR_TO_PENSTYLE.get(value, Qt.SolidLine)
            elif key.endswith("_color") and isinstance(value, list):
                deserialized[key] = tuple(value) if value else None
            else:
                deserialized[key] = value
        return deserialized
