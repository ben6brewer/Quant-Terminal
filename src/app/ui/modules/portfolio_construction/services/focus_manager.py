"""Focus Manager - Focus tracking and deferred validation for editable tables.

This service handles focus tracking, tab navigation, and deferred focus
loss detection with generation counters to avoid stale callbacks.
"""

from typing import Callable, Dict, List, Optional, Tuple

from PySide6.QtCore import QEvent, QObject, Qt, QTimer, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QTableWidget, QWidget


class FocusManager(QObject):
    """
    Manages focus tracking and deferred validation for editable tables.

    Features:
    - Event filter installation on row widgets
    - Current editing row tracking
    - Focus generation counter to invalidate stale callbacks
    - Deferred focus loss detection
    - Tab/Enter key navigation handling
    - Skip validation flag for manual control
    """

    # Signals
    row_focus_entered = Signal(int)  # Emitted when focus enters a row
    row_focus_lost = Signal(int)  # Emitted when focus leaves a row
    enter_pressed = Signal(int)  # Emitted when Enter pressed on a row
    tab_navigation = Signal(int, int, bool)  # (row, col, forward) - request to move focus

    def __init__(
        self,
        table: QTableWidget,
        editable_columns: List[int],
        skip_columns: Optional[List[int]] = None,
        parent: Optional[QObject] = None,
    ):
        """
        Initialize FocusManager.

        Args:
            table: The table widget to manage
            editable_columns: List of column indices that are editable
            skip_columns: Columns to skip during tab navigation (e.g., read-only)
            parent: Parent QObject
        """
        super().__init__(parent)
        self._table = table
        self._editable_columns = editable_columns
        self._skip_columns = skip_columns or []

        self._current_editing_row: Optional[int] = None
        self._focus_generation: int = 0
        self._skip_validation: bool = False
        self._validating: bool = False

        # Widget to (row, col) mapping for reverse lookup
        self._widget_to_cell: Dict[int, Tuple[int, int]] = {}

        # Callback for finding row from widget (provided by table)
        self._find_row_fn: Optional[Callable[[QWidget], Optional[int]]] = None
        self._find_cell_fn: Optional[Callable[[QWidget], Tuple[Optional[int], Optional[int]]]] = None

    # -------------------------------------------------------------------------
    # Configuration
    # -------------------------------------------------------------------------

    def set_find_row_callback(
        self,
        find_row_fn: Callable[[QWidget], Optional[int]],
    ) -> None:
        """
        Set callback for finding row index from widget.

        Args:
            find_row_fn: Function that takes a widget and returns row index or None
        """
        self._find_row_fn = find_row_fn

    def set_find_cell_callback(
        self,
        find_cell_fn: Callable[[QWidget], Tuple[Optional[int], Optional[int]]],
    ) -> None:
        """
        Set callback for finding (row, col) from widget.

        Args:
            find_cell_fn: Function that takes a widget and returns (row, col) tuple
        """
        self._find_cell_fn = find_cell_fn

    # -------------------------------------------------------------------------
    # State Management
    # -------------------------------------------------------------------------

    @property
    def current_editing_row(self) -> Optional[int]:
        """Get the currently editing row."""
        return self._current_editing_row

    @property
    def focus_generation(self) -> int:
        """Get the current focus generation counter."""
        return self._focus_generation

    def invalidate_pending_callbacks(self) -> None:
        """
        Increment focus generation to invalidate any pending deferred callbacks.
        Call this after sorts, successful edits, or other operations that
        change the table state.
        """
        self._focus_generation += 1

    def set_skip_validation(self, skip: bool) -> None:
        """
        Set flag to skip validation on next focus loss.
        Used when validation is handled elsewhere (e.g., Enter key).

        Args:
            skip: Whether to skip validation
        """
        self._skip_validation = skip

    def set_validating(self, validating: bool) -> None:
        """
        Set flag indicating validation is in progress.
        Prevents interference from focus callbacks during validation.

        Args:
            validating: Whether validation is in progress
        """
        self._validating = validating

    def clear_current_row(self) -> None:
        """Clear the current editing row tracking."""
        self._current_editing_row = None

    # -------------------------------------------------------------------------
    # Event Filter Installation
    # -------------------------------------------------------------------------

    def install_on_widget(self, widget: QWidget, row: int, col: int) -> None:
        """
        Install event filter on a widget.

        Args:
            widget: Widget to install filter on
            row: Row index
            col: Column index
        """
        widget.installEventFilter(self)
        self._widget_to_cell[id(widget)] = (row, col)

    def install_on_widgets(self, widgets: List[QWidget], row: int) -> None:
        """
        Install event filter on multiple widgets in a row.

        Args:
            widgets: List of widgets (one per editable column)
            row: Row index
        """
        for i, widget in enumerate(widgets):
            if i < len(self._editable_columns):
                col = self._editable_columns[i]
                self.install_on_widget(widget, row, col)

    def remove_widget(self, widget: QWidget) -> None:
        """
        Remove event filter from a widget.

        Args:
            widget: Widget to remove filter from
        """
        widget.removeEventFilter(self)
        self._widget_to_cell.pop(id(widget), None)

    def update_widget_row(self, widget: QWidget, new_row: int) -> None:
        """
        Update the row for a widget (after row shifts).

        Args:
            widget: Widget to update
            new_row: New row index
        """
        widget_id = id(widget)
        if widget_id in self._widget_to_cell:
            _, col = self._widget_to_cell[widget_id]
            self._widget_to_cell[widget_id] = (new_row, col)

    # -------------------------------------------------------------------------
    # Widget Lookup
    # -------------------------------------------------------------------------

    def find_row_for_widget(self, widget: QWidget) -> Optional[int]:
        """
        Find row index for a widget.

        Args:
            widget: Widget to find

        Returns:
            Row index or None
        """
        # Try internal mapping first
        cell = self._widget_to_cell.get(id(widget))
        if cell:
            return cell[0]

        # Fall back to callback
        if self._find_row_fn:
            return self._find_row_fn(widget)

        return None

    def find_cell_for_widget(self, widget: QWidget) -> Tuple[Optional[int], Optional[int]]:
        """
        Find (row, col) for a widget.

        Args:
            widget: Widget to find

        Returns:
            (row, col) tuple or (None, None)
        """
        # Try internal mapping first
        cell = self._widget_to_cell.get(id(widget))
        if cell:
            return cell

        # Fall back to callback
        if self._find_cell_fn:
            return self._find_cell_fn(widget)

        return None, None

    # -------------------------------------------------------------------------
    # Event Filter
    # -------------------------------------------------------------------------

    def eventFilter(self, obj: QWidget, event: QEvent) -> bool:
        """
        Handle focus and key events on widgets.

        Args:
            obj: Widget that received event
            event: The event

        Returns:
            True to consume event, False to pass through
        """
        event_type = event.type()

        if event_type == QEvent.FocusIn:
            return self._handle_focus_in(obj)

        elif event_type == QEvent.FocusOut:
            return self._handle_focus_out(obj)

        elif event_type == QEvent.KeyPress:
            return self._handle_key_press(obj, event)

        return False

    def _handle_focus_in(self, widget: QWidget) -> bool:
        """Handle FocusIn event."""
        row = self.find_row_for_widget(widget)
        if row is not None:
            self._current_editing_row = row
            self.row_focus_entered.emit(row)
            # Select row visually
            self._table.selectRow(row)
        return False

    def _handle_focus_out(self, widget: QWidget) -> bool:
        """Handle FocusOut event."""
        # Capture current generation for deferred check
        gen = self._focus_generation
        QTimer.singleShot(0, lambda g=gen: self._check_row_focus_loss(g))
        return False

    def _handle_key_press(self, widget: QWidget, event: QEvent) -> bool:
        """Handle KeyPress event."""
        if not isinstance(event, QKeyEvent):
            return False

        key = event.key()
        modifiers = event.modifiers()

        # Handle Tab/Backtab for navigation
        if key == Qt.Key_Tab or key == Qt.Key_Backtab:
            row, col = self.find_cell_for_widget(widget)
            if row is not None and col is not None:
                forward = not (key == Qt.Key_Backtab or (modifiers & Qt.ShiftModifier))
                self.tab_navigation.emit(row, col, forward)
                return True  # Let table handle the actual navigation

        # Handle Enter/Return (not Shift+Enter)
        if key in (Qt.Key_Return, Qt.Key_Enter) and not (modifiers & Qt.ShiftModifier):
            row = self.find_row_for_widget(widget)
            if row is not None:
                self.enter_pressed.emit(row)
                return True  # Let table handle validation

        return False

    def _check_row_focus_loss(self, expected_generation: int) -> None:
        """
        Check if focus has left the current editing row (deferred check).

        Args:
            expected_generation: The focus generation when callback was queued
        """
        # Skip if generation changed (sort/edit invalidated this callback)
        if expected_generation != self._focus_generation:
            return

        # Skip if validating
        if self._validating:
            return

        if self._current_editing_row is None:
            return

        # Check if validation should be skipped
        if self._skip_validation:
            self._skip_validation = False
            return

        # Get currently focused widget
        focused_widget = QApplication.focusWidget()

        if not focused_widget:
            # Focus lost completely - emit signal
            self.row_focus_lost.emit(self._current_editing_row)
            self._current_editing_row = None
            return

        # Check if focus moved to different row
        new_row = self.find_row_for_widget(focused_widget)

        if new_row != self._current_editing_row:
            # Focus moved to different row - emit signal
            self.row_focus_lost.emit(self._current_editing_row)
            self._current_editing_row = new_row

    # -------------------------------------------------------------------------
    # Tab Navigation Helper
    # -------------------------------------------------------------------------

    def get_next_column(self, current_col: int, forward: bool) -> Optional[int]:
        """
        Get next column for tab navigation.

        Args:
            current_col: Current column index
            forward: True for forward (Tab), False for backward (Shift+Tab)

        Returns:
            Next column index or None if out of range
        """
        if forward:
            next_col = current_col + 1
            # Skip any skip_columns
            while next_col in self._skip_columns:
                next_col += 1
        else:
            next_col = current_col - 1
            # Skip any skip_columns
            while next_col in self._skip_columns:
                next_col -= 1

        # Check if within editable range
        if next_col in self._editable_columns:
            return next_col

        return None
