"""Sorting Mixin - Consolidates sorting logic for transaction tables.

This mixin provides generic sorting infrastructure including:
- Binary search insertion for sorted tables
- Table rebuild from sorted transaction list
- Custom sort key generation
"""

from typing import Any, Callable, Dict, List, Optional, Tuple

from PySide6.QtCore import Qt

from ...services.portfolio_service import PortfolioService


class SortingMixin:
    """
    Mixin for table sorting with pinned rows.

    Provides:
    - Binary search for O(log n) insertion position finding
    - Table rebuild from sorted transaction list
    - Sort key generation for transaction ordering

    Requirements:
    - Host class must have rowCount() method
    - Host class must have _get_transaction_for_row(row) method
    - Host class must have add_transaction_row(tx) method
    - Host class must have _ensure_blank_row() method
    - Host class must have _update_calculated_cells(row) method
    - Host class must have _update_free_cash_summary_row() method
    - Host class must have _reset_column_widths() method
    """

    # Number of pinned rows at the top (blank row + FREE CASH summary)
    PINNED_ROW_COUNT = 2

    def _get_transaction_sort_key(
        self,
        tx: Dict[str, Any],
        descending: bool = True,
    ) -> Tuple:
        """
        Generate sort key for a transaction.

        Sort order:
        - Date (descending = most recent first)
        - Priority (ascending within same date)
        - Sequence (ascending within same date and priority)

        Args:
            tx: Transaction dict
            descending: If True, returns key for descending date order

        Returns:
            Sort key tuple
        """
        date = tx.get("date", "")
        ticker = tx.get("ticker", "")
        tx_type = tx.get("transaction_type", "Buy")
        priority = PortfolioService.get_transaction_priority(ticker, tx_type)
        sequence = tx.get("sequence", 0)

        # Negate priority and sequence to get ascending order
        # while date can be either ascending or descending
        return (date, -priority, -sequence)

    def _find_insertion_position(self, transaction: Dict[str, Any]) -> int:
        """
        Find the correct insertion position for a new transaction using binary search.

        The table is sorted by date descending, then priority ascending, then sequence ascending.

        Args:
            transaction: Transaction dict with date, ticker, transaction_type, sequence

        Returns:
            Row index for insertion (minimum PINNED_ROW_COUNT)
        """
        new_key = self._get_transaction_sort_key(transaction, descending=True)

        # Binary search on rows after pinned rows
        left = self.PINNED_ROW_COUNT
        right = self.rowCount()

        while left < right:
            mid = (left + right) // 2

            mid_tx = self._get_transaction_for_row(mid)
            if mid_tx:
                mid_key = self._get_transaction_sort_key(mid_tx, descending=True)

                # For descending order: if new_key > mid_key, insert before mid
                if new_key > mid_key:
                    right = mid
                else:
                    left = mid + 1
            else:
                left = mid + 1

        return left

    def _sort_transactions_by_key(
        self,
        transactions: List[Dict[str, Any]],
        key_fn: Optional[Callable[[Dict[str, Any]], Any]] = None,
        reverse: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Sort a list of transactions.

        Args:
            transactions: List of transaction dicts
            key_fn: Optional custom sort key function
            reverse: If True, sort descending

        Returns:
            Sorted list of transactions
        """
        if key_fn is None:
            key_fn = lambda tx: self._get_transaction_sort_key(tx, descending=reverse)

        return sorted(transactions, key=key_fn, reverse=reverse)

    def _collect_sortable_transactions(
        self,
        extract_fn: Optional[Callable[[int], Optional[Dict[str, Any]]]] = None,
    ) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """
        Collect all sortable transactions from the table.

        Excludes blank row and FREE CASH summary.

        Args:
            extract_fn: Optional function to extract transaction from row.
                       Defaults to self._extract_transaction_from_row if available.

        Returns:
            Tuple of (sortable_transactions list, blank_transaction or None)
        """
        if extract_fn is None:
            if hasattr(self, "_extract_transaction_from_row"):
                extract_fn = self._extract_transaction_from_row
            else:
                return [], None

        sortable_transactions = []
        blank_transaction = None

        for row in range(self.rowCount()):
            tx = extract_fn(row)
            if tx:
                if tx.get("is_blank"):
                    blank_transaction = tx
                elif tx.get("is_free_cash_summary"):
                    pass  # Skip - will be recreated
                else:
                    sortable_transactions.append(tx)

        return sortable_transactions, blank_transaction

    def _rebuild_table_with_transactions(
        self,
        sorted_transactions: List[Dict[str, Any]],
        blank_transaction: Optional[Dict[str, Any]] = None,
        update_calculated: bool = True,
    ) -> None:
        """
        Rebuild the table from a sorted list of transactions.

        Args:
            sorted_transactions: List of transactions in desired order
            blank_transaction: Optional blank row transaction to restore
            update_calculated: Whether to update calculated cells after rebuild
        """
        # Clear table
        self.setRowCount(0)

        # Clear all mappings
        if hasattr(self, "_transactions_by_id"):
            self._transactions_by_id.clear()
        if hasattr(self, "_row_to_id"):
            self._row_to_id.clear()
        if hasattr(self, "_transactions"):
            self._transactions.clear()
        if hasattr(self, "_row_widgets_map"):
            self._row_widgets_map.clear()

        # Add blank row first (also creates FREE CASH summary at row 1)
        if blank_transaction and hasattr(self, "_ensure_blank_row"):
            self._ensure_blank_row()

        # Add sorted transactions using batch mode if available
        if hasattr(self, "_batch_loading"):
            self._batch_loading = True

        for tx in sorted_transactions:
            if hasattr(self, "add_transaction_row"):
                self.add_transaction_row(tx)

        if hasattr(self, "_batch_loading"):
            self._batch_loading = False

        # Update calculated cells
        if update_calculated and hasattr(self, "_update_calculated_cells"):
            for row in range(self.rowCount()):
                self._update_calculated_cells(row)

        # Update FREE CASH summary
        if hasattr(self, "_update_free_cash_summary_row"):
            self._update_free_cash_summary_row()

        # Reset column widths
        if hasattr(self, "_reset_column_widths"):
            self._reset_column_widths()

    def _update_sort_indicator(
        self,
        column: int,
        order: Qt.SortOrder,
    ) -> None:
        """
        Update the sort indicator on the header.

        Args:
            column: Column index
            order: Sort order (Qt.AscendingOrder or Qt.DescendingOrder)
        """
        if hasattr(self, "_current_sort_column"):
            self._current_sort_column = column
        if hasattr(self, "_current_sort_order"):
            self._current_sort_order = order

        header = self.horizontalHeader()
        header.setSortIndicator(column, order)
