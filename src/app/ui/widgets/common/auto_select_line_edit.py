"""Auto-Select Line Edit - QLineEdit with auto-select and auto-capitalize."""

from PySide6.QtWidgets import QLineEdit


class AutoSelectLineEdit(QLineEdit):
    """QLineEdit that auto-selects all text on focus or click and auto-capitalizes.

    Useful for ticker symbol input where:
    - Text should be selected on focus for easy replacement
    - Input should be automatically uppercased
    """

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        # Connect to textEdited to auto-capitalize (textEdited only fires on user input)
        self.textEdited.connect(self._on_text_edited)

    def _on_text_edited(self, text: str):
        """Convert text to uppercase while preserving cursor position."""
        if text != text.upper():
            cursor_pos = self.cursorPosition()
            self.blockSignals(True)
            self.setText(text.upper())
            self.setCursorPosition(cursor_pos)
            self.blockSignals(False)
            # Emit textChanged manually since we blocked signals
            self.textChanged.emit(self.text())

    def focusInEvent(self, event):
        super().focusInEvent(event)
        # Select all text so typing replaces it
        self.selectAll()

    def mousePressEvent(self, event):
        # Select all text when clicked (whether already focused or not)
        super().mousePressEvent(event)
        self.selectAll()
