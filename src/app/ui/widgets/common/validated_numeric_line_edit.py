"""Validated Numeric Line Edit - QLineEdit with numeric validation and formatting."""

from PySide6.QtWidgets import QLineEdit
from PySide6.QtCore import Qt
from PySide6.QtGui import QDoubleValidator


class ValidatedNumericLineEdit(QLineEdit):
    """QLineEdit with numeric validation, optional prefix, and formatting.

    Features:
    - Double validation with min/max bounds
    - Optional prefix (e.g., "$" for currency)
    - Optional dash display for zero values
    - Auto-select on focus
    - Smart formatting on focus out

    Args:
        min_value: Minimum allowed value
        max_value: Maximum allowed value
        decimals: Number of decimal places
        prefix: Optional prefix string (e.g., "$")
        show_dash_for_zero: If True, display "--" for zero values
        parent: Parent widget
    """

    def __init__(
        self,
        min_value: float = 0.0,
        max_value: float = 1000000.0,
        decimals: int = 2,
        prefix: str = "",
        show_dash_for_zero: bool = False,
        parent=None
    ):
        super().__init__(parent)
        self.prefix = prefix
        self.decimals = decimals
        self.show_dash_for_zero = show_dash_for_zero

        self.validator = QDoubleValidator(min_value, max_value, decimals, self)
        self.validator.setNotation(QDoubleValidator.StandardNotation)
        self.setValidator(self.validator)
        self.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        if prefix:
            self.setPlaceholderText(f"{prefix}0.00")

    def value(self) -> float:
        """Get the numeric value."""
        text = self.text().replace(self.prefix, "").strip()
        if text == "--":
            return 0.0
        try:
            return float(text)
        except ValueError:
            return 0.0

    def setValue(self, value: float):
        """Set the numeric value with formatting."""
        # Show '--' for zero if enabled
        if self.show_dash_for_zero and value == 0.0:
            self.setText("--")
            return

        # Format with specified decimals, then strip trailing zeros
        formatted = f"{value:.{self.decimals}f}"
        # Remove trailing zeros and trailing decimal point
        formatted = formatted.rstrip('0').rstrip('.')

        self.setText(f"{self.prefix}{formatted}" if self.prefix else formatted)

    def focusInEvent(self, event):
        super().focusInEvent(event)
        # Select all text so typing replaces it
        self.selectAll()

    def mousePressEvent(self, event):
        # Select all text when clicked (whether already focused or not)
        super().mousePressEvent(event)
        self.selectAll()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        text = self.text().strip()

        # Handle '--' display for zero
        if text == "--" or not text:
            if self.show_dash_for_zero:
                self.setText("--")
            else:
                formatted = "0"
                self.setText(f"{self.prefix}{formatted}" if self.prefix else formatted)
        else:
            # Remove prefix for validation
            if self.prefix and text.startswith(self.prefix):
                text = text.replace(self.prefix, "").strip()

            try:
                self.setValue(float(text))
            except ValueError:
                if self.show_dash_for_zero:
                    self.setText("--")
                else:
                    self.setText(f"{self.prefix}0" if self.prefix else "0")
