"""Pinned Row Manager - Manages blank entry row and FREE CASH summary.

This class encapsulates the logic for managing pinned rows at the top
of the transaction table: the blank entry row (row 0) and the
FREE CASH summary row (row 1).
"""

from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import QComboBox, QLineEdit, QTableWidget, QTableWidgetItem

from app.ui.widgets.common import (
    AutoSelectLineEdit,
    DateInputWidget,
    NoScrollComboBox,
    ValidatedNumericLineEdit,
)

from ..services.portfolio_service import PortfolioService


class PinnedRowManager:
    """
    Manages the blank entry row and FREE CASH summary row.

    The blank row is always at index 0 and provides an entry point
    for new transactions. The FREE CASH summary row is at index 1
    and shows the current cash balance.

    This class handles:
    - Creating and maintaining the blank row
    - Creating and maintaining the FREE CASH summary row
    - Updating FREE CASH calculations
    - Managing visibility of the FREE CASH row
    """

    BLANK_ROW_ID = "BLANK_ROW"
    FREE_CASH_ROW_ID = "FREE_CASH_SUMMARY"
    BLANK_ROW_INDEX = 0
    FREE_CASH_ROW_INDEX = 1

    def __init__(
        self,
        table: QTableWidget,
        widget_style_fn: Callable[[], str],
        combo_style_fn: Callable[[], str],
        set_editable_widget_fn: Callable[[int, int, any], None],
        set_widget_position_fn: Callable[[any, int, int], None],
    ):
        """
        Initialize PinnedRowManager.

        Args:
            table: The table widget to manage
            widget_style_fn: Function that returns current widget stylesheet
            combo_style_fn: Function that returns current combo stylesheet
            set_editable_widget_fn: Function to set editable cell widget
            set_widget_position_fn: Function to set widget position properties
        """
        self._table = table
        self._get_widget_style = widget_style_fn
        self._get_combo_style = combo_style_fn
        self._set_editable_widget = set_editable_widget_fn
        self._set_widget_position = set_widget_position_fn

        self._hide_free_cash = False

    def set_hide_free_cash(self, hidden: bool) -> None:
        """
        Set whether to hide the FREE CASH summary row.

        Args:
            hidden: True to hide, False to show
        """
        self._hide_free_cash = hidden
        if self._table.rowCount() > self.FREE_CASH_ROW_INDEX:
            self._table.setRowHidden(self.FREE_CASH_ROW_INDEX, hidden)

    def is_blank_row(self, row: int) -> bool:
        """Check if row is the blank entry row."""
        return row == self.BLANK_ROW_INDEX

    def is_free_cash_row(self, row: int) -> bool:
        """Check if row is the FREE CASH summary row."""
        return row == self.FREE_CASH_ROW_INDEX

    def is_pinned_row(self, row: int) -> bool:
        """Check if row is a pinned row (blank or FREE CASH)."""
        return row in (self.BLANK_ROW_INDEX, self.FREE_CASH_ROW_INDEX)

    def create_blank_transaction(self) -> Dict[str, Any]:
        """Create a new blank transaction dict."""
        return {
            "id": self.BLANK_ROW_ID,
            "is_blank": True,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "ticker": "",
            "transaction_type": "",
            "quantity": 0.0,
            "entry_price": 0.0,
            "fees": 0.0,
        }

    def create_free_cash_summary_transaction(self) -> Dict[str, Any]:
        """Create a FREE CASH summary transaction dict."""
        return {
            "id": self.FREE_CASH_ROW_ID,
            "is_free_cash_summary": True,
            "date": "",
            "ticker": "FREE CASH",
            "transaction_type": "",
            "quantity": 0.0,
            "entry_price": 0.0,
            "fees": 0.0,
        }

    def create_blank_row_widgets(
        self,
        transaction: Dict[str, Any],
        on_widget_changed: Callable,
        on_date_error: Callable,
    ) -> List[any]:
        """
        Create widgets for the blank entry row.

        Args:
            transaction: The blank transaction dict
            on_widget_changed: Callback for widget value changes
            on_date_error: Callback for date validation errors

        Returns:
            List of created widgets (for focus tracking)
        """
        widget_style = self._get_widget_style()
        combo_style = self._get_combo_style()
        row = self.BLANK_ROW_INDEX
        widgets = []

        # Date cell - column 0
        date_edit = DateInputWidget()
        date_edit.validation_error.connect(on_date_error)
        date_edit.setDate(QDate.fromString(transaction["date"], "yyyy-MM-dd"))
        date_edit.setStyleSheet(widget_style)
        date_edit.date_changed.connect(on_widget_changed)
        self._set_widget_position(date_edit, row, 0)
        self._set_editable_widget(row, 0, date_edit)
        widgets.append(date_edit)

        # Ticker cell - column 1
        ticker_edit = AutoSelectLineEdit(transaction["ticker"])
        ticker_edit.setPlaceholderText("Enter ticker...")
        ticker_edit.setStyleSheet(widget_style)
        ticker_edit.textChanged.connect(on_widget_changed)
        self._set_widget_position(ticker_edit, row, 1)
        self._set_editable_widget(row, 1, ticker_edit)
        widgets.append(ticker_edit)

        # Name cell (read-only) - column 2
        name_edit = AutoSelectLineEdit("")
        name_edit.setReadOnly(True)
        name_edit.setStyleSheet(widget_style)
        self._set_widget_position(name_edit, row, 2)
        self._set_editable_widget(row, 2, name_edit)
        widgets.append(name_edit)

        # Quantity cell - column 3
        qty_edit = ValidatedNumericLineEdit(
            min_value=0.0001, max_value=1000000, decimals=4,
            prefix="", show_dash_for_zero=True
        )
        qty_edit.setValue(transaction["quantity"])
        qty_edit.setStyleSheet(widget_style)
        qty_edit.textChanged.connect(on_widget_changed)
        self._set_widget_position(qty_edit, row, 3)
        self._set_editable_widget(row, 3, qty_edit)
        widgets.append(qty_edit)

        # Execution Price cell - column 4
        price_edit = ValidatedNumericLineEdit(
            min_value=0, max_value=1000000, decimals=2,
            prefix="", show_dash_for_zero=True
        )
        price_edit.setValue(transaction["entry_price"])
        price_edit.setStyleSheet(widget_style)
        price_edit.textChanged.connect(on_widget_changed)
        self._set_widget_position(price_edit, row, 4)
        self._set_editable_widget(row, 4, price_edit)
        widgets.append(price_edit)

        # Fees cell - column 5
        fees_edit = ValidatedNumericLineEdit(
            min_value=0, max_value=10000, decimals=2,
            prefix="", show_dash_for_zero=True
        )
        fees_edit.setValue(transaction["fees"])
        fees_edit.setStyleSheet(widget_style)
        fees_edit.textChanged.connect(on_widget_changed)
        self._set_widget_position(fees_edit, row, 5)
        self._set_editable_widget(row, 5, fees_edit)
        widgets.append(fees_edit)

        # Type cell - column 6
        type_combo = NoScrollComboBox()
        type_combo.addItems(["Buy", "Sell"])
        type_combo.setCurrentIndex(-1)
        type_combo.setPlaceholderText("Buy/Sell")
        type_combo.currentTextChanged.connect(on_widget_changed)
        type_combo.setStyleSheet(combo_style)
        self._set_widget_position(type_combo, row, 6)
        self._set_editable_widget(row, 6, type_combo)
        widgets.append(type_combo)

        # Read-only cells (7-10)
        for col in range(7, 11):
            item = QTableWidgetItem("--")
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self._table.setItem(row, col, item)

        return widgets

    def create_free_cash_summary_row(self) -> None:
        """Create the FREE CASH summary row at index 1."""
        row = self.FREE_CASH_ROW_INDEX

        # All cells are read-only for summary row
        # Column 0: Date (empty)
        date_item = QTableWidgetItem("")
        date_item.setFlags(date_item.flags() & ~Qt.ItemIsEditable)
        self._table.setItem(row, 0, date_item)

        # Column 1: Ticker
        ticker_item = QTableWidgetItem("FREE CASH")
        ticker_item.setFlags(ticker_item.flags() & ~Qt.ItemIsEditable)
        ticker_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._table.setItem(row, 1, ticker_item)

        # Column 2: Name
        name_item = QTableWidgetItem("Cash Balance Summary")
        name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
        name_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._table.setItem(row, 2, name_item)

        # Columns 3-10: Numeric/calculated cells
        for col in range(3, 11):
            item = QTableWidgetItem("--")
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self._table.setItem(row, col, item)

        # Set blank vertical header
        blank_header = QTableWidgetItem("")
        self._table.setVerticalHeaderItem(row, blank_header)

        # Apply hidden state
        self._table.setRowHidden(row, self._hide_free_cash)

    def update_free_cash_summary(
        self,
        transactions: List[Dict[str, Any]],
    ) -> None:
        """
        Update the FREE CASH summary row with calculated values.

        Args:
            transactions: All transactions to calculate from
        """
        if self._table.rowCount() <= self.FREE_CASH_ROW_INDEX:
            return

        # Calculate FREE CASH summary
        summary = PortfolioService.calculate_free_cash_summary(transactions)

        row = self.FREE_CASH_ROW_INDEX

        # Update Quantity (column 3)
        qty_item = self._table.item(row, 3)
        if qty_item:
            total_qty = summary.get("quantity", 0.0)
            qty_item.setText(f"{total_qty:,.4f}" if total_qty else "--")

        # Update Market Value (column 10)
        mv_item = self._table.item(row, 10)
        if mv_item:
            current_balance = summary.get("current_balance", 0.0)
            mv_item.setText(f"${current_balance:,.2f}" if current_balance else "--")
