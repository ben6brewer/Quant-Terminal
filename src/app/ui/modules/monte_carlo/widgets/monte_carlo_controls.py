"""Monte Carlo Controls - Helper widgets for Monte Carlo toolbar."""

from typing import Optional
from PySide6.QtWidgets import (
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QMessageBox,
)
from PySide6.QtCore import QDate
from PySide6.QtGui import QWheelEvent

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common import (
    ThemedDialog,
    DateInputWidget,
    NoScrollComboBox,
)


class HorizonComboBox(NoScrollComboBox):
    """ComboBox for horizon selection with custom value display.

    Shows 'x.xx Years' when custom is selected, but reverts to 'Custom'
    in the dropdown so user can click to edit.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._custom_years_text: Optional[str] = None  # e.g., "1.38 Years"
        self._custom_label = "Custom"

    def set_custom_years(self, years: float):
        """Set the custom years value to display."""
        self._custom_years_text = f"{years:.2f} Years"
        # Update the item text to show years
        last_idx = self.count() - 1
        self.setItemText(last_idx, self._custom_years_text)

    def clear_custom_years(self):
        """Clear the custom years display, revert to 'Custom'."""
        self._custom_years_text = None
        last_idx = self.count() - 1
        self.setItemText(last_idx, self._custom_label)

    def showPopup(self):
        """Before showing popup, temporarily show 'Custom' text."""
        if self._custom_years_text:
            last_idx = self.count() - 1
            self.setItemText(last_idx, self._custom_label)
        super().showPopup()

    def hidePopup(self):
        """After hiding popup, restore the years text if custom is selected."""
        super().hidePopup()
        if self._custom_years_text and self.currentData() == -1:
            last_idx = self.count() - 1
            self.setItemText(last_idx, self._custom_years_text)


class NoScrollSpinBox(QSpinBox):
    """SpinBox that ignores scroll wheel events."""

    def wheelEvent(self, event: QWheelEvent):
        event.ignore()


class FutureDateInputWidget(DateInputWidget):
    """DateInputWidget that allows future dates (for Monte Carlo horizon)."""

    def _trigger_validation(self) -> bool:
        """Override to allow future dates and require date > today."""
        current = self.text()

        # Empty field is allowed (no error)
        if not current:
            self._current_date = None
            return True

        # Extract digits
        digits = current.replace("-", "")

        # Incomplete date (less than 8 digits)
        if len(digits) < 8:
            self.validation_error.emit(
                "Incomplete Date",
                f"Please enter a complete date in YYYY-MM-DD format.\nCurrent input: {current}"
            )
            self.setFocus()
            self.selectAll()
            return False

        # Parse as QDate
        parsed_date = QDate.fromString(current, "yyyy-MM-dd")

        if not parsed_date.isValid():
            self.validation_error.emit(
                "Invalid Date",
                f"The date '{current}' is not valid.\nPlease check the month and day values."
            )
            self.setFocus()
            self.selectAll()
            return False

        # Check date is AFTER today (opposite of transaction date validation)
        if parsed_date <= QDate.currentDate():
            self.validation_error.emit(
                "Date Must Be In Future",
                f"End date must be after today ({QDate.currentDate().toString('yyyy-MM-dd')})."
            )
            self.setFocus()
            self.selectAll()
            return False

        # Valid date - store and emit signal
        self._current_date = parsed_date
        self.date_changed.emit(parsed_date)
        return True


class CustomHorizonDialog(ThemedDialog):
    """Dialog for selecting a custom end date for Monte Carlo simulation horizon."""

    def __init__(self, theme_manager: ThemeManager, parent=None):
        self._end_date: Optional[QDate] = None
        super().__init__(theme_manager, "Custom Horizon", parent, min_width=350)

    def _setup_content(self, layout: QVBoxLayout):
        """Setup dialog content."""
        # Description
        desc_label = QLabel("Enter the end date for the simulation horizon:")
        desc_label.setWordWrap(True)
        desc_label.setObjectName("description_label")
        layout.addWidget(desc_label)

        # Date input row
        date_row = QHBoxLayout()
        date_row.setSpacing(10)

        date_label = QLabel("End Date:")
        date_label.setObjectName("field_label")
        date_row.addWidget(date_label)

        self.date_input = FutureDateInputWidget()
        self.date_input.setFixedWidth(150)
        self.date_input.setFixedHeight(36)
        self.date_input.validation_error.connect(self._show_validation_error)
        date_row.addWidget(self.date_input)

        date_row.addStretch()
        layout.addLayout(date_row)

        # Info label
        info_label = QLabel("Date must be after today. Trading days will be calculated automatically.")
        info_label.setObjectName("noteLabel")
        layout.addWidget(info_label)

        layout.addStretch()

        # Button row
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedSize(100, 36)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        ok_btn = QPushButton("OK")
        ok_btn.setFixedSize(100, 36)
        ok_btn.setObjectName("defaultButton")
        ok_btn.clicked.connect(self._on_ok_clicked)
        btn_row.addWidget(ok_btn)

        layout.addLayout(btn_row)

    def _show_validation_error(self, title: str, message: str):
        """Show validation error from DateInputWidget."""
        QMessageBox.warning(self, title, message)

    def _on_ok_clicked(self):
        """Handle OK button click with validation."""
        date_text = self.date_input.text().strip()

        if not date_text:
            QMessageBox.warning(self, "Date Required", "Please enter an end date.")
            self.date_input.setFocus()
            return

        # Parse the date
        parsed_date = QDate.fromString(date_text, "yyyy-MM-dd")
        if not parsed_date.isValid():
            QMessageBox.warning(
                self, "Invalid Date",
                f"The date '{date_text}' is not valid.\nPlease use YYYY-MM-DD format."
            )
            self.date_input.setFocus()
            self.date_input.selectAll()
            return

        # Check that date is after today
        today = QDate.currentDate()
        if parsed_date <= today:
            QMessageBox.warning(
                self, "Invalid Date",
                f"End date must be after today ({today.toString('yyyy-MM-dd')})."
            )
            self.date_input.setFocus()
            self.date_input.selectAll()
            return

        self._end_date = parsed_date
        self.accept()

    def get_end_date(self) -> Optional[QDate]:
        """Get the selected end date."""
        return self._end_date


