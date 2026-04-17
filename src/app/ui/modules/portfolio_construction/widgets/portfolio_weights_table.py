"""Portfolio Weights Table Widget - Editable Ticker/Weight Table"""

from typing import Dict, List, Optional, Tuple

from PySide6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QHeaderView, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QAbstractButton, QMenu, QLineEdit
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QEvent
from PySide6.QtGui import QColor, QAction, QBrush, QKeyEvent

from app.core.theme_manager import ThemeManager
from app.services.theme_stylesheet_service import ThemeStylesheetService
from app.ui.widgets.common import (
    AutoSelectLineEdit,
    CustomMessageBox,
    ValidatedNumericLineEdit,
    EditableTableBase,
)
from app.ui.widgets.common.lazy_theme_mixin import LazyThemeMixin


class PortfolioWeightsTable(LazyThemeMixin, EditableTableBase):
    """
    Editable weights table for defining portfolio allocations.
    Columns: Ticker, Weight (%), Name.
    """

    weights_changed = Signal()  # Emitted on any edit
    _name_autofill_ready = Signal(int, str)  # (row, name) for thread-safe UI update
    _ticker_invalid = Signal(int, str)  # (row, error_message) for invalid ticker

    COLUMNS = ["Ticker", "Weight (%)", "Name"]
    EDITABLE_COLUMNS = [0, 1]  # Ticker and Weight (Name is read-only)

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(theme_manager, self.COLUMNS, parent)

        self._cached_names: Dict[str, str] = {}
        self._autofill_threads: Dict[int, QThread] = {}
        self._batch_loading = False

        self._setup_base_table()
        self._setup_table()
        self._apply_base_theme()
        self._setup_total_label()
        self._ensure_blank_row()

        # Auto-fill signals
        self._name_autofill_ready.connect(self._apply_name_autofill)
        self._ticker_invalid.connect(self._on_ticker_invalid)

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
        # Weight - fixed width
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        self.setColumnWidth(1, 120)
        # Name - stretch
        header.setSectionResizeMode(2, QHeaderView.Stretch)

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
    # Name column widget helper (plain background, read-only)
    # -------------------------------------------------------------------------

    def _create_name_widget(self, row: int, name: str = "") -> None:
        """Create a read-only Name widget with plain (non-accent) background."""
        theme = self.theme_manager.current_theme
        name_style = ThemeStylesheetService.get_line_edit_stylesheet(
            theme, highlighted=False
        )
        name_edit = AutoSelectLineEdit(name, self)
        name_edit.setReadOnly(True)
        name_edit.setStyleSheet(name_style)

        # Wrap in transparent container
        container = QWidget()
        container.setAutoFillBackground(True)
        container.setStyleSheet("QWidget { background-color: transparent; }")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(name_edit)
        container.setProperty("_inner_widget", name_edit)

        # Set plain table item (no accent background)
        item = QTableWidgetItem()
        self.setItem(row, 2, item)
        self.setCellWidget(row, 2, container)

    # -------------------------------------------------------------------------
    # Event filter for Tab / Enter navigation
    # -------------------------------------------------------------------------

    def _install_event_filter(self, row: int):
        """Install event filter on editable widgets in a row for keyboard navigation."""
        for col in (0, 1):
            inner = self._get_inner_widget(row, col)
            if inner:
                inner.installEventFilter(self)

    def eventFilter(self, obj: QWidget, event: QEvent) -> bool:
        """Handle Tab and Enter key events for cell navigation."""
        if event.type() != QEvent.KeyPress:
            return False

        key_event = event
        if not isinstance(key_event, QKeyEvent):
            return False

        key = key_event.key()
        modifiers = key_event.modifiers()

        # Tab / Shift+Tab: move between Ticker (col 0) and Weight (col 1)
        if key in (Qt.Key_Tab, Qt.Key_Backtab):
            row, col = self._find_cell_for_widget(obj)
            if row is not None and col is not None:
                # Validate weight before leaving the weight column
                if col == 1:
                    self._on_weight_edited(row)

                if key == Qt.Key_Backtab or (modifiers & Qt.ShiftModifier):
                    next_col = col - 1
                else:
                    next_col = col + 1

                if next_col in (0, 1):
                    next_widget = self._get_inner_widget(row, next_col)
                    if next_widget:
                        next_widget.setFocus()
                        if isinstance(next_widget, QLineEdit):
                            next_widget.selectAll()
                        return True
            return True  # Consume Tab even if out of range

        # Enter/Return: validate row and move cursor to new blank row's ticker
        if key in (Qt.Key_Return, Qt.Key_Enter) and not (modifiers & Qt.ShiftModifier):
            row = self._find_row_for_widget(obj)
            if row is not None:
                self._handle_enter_key(row)
                return True

        return False

    def _handle_enter_key(self, row: int):
        """Handle Enter key - validate row and advance to new blank row."""
        # Validate and cap weight before advancing
        self._on_weight_edited(row)

        ticker_widget = self._get_inner_widget(row, 0)
        weight_widget = self._get_inner_widget(row, 1)

        if not ticker_widget or not weight_widget:
            return

        ticker = ""
        if isinstance(ticker_widget, AutoSelectLineEdit):
            from ..services.portfolio_service import PortfolioService
            ticker = PortfolioService.normalize_ticker(ticker_widget.text())

        weight_pct = 0.0
        if isinstance(weight_widget, ValidatedNumericLineEdit):
            weight_pct = weight_widget.value()

        if not ticker or weight_pct <= 0:
            return  # Row not valid, don't advance

        # Trigger name autofill if not already done
        self._start_name_autofill(row, ticker)

        # Ensure blank row exists and focus its ticker
        self._ensure_blank_row()
        last_row = self.rowCount() - 1
        ticker_edit = self._get_inner_widget(last_row, 0)
        if ticker_edit:
            # Use singleShot to let the current event processing finish
            def _focus():
                ticker_edit.setFocus()
                if isinstance(ticker_edit, QLineEdit):
                    ticker_edit.selectAll()
            QTimer.singleShot(50, _focus)

    # -------------------------------------------------------------------------
    # Row lookup helper
    # -------------------------------------------------------------------------

    def _row_for_widget(self, widget: QWidget) -> int:
        """Find the current row index for a widget by scanning the table.

        Returns -1 if not found.
        """
        for r in range(self.rowCount()):
            for c in (0, 1):  # Ticker and Weight columns
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

        widget_style = self._get_widget_stylesheet()

        # Ticker - editable (col 0)
        ticker_edit = AutoSelectLineEdit("", self)
        ticker_edit.setPlaceholderText("Enter ticker...")
        ticker_edit.setStyleSheet(widget_style)
        ticker_edit.editingFinished.connect(
            lambda w=ticker_edit: self._on_ticker_edited_from_widget(w)
        )
        self._set_editable_cell_widget(row, 0, ticker_edit)
        self._set_widget_position(ticker_edit, row, 0)

        # Weight - editable (col 1)
        weight_edit = ValidatedNumericLineEdit(
            min_value=0.0, max_value=100.0, decimals=2, parent=self
        )
        weight_edit.setPlaceholderText("0.00")
        weight_edit.setStyleSheet(widget_style)
        weight_edit.editingFinished.connect(
            lambda w=weight_edit: self._on_weight_edited_from_widget(w)
        )
        self._set_editable_cell_widget(row, 1, weight_edit)
        self._set_widget_position(weight_edit, row, 1)

        # Name - read-only (col 2, plain background)
        self._create_name_widget(row, "")

        # Install event filter for Tab/Enter navigation
        self._install_event_filter(row)

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

        from ..services.portfolio_service import PortfolioService
        ticker = PortfolioService.normalize_ticker(ticker_widget.text())
        if not ticker:
            return

        # Check for duplicate - merge weights into existing row
        existing_row = self._find_row_for_ticker(ticker, exclude_row=row)
        if existing_row is not None:
            self._merge_duplicate_row(row, existing_row)
            return

        # Start name auto-fill
        self._start_name_autofill(row, ticker)

        # Ensure blank row exists
        self._ensure_blank_row()

        if not self._batch_loading:
            self.weights_changed.emit()

    def _on_weight_edited(self, row: int):
        """Handle weight field editing finished."""
        self._cap_weight_if_over_100(row)
        self._update_total_display()
        self._ensure_blank_row()
        if not self._batch_loading:
            self.weights_changed.emit()

    def _find_row_for_ticker(self, ticker: str, exclude_row: int = -1) -> Optional[int]:
        """Find the row index containing a given ticker, or None.

        Comparison is done on the normalized form so [Custom] tickers are
        matched case-insensitively against the stored canonical form.
        """
        from ..services.portfolio_service import PortfolioService
        target = PortfolioService.normalize_ticker(ticker)
        for r in range(self.rowCount()):
            if r == exclude_row:
                continue
            widget = self._get_inner_widget(r, 0)
            if widget and isinstance(widget, AutoSelectLineEdit):
                if PortfolioService.normalize_ticker(widget.text()) == target:
                    return r
        return None

    def _merge_duplicate_row(self, source_row: int, target_row: int):
        """Merge a duplicate ticker row into the existing row by summing weights."""
        source_weight_widget = self._get_inner_widget(source_row, 1)
        target_weight_widget = self._get_inner_widget(target_row, 1)

        source_weight = 0.0
        if source_weight_widget and isinstance(source_weight_widget, ValidatedNumericLineEdit):
            source_weight = source_weight_widget.value()

        target_weight = 0.0
        if target_weight_widget and isinstance(target_weight_widget, ValidatedNumericLineEdit):
            target_weight = target_weight_widget.value()

        combined = target_weight + source_weight

        # Cap combined weight so total doesn't exceed 100%
        other_total = self._total_weight_excluding_rows(target_row, source_row)
        max_allowed = max(0.0, 100.0 - other_total)
        if combined > max_allowed:
            combined = max_allowed

        if target_weight_widget and isinstance(target_weight_widget, ValidatedNumericLineEdit):
            target_weight_widget.setValue(combined)

        # Remove the source (duplicate) row
        self.removeRow(source_row)
        self._ensure_blank_row()
        self._update_total_display()

        if not self._batch_loading:
            self.weights_changed.emit()

    def _cap_weight_if_over_100(self, row: int):
        """Cap a row's weight so the total doesn't exceed 100%. Show warning if capped."""
        weight_widget = self._get_inner_widget(row, 1)
        if not weight_widget or not isinstance(weight_widget, ValidatedNumericLineEdit):
            return

        current_value = weight_widget.value()
        if current_value <= 0:
            return

        other_total = self._total_weight_excluding_rows(row)
        max_allowed = max(0.0, 100.0 - other_total)

        if current_value > max_allowed:
            weight_widget.setValue(max_allowed)
            CustomMessageBox.warning(
                self.theme_manager,
                self,
                "Weight Capped",
                f"Weight was reduced from {current_value:.2f}% to {max_allowed:.2f}% "
                f"so that the total does not exceed 100%."
            )

    def _total_weight_excluding_rows(self, *exclude_rows: int) -> float:
        """Calculate total weight excluding specific rows."""
        total = 0.0
        for r in range(self.rowCount()):
            if r in exclude_rows:
                continue
            widget = self._get_inner_widget(r, 1)
            if widget and isinstance(widget, ValidatedNumericLineEdit):
                total += widget.value()
        return total

    # -------------------------------------------------------------------------
    # Name auto-fill
    # -------------------------------------------------------------------------

    def _start_name_autofill(self, row: int, ticker: str):
        """Validate ticker and fetch company name in background thread."""
        if ticker in self._cached_names:
            self._apply_name_autofill(row, self._cached_names[ticker])
            return

        from app.services.calculation_worker import CalculationWorker

        def fetch_and_validate():
            from app.ui.modules.portfolio_construction.services.portfolio_service import PortfolioService
            # Validate ticker first
            is_valid, error_msg = PortfolioService.is_valid_ticker(ticker)
            if not is_valid:
                return {"name": "", "error": error_msg}
            # Fetch name
            names = PortfolioService.fetch_ticker_names([ticker])
            return {"name": names.get(ticker, "") or "", "error": None}

        thread = QThread()
        worker = CalculationWorker(fetch_and_validate)
        worker.moveToThread(thread)

        def on_done():
            if worker.result is not None and worker.error_msg is None:
                result = worker.result
                error = result.get("error")
                if error:
                    self._ticker_invalid.emit(row, error)
                else:
                    name = result["name"]
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

    def _on_ticker_invalid(self, row: int, error_msg: str):
        """Handle invalid ticker - show warning and clear the ticker field."""
        if row < 0 or row >= self.rowCount():
            return

        CustomMessageBox.warning(
            self.theme_manager,
            self,
            "Invalid Ticker",
            error_msg
        )

        # Clear the invalid ticker
        ticker_widget = self._get_inner_widget(row, 0)
        if ticker_widget and isinstance(ticker_widget, AutoSelectLineEdit):
            ticker_widget.setText("")
            ticker_widget.setFocus()

    def _apply_name_autofill(self, row: int, name: str):
        """Apply fetched name to the Name column (main thread)."""
        if row < 0 or row >= self.rowCount():
            return
        name_widget = self._get_inner_widget(row, 2)
        if name_widget and isinstance(name_widget, AutoSelectLineEdit):
            name_widget.setText(name or "")

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
            widget = self._get_inner_widget(r, 1)
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
            weight_widget = self._get_inner_widget(r, 1)

            if not ticker_widget or not weight_widget:
                continue

            ticker = ""
            if isinstance(ticker_widget, AutoSelectLineEdit):
                from ..services.portfolio_service import PortfolioService
                ticker = PortfolioService.normalize_ticker(ticker_widget.text())

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

        widget_style = self._get_widget_stylesheet()

        for ticker, weight_decimal in weights.items():
            row = self.rowCount()
            self.insertRow(row)
            self.setRowHeight(row, 40)

            # Ticker (col 0)
            ticker_edit = AutoSelectLineEdit(ticker, self)
            ticker_edit.setPlaceholderText("Enter ticker...")
            ticker_edit.setStyleSheet(widget_style)
            ticker_edit.editingFinished.connect(
                lambda w=ticker_edit: self._on_ticker_edited_from_widget(w)
            )
            self._set_editable_cell_widget(row, 0, ticker_edit)
            self._set_widget_position(ticker_edit, row, 0)

            # Weight (col 1, convert decimal to percentage)
            weight_edit = ValidatedNumericLineEdit(
                min_value=0.0, max_value=100.0, decimals=2, parent=self
            )
            weight_edit.setValue(weight_decimal * 100.0)
            weight_edit.setStyleSheet(widget_style)
            weight_edit.editingFinished.connect(
                lambda w=weight_edit: self._on_weight_edited_from_widget(w)
            )
            self._set_editable_cell_widget(row, 1, weight_edit)
            self._set_widget_position(weight_edit, row, 1)

            # Name (col 2, read-only, plain background)
            name = self._cached_names.get(ticker, "")
            self._create_name_widget(row, name)

            # Install event filter for Tab/Enter navigation
            self._install_event_filter(row)

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

        # Update Name column widgets (not in EDITABLE_COLUMNS, so not handled by base)
        theme = self.theme_manager.current_theme
        name_style = ThemeStylesheetService.get_line_edit_stylesheet(
            theme, highlighted=False
        )
        for row in range(self.rowCount()):
            container = self.cellWidget(row, 2)
            if container:
                container.setStyleSheet("QWidget { background-color: transparent; }")
                inner = container.property("_inner_widget")
                if inner and isinstance(inner, QLineEdit):
                    inner.setStyleSheet(name_style)

        self._update_total_display()
