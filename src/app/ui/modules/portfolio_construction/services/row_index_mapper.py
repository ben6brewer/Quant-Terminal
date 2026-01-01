"""Row Index Mapper - Manages bidirectional row-to-data mapping.

This service provides a unified API for managing the complex mapping between
table row indices, transaction IDs, transaction data, and row widgets.
It handles atomic shift operations for insert/delete to keep all maps in sync.
"""

from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple

from PySide6.QtWidgets import QWidget


class RowIndexMapper:
    """
    Manages bidirectional mapping between row indices and transaction data.

    Maintains three parallel data structures:
    - id_to_data: transaction_id -> transaction_dict
    - row_to_id: row_index -> transaction_id
    - row_widgets: row_index -> list of widgets in that row

    Provides atomic shift operations to keep all maps consistent
    during insert/delete operations.
    """

    def __init__(self):
        self._id_to_data: Dict[str, Dict[str, Any]] = {}
        self._row_to_id: Dict[int, str] = {}
        self._row_widgets: Dict[int, List[QWidget]] = {}
        self._original_values: Dict[str, Dict[str, Any]] = {}

    def clear(self) -> None:
        """Clear all mappings."""
        self._id_to_data.clear()
        self._row_to_id.clear()
        self._row_widgets.clear()
        self._original_values.clear()

    # -------------------------------------------------------------------------
    # Basic CRUD Operations
    # -------------------------------------------------------------------------

    def add(
        self,
        row: int,
        tx_id: str,
        data: Dict[str, Any],
        original_values: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Add a mapping for a row.

        Args:
            row: Row index
            tx_id: Transaction ID (UUID)
            data: Transaction data dict
            original_values: Optional original values for revert functionality
        """
        self._id_to_data[tx_id] = data
        self._row_to_id[row] = tx_id

        if original_values is not None:
            self._original_values[tx_id] = original_values

    def remove_by_row(self, row: int) -> Optional[str]:
        """
        Remove mapping for a row.

        Args:
            row: Row index to remove

        Returns:
            Transaction ID that was removed, or None if not found
        """
        tx_id = self._row_to_id.pop(row, None)
        if tx_id:
            self._id_to_data.pop(tx_id, None)
            self._original_values.pop(tx_id, None)
        self._row_widgets.pop(row, None)
        return tx_id

    def remove_by_id(self, tx_id: str) -> Optional[int]:
        """
        Remove mapping for a transaction ID.

        Args:
            tx_id: Transaction ID to remove

        Returns:
            Row index that was removed, or None if not found
        """
        self._id_to_data.pop(tx_id, None)
        self._original_values.pop(tx_id, None)

        # Find and remove row mapping
        for row, rid in list(self._row_to_id.items()):
            if rid == tx_id:
                del self._row_to_id[row]
                self._row_widgets.pop(row, None)
                return row
        return None

    def get_by_row(self, row: int) -> Optional[Dict[str, Any]]:
        """
        Get transaction data for a row.

        Args:
            row: Row index

        Returns:
            Transaction data dict, or None if not found
        """
        tx_id = self._row_to_id.get(row)
        if tx_id:
            return self._id_to_data.get(tx_id)
        return None

    def get_by_id(self, tx_id: str) -> Optional[Dict[str, Any]]:
        """
        Get transaction data for a transaction ID.

        Args:
            tx_id: Transaction ID

        Returns:
            Transaction data dict, or None if not found
        """
        return self._id_to_data.get(tx_id)

    def get_row_for_id(self, tx_id: str) -> Optional[int]:
        """
        Get row index for a transaction ID.

        Args:
            tx_id: Transaction ID

        Returns:
            Row index, or None if not found
        """
        for row, rid in self._row_to_id.items():
            if rid == tx_id:
                return row
        return None

    def get_id_for_row(self, row: int) -> Optional[str]:
        """
        Get transaction ID for a row.

        Args:
            row: Row index

        Returns:
            Transaction ID, or None if not found
        """
        return self._row_to_id.get(row)

    def update_data(self, tx_id: str, data: Dict[str, Any]) -> bool:
        """
        Update transaction data for an existing ID.

        Args:
            tx_id: Transaction ID
            data: New transaction data

        Returns:
            True if updated, False if ID not found
        """
        if tx_id in self._id_to_data:
            self._id_to_data[tx_id] = data
            return True
        return False

    def update_data_by_row(self, row: int, data: Dict[str, Any]) -> bool:
        """
        Update transaction data for a row.

        Args:
            row: Row index
            data: New transaction data

        Returns:
            True if updated, False if row not found
        """
        tx_id = self._row_to_id.get(row)
        if tx_id:
            self._id_to_data[tx_id] = data
            return True
        return False

    # -------------------------------------------------------------------------
    # Original Values (for revert functionality)
    # -------------------------------------------------------------------------

    def set_original_values(self, tx_id: str, values: Dict[str, Any]) -> None:
        """
        Set original values for a transaction (for revert on validation failure).

        Args:
            tx_id: Transaction ID
            values: Original field values
        """
        self._original_values[tx_id] = values

    def get_original_values(self, tx_id: str) -> Optional[Dict[str, Any]]:
        """
        Get original values for a transaction.

        Args:
            tx_id: Transaction ID

        Returns:
            Original values dict, or None if not found
        """
        return self._original_values.get(tx_id)

    def get_original_values_by_row(self, row: int) -> Optional[Dict[str, Any]]:
        """
        Get original values for a row.

        Args:
            row: Row index

        Returns:
            Original values dict, or None if not found
        """
        tx_id = self._row_to_id.get(row)
        if tx_id:
            return self._original_values.get(tx_id)
        return None

    # -------------------------------------------------------------------------
    # Widget Tracking
    # -------------------------------------------------------------------------

    def set_row_widgets(self, row: int, widgets: List[QWidget]) -> None:
        """
        Set widgets for a row.

        Args:
            row: Row index
            widgets: List of widgets in the row
        """
        self._row_widgets[row] = widgets

    def get_row_widgets(self, row: int) -> List[QWidget]:
        """
        Get widgets for a row.

        Args:
            row: Row index

        Returns:
            List of widgets, or empty list if not found
        """
        return self._row_widgets.get(row, [])

    def add_widget_to_row(self, row: int, widget: QWidget) -> None:
        """
        Add a widget to a row's widget list.

        Args:
            row: Row index
            widget: Widget to add
        """
        if row not in self._row_widgets:
            self._row_widgets[row] = []
        self._row_widgets[row].append(widget)

    # -------------------------------------------------------------------------
    # Bulk Shift Operations
    # -------------------------------------------------------------------------

    def shift_rows_down(self, from_row: int, count: int = 1) -> None:
        """
        Shift all rows >= from_row down by count.
        Used when inserting rows.

        Args:
            from_row: First row to shift
            count: Number of positions to shift down
        """
        # Build new mappings
        new_row_to_id: Dict[int, str] = {}
        new_row_widgets: Dict[int, List[QWidget]] = {}

        for old_row in sorted(self._row_to_id.keys(), reverse=True):
            if old_row >= from_row:
                new_row = old_row + count
            else:
                new_row = old_row

            new_row_to_id[new_row] = self._row_to_id[old_row]

            if old_row in self._row_widgets:
                new_row_widgets[new_row] = self._row_widgets[old_row]

        self._row_to_id = new_row_to_id
        self._row_widgets = new_row_widgets

    def shift_rows_up(self, from_row: int, count: int = 1) -> None:
        """
        Shift all rows > from_row up by count.
        Used when deleting rows.

        Args:
            from_row: Row that was deleted (rows above this shift up)
            count: Number of positions to shift up
        """
        # Build new mappings
        new_row_to_id: Dict[int, str] = {}
        new_row_widgets: Dict[int, List[QWidget]] = {}

        for old_row in sorted(self._row_to_id.keys()):
            if old_row > from_row:
                new_row = old_row - count
            elif old_row < from_row:
                new_row = old_row
            else:
                continue  # Skip the deleted row

            new_row_to_id[new_row] = self._row_to_id[old_row]

            if old_row in self._row_widgets:
                new_row_widgets[new_row] = self._row_widgets[old_row]

        self._row_to_id = new_row_to_id
        self._row_widgets = new_row_widgets

    def rebuild_from_list(
        self,
        transactions: List[Dict[str, Any]],
        start_row: int = 0,
        id_field: str = "id",
    ) -> None:
        """
        Rebuild mappings from a list of transactions.

        Args:
            transactions: List of transaction dicts (in row order)
            start_row: First row index (default 0)
            id_field: Field name for transaction ID
        """
        self.clear()
        for i, tx in enumerate(transactions):
            row = start_row + i
            tx_id = tx.get(id_field)
            if tx_id:
                self.add(row, tx_id, tx)

    # -------------------------------------------------------------------------
    # Iteration & Queries
    # -------------------------------------------------------------------------

    def rows(self) -> Iterator[int]:
        """Iterate over all mapped row indices."""
        return iter(sorted(self._row_to_id.keys()))

    def ids(self) -> Iterator[str]:
        """Iterate over all transaction IDs."""
        return iter(self._id_to_data.keys())

    def items(self) -> Iterator[Tuple[int, str, Dict[str, Any]]]:
        """
        Iterate over all mappings as (row, tx_id, data) tuples.
        Sorted by row index.
        """
        for row in sorted(self._row_to_id.keys()):
            tx_id = self._row_to_id[row]
            data = self._id_to_data.get(tx_id, {})
            yield row, tx_id, data

    def all_data(self) -> List[Dict[str, Any]]:
        """
        Get all transaction data as a list, sorted by row index.

        Returns:
            List of transaction dicts
        """
        result = []
        for row in sorted(self._row_to_id.keys()):
            tx_id = self._row_to_id[row]
            if tx_id in self._id_to_data:
                result.append(self._id_to_data[tx_id])
        return result

    def row_count(self) -> int:
        """Get number of mapped rows."""
        return len(self._row_to_id)

    def has_row(self, row: int) -> bool:
        """Check if row is mapped."""
        return row in self._row_to_id

    def has_id(self, tx_id: str) -> bool:
        """Check if transaction ID is mapped."""
        return tx_id in self._id_to_data

    # -------------------------------------------------------------------------
    # Special Row Types
    # -------------------------------------------------------------------------

    def is_blank_row(self, row: int) -> bool:
        """Check if row is the blank entry row."""
        data = self.get_by_row(row)
        return data is not None and data.get("is_blank", False)

    def is_free_cash_summary(self, row: int) -> bool:
        """Check if row is the FREE CASH summary row."""
        data = self.get_by_row(row)
        return data is not None and data.get("is_free_cash_summary", False)

    def is_pinned_row(self, row: int) -> bool:
        """Check if row is pinned (blank or FREE CASH summary)."""
        return self.is_blank_row(row) or self.is_free_cash_summary(row)

    def get_regular_transactions(self) -> List[Dict[str, Any]]:
        """
        Get all non-pinned transactions (excludes blank row and FREE CASH summary).

        Returns:
            List of regular transaction dicts
        """
        result = []
        for row in sorted(self._row_to_id.keys()):
            if not self.is_pinned_row(row):
                tx_id = self._row_to_id[row]
                if tx_id in self._id_to_data:
                    result.append(self._id_to_data[tx_id])
        return result
