"""Portfolio Weights Table Widget - Editable Ticker/Weight Table"""

from typing import Dict, List, Optional, Tuple

from PySide6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QHeaderView, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QAbstractButton, QMenu
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor, QAction

from app.core.theme_manager import ThemeManager
from app.services.theme_stylesheet_service import ThemeStylesheetService
from app.ui.widgets.common import (
    AutoSelectLineEdit,
    ValidatedNumericLineEdit,
    EditableTableBase,
)
from app.ui.widgets.common.lazy_theme_mixin import LazyThemeMixin


class PortfolioWeightsTable(LazyThemeMixin, EditableTableBase):
    """
    Editable weights table for defining portfolio allocations.
    Columns: Ticker, Name, Weight (%).
    """

    weights_changed = Signal()  # Emitted on any edit
    _name_autofill_ready = Signal(int, str)  # (row, name) for thread-safe UI update

    COLUMNS = ["Ticker", "Name", "Weight (%)"]
    EDITABLE_COLUMNS = [0, 2]  # Ticker and Weight

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(theme_manager, self.COLUMNS, parent)

        self._cached_names: Dict[str, str] = {}
        self._autofill_threads: Dict[int, QThread] = {}
        self._batch_loading = False

        self._setup_base_table()
        self._setup_table()
        # Disable the aggressive accent highlighting on editable cells
        self.set_highlight_editable(False)
        self._apply_base_theme()
        self._setup_total_label()
        self._ensure_blank_row()

        # Auto-fill signal
        self._name_autofill_ready.connect(self._apply_name_autofill)

        # Context menu
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        # Lazy theme
        self.theme_manager.theme_changed.connect(self._on_theme_changed_lazy)

    def showEvent(self, event):
        super().showEvent(event)
        self._check_theme_dirty()

    def _get_editable_columns(self) -> list:
        return self.EDITABLE_COLUMNS

    def _setup_table(self):
        """Configure table structure."""
        header = self.horizontalHeader()
        # Ticker - fixed width
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        self.setColumnWidth(0, 120)
        # Name - stretch
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        # Weight - fixed width
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        self.setColumnWidth(2, 120)

        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.verticalHeader().setVisible(False)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setSelectionMode(QTableWidget.SingleSelection)
        self.setAlternatingRowColors(True)

        # Corner button
        corner = self.findChild(QAbstractButton)
        if corner:
            corner.setEnabled(False)

    def _setup_total_label(self):
        """Create the total weight indicator label below the table."""
        self._total_label = QLabel("Total: 0.00%")
        self._total_label.setObjectName("weightsTotalLabel")
        self._total_label.setFixedHeight(32)
        self._total_label.setContentsMargins(10, 4, 10, 4)
        self._update_total_display()

    def get_total_label(self) -> QLabel:
        """Return the total weight label widget for layout by the parent."""
        return self._total_label

    # -------------------------------------------------------------------------
    # Row lookup helper
    # -------------------------------------------------------------------------

    def _row_for_widget(self, widget: QWidget) -> int:
        """Find the current row index for a widget by scanning the table.

        Returns -1 if not found.
        """
        for r in range(self.rowCount()):
            for c in (0, 2):  # Only editable columns
                inner = self._get_inner_widget(r, c)
                if inner is widget:
                    return r
        return -1

    # -------------------------------------------------------------------------
    # Row management
    # -------------------------------------------------------------------------

    def _ensure_blank_row(self):
        """Ensure there's always a blank row at the bottom for adding entries."""
        row_count = self.rowCount()
        if row_count > 0:
            ticker_widget = self._get_inner_widget(row_count - 1, 0)
            if ticker_widget and isinstance(ticker_widget, AutoSelectLineEdit):
                if not ticker_widget.text().strip():
                    return  # Already has blank row
        self._add_blank_row()

    def _add_blank_row(self):
        """Add a new blank row at the bottom."""
        row = self.rowCount()
        self.insertRow(row)
        self.setRowHeight(row, 40)

        # Ticker - editable
        ticker_edit = AutoSelectLineEdit("", self)
        ticker_edit.setPlaceholderText("Enter ticker...")
        ticker_edit.editingFinished.connect(
            lambda w=ticker_edit: self._on_ticker_edited_from_widget(w)
        )
        self._set_editable_cell_widget(row, 0, ticker_edit)

        # Name - read-only
        self._create_readonly_cell(row, 1, "")

        # Weight - editable
        weight_edit = ValidatedNumericLineEdit(
            min_value=0.0, max_value=100.0, decimals=2, parent=self
        )
        weight_edit.setPlaceholderText("0.00")
        weight_edit.editingFinished.connect(
            lambda w=weight_edit: self._on_weight_edited_from_widget(w)
        )
        self._set_editable_cell_widget(row, 2, weight_edit)

    # -------------------------------------------------------------------------
    # Edit handlers
    # -------------------------------------------------------------------------

    def _on_ticker_edited_from_widget(self, widget: QWidget):
        """Resolve row from widget, then handle edit."""
        row = self._row_for_widget(widget)
        if row >= 0:
            self._on_ticker_edited(row)

    def _on_weight_edited_from_widget(self, widget: QWidget):
        """Resolve row from widget, then handle edit."""
        row = self._row_for_widget(widget)
        if row >= 0:
            self._on_weight_edited(row)

    def _on_ticker_edited(self, row: int):
        """Handle ticker field editing finished."""
        ticker_widget = self._get_inner_widget(row, 0)
        if not ticker_widget:
            return

        ticker = ticker_widget.text().strip().upper()
        if not ticker:
            return

        # Check for duplicate
        existing = self._get_all_tickers_except_row(row)
        if ticker in existing:
            ticker_widget.setText("")
            return

        # Start name auto-fill
        self._start_name_autofill(row, ticker)

        # Ensure blank row exists
        self._ensure_blank_row()

        if not self._batch_loading:
            self.weights_changed.emit()

    def _on_weight_edited(self, row: int):
        """Handle weight field editing finished."""
        self._update_total_display()
        self._ensure_blank_row()
        if not self._batch_loading:
            self.weights_changed.emit()

    def _get_all_tickers_except_row(self, exclude_row: int) -> set:
        """Get all tickers in the table except the given row."""
        tickers = set()
        for r in range(self.rowCount()):
            if r == exclude_row:
                continue
            widget = self._get_inner_widget(r, 0)
            if widget and isinstance(widget, AutoSelectLineEdit):
                t = widget.text().strip().upper()
                if t:
                    tickers.add(t)
        return tickers

    # -------------------------------------------------------------------------
    # Name auto-fill
    # -------------------------------------------------------------------------

    def _start_name_autofill(self, row: int, ticker: str):
        """Fetch company name in background thread."""
        if ticker in self._cached_names:
            self._apply_name_autofill(row, self._cached_names[ticker])
            return

        from app.services.calculation_worker import CalculationWorker

        def fetch_name():
            from app.ui.modules.portfolio_construction.services.portfolio_service import PortfolioService
            name = PortfolioService.fetch_ticker_name(ticker)
            return name or ""

        thread = QThread()
        worker = CalculationWorker(fetch_name)
        worker.moveToThread(thread)

        def on_done():
            if worker.result is not None and worker.error_msg is None:
                name = worker.result
                if name:
                    self._cached_names[ticker] = name
                self._name_autofill_ready.emit(row, name)
            thread.quit()
            self._autofill_threads.pop(row, None)
            from app.ui.modules.base_module import _global_orphaned_threads
            _global_orphaned_threads.append(thread)
            _global_orphaned_threads.append(worker)

            def _cleanup(t=thread, w=worker):
                try:
                    _global_orphaned_threads.remove(t)
                except ValueError:
                    pass
                try:
                    _global_orphaned_threads.remove(w)
                except ValueError:
                    pass

            thread.finished.connect(_cleanup, Qt.QueuedConnection)

        thread.started.connect(worker.run)
        thread.finished.connect(on_done, Qt.QueuedConnection)

        old_thread = self._autofill_threads.get(row)
        if old_thread is not None:
            old_thread.quit()

        self._autofill_threads[row] = thread
        thread.start()

    def _apply_name_autofill(self, row: int, name: str):
        """Apply fetched name to the Name column (main thread)."""
        if row < 0 or row >= self.rowCount():
            return
        item = self.item(row, 1)
        if item:
            item.setText(name or "")

    # -------------------------------------------------------------------------
    # Total weight display
    # -------------------------------------------------------------------------

    def _update_total_display(self):
        """Update the total weight label."""
        total = self._calculate_total_weight()
        self._total_label.setText(f"Total: {total:.2f}%")

        if abs(total - 100.0) < 0.01:
            self._total_label.setStyleSheet(
                "QLabel { color: #4caf50; font-weight: bold; font-size: 14px; }"
            )
        elif total > 0:
            self._total_label.setStyleSheet(
                "QLabel { color: #f44336; font-weight: bold; font-size: 14px; }"
            )
        else:
            self._total_label.setStyleSheet(
                "QLabel { color: #888888; font-weight: bold; font-size: 14px; }"
            )

    def _calculate_total_weight(self) -> float:
        """Calculate total weight across all rows."""
        total = 0.0
        for r in range(self.rowCount()):
            widget = self._get_inner_widget(r, 2)
            if widget and isinstance(widget, ValidatedNumericLineEdit):
                total += widget.value()
        return total

    # -------------------------------------------------------------------------
    # Data access
    # -------------------------------------------------------------------------

    def get_all_weights(self) -> Dict[str, float]:
        """
        Get all weights as {ticker: decimal_weight}.

        Returns dict with weights converted from percentage (0-100) to decimal (0-1).
        Only includes rows with both ticker and weight filled in.
        """
        weights = {}
        for r in range(self.rowCount()):
            ticker_widget = self._get_inner_widget(r, 0)
            weight_widget = self._get_inner_widget(r, 2)

            if not ticker_widget or not weight_widget:
                continue

            ticker = ""
            if isinstance(ticker_widget, AutoSelectLineEdit):
                ticker = ticker_widget.text().strip().upper()

            weight_pct = 0.0
            if isinstance(weight_widget, ValidatedNumericLineEdit):
                weight_pct = weight_widget.value()

            if ticker and weight_pct > 0:
                weights[ticker] = round(weight_pct / 100.0, 6)

        return weights

    def set_weights(self, weights: Dict[str, float]):
        """
        Populate table from a weights dict.

        Args:
            weights: {ticker: decimal_weight} where decimal_weight is 0-1
        """
        self._batch_loading = True
        self.setRowCount(0)

        for ticker, weight_decimal in weights.items():
            row = self.rowCount()
            self.insertRow(row)
            self.setRowHeight(row, 40)

            # Ticker
            ticker_edit = AutoSelectLineEdit(ticker, self)
            ticker_edit.setPlaceholderText("Enter ticker...")
            ticker_edit.editingFinished.connect(
                lambda w=ticker_edit: self._on_ticker_edited_from_widget(w)
            )
            self._set_editable_cell_widget(row, 0, ticker_edit)

            # Name - read-only, auto-fill
            name = self._cached_names.get(ticker, "")
            self._create_readonly_cell(row, 1, name)

            # Weight (convert decimal to percentage)
            weight_edit = ValidatedNumericLineEdit(
                min_value=0.0, max_value=100.0, decimals=2, parent=self
            )
            weight_edit.setValue(weight_decimal * 100.0)
            weight_edit.editingFinished.connect(
                lambda w=weight_edit: self._on_weight_edited_from_widget(w)
            )
            self._set_editable_cell_widget(row, 2, weight_edit)

            # Start name auto-fill if not cached
            if not name:
                self._start_name_autofill(row, ticker)

        self._ensure_blank_row()
        self._update_total_display()
        self._batch_loading = False

    def clear_all(self):
        """Clear all rows and reset state."""
        self.setRowCount(0)
        self._ensure_blank_row()
        self._update_total_display()

    def validate_weights(self) -> Tuple[bool, str]:
        """
        Validate that weights are correct for saving.

        Returns:
            (is_valid, error_message) tuple
        """
        weights = self.get_all_weights()

        if not weights:
            return False, "Portfolio must have at least one ticker with a weight."

        # Check for duplicate tickers
        tickers = []
        for r in range(self.rowCount()):
            widget = self._get_inner_widget(r, 0)
            if widget and isinstance(widget, AutoSelectLineEdit):
                t = widget.text().strip().upper()
                if t:
                    if t in tickers:
                        return False, f"Duplicate ticker: {t}"
                    tickers.append(t)

        # Check all weights are positive
        for ticker, w in weights.items():
            if w <= 0:
                return False, f"Weight for {ticker} must be positive."

        # Check sum equals 100%
        total_pct = sum(w * 100 for w in weights.values())
        if abs(total_pct - 100.0) >= 0.01:
            return False, f"Weights must sum to 100%. Current total: {total_pct:.2f}%"

        return True, ""

    # -------------------------------------------------------------------------
    # Context menu and deletion
    # -------------------------------------------------------------------------

    def _show_context_menu(self, pos):
        """Show right-click context menu."""
        row = self.rowAt(pos.y())
        if row < 0:
            return

        # Don't allow deleting the blank row
        ticker_widget = self._get_inner_widget(row, 0)
        if ticker_widget and isinstance(ticker_widget, AutoSelectLineEdit):
            if not ticker_widget.text().strip():
                return

        menu = QMenu(self)
        delete_action = QAction("Delete Row", self)
        delete_action.triggered.connect(lambda: self._delete_row(row))
        menu.addAction(delete_action)
        menu.exec(self.viewport().mapToGlobal(pos))

    def _delete_row(self, row: int):
        """Delete a row from the table."""
        if row < 0 or row >= self.rowCount():
            return
        self.removeRow(row)
        self._ensure_blank_row()
        self._update_total_display()
        self.weights_changed.emit()

    def keyPressEvent(self, event):
        """Handle key press events."""
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            row = self.currentRow()
            if row >= 0:
                ticker_widget = self._get_inner_widget(row, 0)
                if ticker_widget and isinstance(ticker_widget, AutoSelectLineEdit):
                    if ticker_widget.text().strip():
                        self._delete_row(row)
                        return
        super().keyPressEvent(event)

    def _apply_theme(self):
        """Apply theme styling."""
        self._apply_base_theme()
        self._update_total_display()
