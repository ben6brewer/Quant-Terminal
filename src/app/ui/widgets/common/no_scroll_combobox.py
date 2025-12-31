"""No-Scroll ComboBox - Prevents wheel scrolling from changing selection."""

from PySide6.QtWidgets import QComboBox


class NoScrollComboBox(QComboBox):
    """QComboBox that ignores wheel events to prevent accidental changes.

    Useful in table cells where scrolling should scroll the table,
    not change the combo box value.
    """

    def wheelEvent(self, event):
        """Ignore wheel events - do not change selection."""
        event.ignore()  # Propagate to parent (table scrolling)
