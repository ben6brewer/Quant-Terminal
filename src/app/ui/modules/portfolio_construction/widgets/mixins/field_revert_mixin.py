"""Field Revert Mixin - Consolidates field revert logic for transaction tables.

This mixin provides a generic field revert system that consolidates
6+ individual revert methods into a single unified implementation.
"""

from typing import Any, Callable, Dict, Optional, Tuple, Type

from PySide6.QtCore import QDate
from PySide6.QtWidgets import QComboBox, QLineEdit, QWidget

from app.ui.widgets.common import DateInputWidget, ValidatedNumericLineEdit


class FieldRevertMixin:
    """
    Mixin for reverting editable fields to original values.

    Provides a generic _revert_field() method that handles different
    widget types and updates both the widget and stored transaction.

    Requirements:
    - Host class must have _get_inner_widget(row, col) method
    - Host class must have _get_transaction_for_row(row) method
    - Host class must have _transactions_by_id dict
    """

    # Field configuration: column -> (field_name, widget_type, setter_method)
    # Subclasses can override this to customize field handling
    REVERT_FIELD_CONFIG: Dict[int, Tuple[str, Type, str]] = {
        0: ("date", DateInputWidget, "setDate"),
        1: ("ticker", QLineEdit, "setText"),
        3: ("quantity", ValidatedNumericLineEdit, "setValue"),
        4: ("entry_price", ValidatedNumericLineEdit, "setValue"),
        5: ("fees", ValidatedNumericLineEdit, "setValue"),
        6: ("transaction_type", QComboBox, "setCurrentText"),
    }

    def _convert_value_for_widget(self, col: int, value: Any) -> Any:
        """
        Convert a value for the appropriate widget type.

        Args:
            col: Column index
            value: Raw value from original data

        Returns:
            Converted value suitable for the widget
        """
        if col == 0:  # Date column - convert string to QDate
            if isinstance(value, str):
                return QDate.fromString(value, "yyyy-MM-dd")
            return value
        return value

    def _revert_field(
        self,
        row: int,
        col: int,
        value: Any,
        field_name: Optional[str] = None,
    ) -> bool:
        """
        Revert a single field to its original value.

        Args:
            row: Row index
            col: Column index
            value: Value to revert to
            field_name: Optional field name (uses config if not provided)

        Returns:
            True if reverted successfully, False otherwise
        """
        # Get field config
        config = self.REVERT_FIELD_CONFIG.get(col)
        if not config and not field_name:
            return False

        if config:
            fname, widget_type, setter_name = config
        else:
            fname = field_name
            widget_type = None
            setter_name = None

        # Use provided field_name if given
        if field_name:
            fname = field_name

        # Get and update widget
        inner_widget = self._get_inner_widget(row, col)
        if inner_widget:
            # Convert value for widget if needed
            converted_value = self._convert_value_for_widget(col, value)

            # Block signals and set value
            inner_widget.blockSignals(True)
            try:
                if setter_name and hasattr(inner_widget, setter_name):
                    getattr(inner_widget, setter_name)(converted_value)
                elif hasattr(inner_widget, "setText"):
                    inner_widget.setText(str(value))
                elif hasattr(inner_widget, "setValue"):
                    inner_widget.setValue(value)
            finally:
                inner_widget.blockSignals(False)

        # Update stored transaction
        transaction = self._get_transaction_for_row(row)
        if transaction:
            transaction[fname] = value
            tx_id = transaction.get("id")
            if tx_id and hasattr(self, "_transactions_by_id"):
                if tx_id in self._transactions_by_id:
                    self._transactions_by_id[tx_id][fname] = value

        return True

    def _revert_all_fields(self, row: int, original: Dict[str, Any]) -> None:
        """
        Revert all editable fields to original values.

        Args:
            row: Row index
            original: Dict with original values for all fields
        """
        if not original:
            return

        # Map field names to columns
        field_to_col = {
            "date": 0,
            "ticker": 1,
            "quantity": 3,
            "entry_price": 4,
            "fees": 5,
            "transaction_type": 6,
        }

        for field_name, col in field_to_col.items():
            if field_name in original:
                self._revert_field(row, col, original[field_name], field_name)

    # Convenience methods for backwards compatibility
    def _revert_ticker(self, row: int, original_ticker: str) -> None:
        """Revert ticker field to original value."""
        self._revert_field(row, 1, original_ticker, "ticker")

    def _revert_date(self, row: int, original_date: str) -> None:
        """Revert date field to original value."""
        self._revert_field(row, 0, original_date, "date")

    def _revert_quantity(self, row: int, original_quantity: float) -> None:
        """Revert quantity field to original value."""
        self._revert_field(row, 3, original_quantity, "quantity")

    def _revert_entry_price(self, row: int, original_price: float) -> None:
        """Revert entry price field to original value."""
        self._revert_field(row, 4, original_price, "entry_price")

    def _revert_fees(self, row: int, original_fees: float) -> None:
        """Revert fees field to original value."""
        self._revert_field(row, 5, original_fees, "fees")

    def _revert_transaction_type(self, row: int, original_type: str) -> None:
        """Revert transaction type field to original value."""
        self._revert_field(row, 6, original_type, "transaction_type")
