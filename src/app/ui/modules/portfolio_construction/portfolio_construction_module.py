"""Portfolio Construction Module - Main Orchestrator"""

import threading
import weakref
from datetime import datetime
from typing import List, Dict, Any, Optional

from PySide6.QtWidgets import QWidget, QVBoxLayout, QStackedWidget, QApplication
from PySide6.QtCore import Qt, QTimer, QThread, Signal

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common import CustomMessageBox, parse_portfolio_value
from app.ui.widgets.common.loading_overlay import LoadingOverlay
from app.ui.widgets.common.lazy_theme_mixin import LazyThemeMixin

from .services import PortfolioService, PortfolioPersistence, PortfolioSettingsManager, PortfolioExportService
from .widgets import (
    PortfolioControls,
    TransactionLogTable,
    AggregatePortfolioTable,
    NewPortfolioDialog,
    LoadPortfolioDialog,
    RenamePortfolioDialog,
    ImportPortfolioDialog,
    ExportDialog,
    ViewTabBar
)
from .widgets.portfolio_settings_dialog import PortfolioSettingsDialog


def _fetch_prices_and_names(tickers):
    """Fetch prices and names for tickers (runs in background thread)."""
    from app.services.market_data import fetch_price_history_batch

    fetch_price_history_batch(tickers)
    prices = PortfolioService.fetch_current_prices(tickers)
    names = PortfolioService.fetch_ticker_names(tickers)
    return (prices, names)


class PortfolioConstructionModule(LazyThemeMixin, QWidget):
    """
    Main portfolio construction module.
    Orchestrates all widgets and services for portfolio management.
    """

    # Signal emitted when live prices are received (from background thread)
    _live_prices_received = Signal(dict)  # {ticker: price}

    # Live polling interval (1 minute)
    _POLL_INTERVAL_MS = 60000

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._theme_dirty = False  # For lazy theme application

        # Initialize services
        PortfolioPersistence.initialize()

        # State
        self.current_portfolio = None  # Current portfolio dict
        self.unsaved_changes = False

        # Price cache - only fetch when tickers change
        self._cached_prices = {}  # ticker -> price
        self._cached_tickers = set()  # Set of tickers we've fetched prices for

        # Name cache - ticker short names from Yahoo Finance
        self._cached_names = {}  # ticker -> short name

        # Settings manager (handles persistence)
        self._settings_manager = PortfolioSettingsManager()

        # Loading overlay (created on demand)
        self._loading_overlay = None

        # Background price load worker
        self._load_thread: Optional[QThread] = None
        self._load_worker = None
        self._loading_portfolio_name: Optional[str] = None
        self._loading_tickers: List[str] = []

        # Live price polling timer
        self._live_poll_timer: Optional[QTimer] = None

        self._setup_ui()

        # Apply persisted settings to widgets
        self._apply_settings()
        self._connect_signals()
        self._apply_theme()

        # Initialize portfolio list without loading data
        self._initialize_portfolio_list()

        # Set initial view mode (Transaction Log by default)
        self.controls.set_view_mode(is_transaction_view=True)

        # Connect theme changes (lazy - only apply when visible)
        self.theme_manager.theme_changed.connect(self._on_theme_changed_lazy)

    def showEvent(self, event):
        """Handle show event - apply pending theme and resume live updates."""
        super().showEvent(event)
        self._check_theme_dirty()
        # Resume live price updates when module becomes visible
        if self.current_portfolio:
            self._start_live_updates()

    def hideEvent(self, event):
        """Handle hide event - cancel load worker and pause live updates."""
        self._cancel_load_worker()
        self._stop_live_updates()
        super().hideEvent(event)

    def _setup_ui(self):
        """Setup main UI layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Controls bar at top
        self.controls = PortfolioControls(self.theme_manager)
        layout.addWidget(self.controls)

        # View tab bar
        self.view_tab_bar = ViewTabBar(self.theme_manager)
        layout.addWidget(self.view_tab_bar)

        # Stacked widget for switching between tables
        self.table_stack = QStackedWidget()

        # Index 0: Transaction Log (full screen, no label)
        self.transaction_table = TransactionLogTable(self.theme_manager)
        self.table_stack.addWidget(self.transaction_table)

        # Index 1: Portfolio Holdings (full screen, no label)
        self.aggregate_table = AggregatePortfolioTable(self.theme_manager)
        self.table_stack.addWidget(self.aggregate_table)

        # Default to Transaction Log
        self.table_stack.setCurrentIndex(0)

        layout.addWidget(self.table_stack)

    def _connect_signals(self):
        """Connect all signals."""
        # Controls
        self.controls.portfolio_changed.connect(self._on_portfolio_changed)
        self.controls.save_clicked.connect(self._save_portfolio)
        self.controls.import_clicked.connect(self._import_portfolio_dialog)
        self.controls.export_clicked.connect(self._export_dialog)
        self.controls.new_portfolio_clicked.connect(self._new_portfolio_dialog)
        self.controls.rename_portfolio_clicked.connect(self._rename_portfolio_dialog)
        self.controls.delete_portfolio_clicked.connect(self._delete_portfolio_dialog)
        self.controls.home_clicked.connect(self._on_home_clicked)
        self.controls.settings_clicked.connect(self._open_settings_dialog)

        # Transaction table
        self.transaction_table.transaction_added.connect(self._on_transaction_changed)
        self.transaction_table.transaction_modified.connect(self._on_transaction_changed)
        self.transaction_table.transaction_deleted.connect(self._on_transaction_changed)

        # View tab bar
        self.view_tab_bar.view_changed.connect(self._on_view_changed)

        # Live price updates from background thread
        self._live_prices_received.connect(self._apply_live_prices)

    def _on_view_changed(self, index: int):
        """Handle view tab change."""
        self.table_stack.setCurrentIndex(index)
        # Show editing buttons only on Transaction Log view (index 0)
        self.controls.set_view_mode(is_transaction_view=(index == 0))

    def _initialize_portfolio_list(self):
        """Initialize portfolio dropdown without loading any portfolio."""
        portfolios = PortfolioPersistence.list_portfolios_by_recent()

        # Populate dropdown with no portfolio selected (shows placeholder)
        self.controls.update_portfolio_list(portfolios, None)

        # Show empty state - user must explicitly select a portfolio
        self._show_empty_state()

    def _populate_transaction_table(self):
        """Populate transaction table from current portfolio."""
        self.transaction_table.clear_all_transactions()

        if not self.current_portfolio:
            return

        transactions = self.current_portfolio.get("transactions", [])

        # Initialize sequence counter from existing transactions
        self.transaction_table._initialize_sequence_counter(transactions)

        # Use batch loading mode to avoid O(N²) FREE CASH updates
        self.transaction_table.begin_batch_loading()
        for transaction in transactions:
            self.transaction_table.add_transaction_row(transaction)
        self.transaction_table.end_batch_loading()

        # Ensure blank row exists for adding new transactions
        self.transaction_table._ensure_blank_row()

        # Sort by date descending (most recent first) with sequence for same-day ordering
        self.transaction_table.sort_by_date_descending()

        # Historical prices fetched in _update_aggregate_table() to avoid duplicate calls
        self.unsaved_changes = False

    def _on_transaction_changed(self, *args):
        """Handle transaction add/modify/delete."""
        self.unsaved_changes = True
        self._update_aggregate_table()

    def _show_empty_state(self):
        """Display empty state when no portfolio loaded."""
        self.current_portfolio = None
        self.transaction_table.clear_all_transactions()
        self.aggregate_table.setRowCount(0)
        self.unsaved_changes = False
        # Clear price cache
        self._cached_prices.clear()
        self._cached_tickers.clear()
        # Update button states (disable Save/Rename/Delete)
        self.controls._update_button_states(False)

    def _update_aggregate_table(self, force_fetch: bool = False):
        """
        Recalculate and update aggregate table.

        Fetches prices in a background thread if new tickers need data,
        then applies results on the main thread.

        Args:
            force_fetch: If True, fetch prices for all tickers (used on portfolio load)
        """
        transactions = self.transaction_table.get_all_transactions()

        if not transactions:
            self.aggregate_table.setRowCount(0)
            return

        # Get unique tickers (excluding FREE CASH - it doesn't need price fetching)
        tickers = set(
            t["ticker"] for t in transactions
            if t["ticker"] and t["ticker"].upper() != PortfolioService.FREE_CASH_TICKER
        )

        # Determine which tickers need price fetching
        tickers_to_fetch = []
        if tickers:
            if force_fetch:
                tickers_to_fetch = list(tickers)
            else:
                tickers_to_fetch = [t for t in tickers if t not in self._cached_tickers]

        if tickers_to_fetch:
            # Fetch in background thread to avoid blocking UI
            self._cancel_load_worker()

            from app.services.calculation_worker import CalculationWorker

            # Store context for the completion callback
            self._pending_tickers = tickers
            self._pending_tickers_to_fetch = tickers_to_fetch
            self._pending_transactions = transactions

            self._load_thread = QThread()
            self._load_worker = CalculationWorker(
                _fetch_prices_and_names, tickers_to_fetch
            )
            self._load_worker.moveToThread(self._load_thread)

            self._load_thread.started.connect(self._load_worker.run)
            self._load_worker.finished.connect(self._on_aggregate_fetch_complete)
            self._load_worker.error.connect(self._on_aggregate_fetch_error)
            self._load_thread.start()
        else:
            # No new tickers to fetch — apply directly with cached data
            self._apply_aggregate_update(tickers, transactions)

    def _on_aggregate_fetch_complete(self, result):
        """Handle background price/name fetch for aggregate table."""
        prices, names = result
        tickers = getattr(self, "_pending_tickers", set())
        tickers_to_fetch = getattr(self, "_pending_tickers_to_fetch", [])
        transactions = getattr(self, "_pending_transactions", [])

        # Update caches
        self._cached_prices.update(prices)
        self._cached_names.update(names)
        self._cached_tickers.update(tickers_to_fetch)

        self._apply_aggregate_update(tickers, transactions)
        self._cleanup_load_worker()

    def _on_aggregate_fetch_error(self, error_msg: str):
        """Handle error during aggregate fetch — apply with available data."""
        tickers = getattr(self, "_pending_tickers", set())
        tickers_to_fetch = getattr(self, "_pending_tickers_to_fetch", [])
        transactions = getattr(self, "_pending_transactions", [])

        self._cached_tickers.update(tickers_to_fetch)
        self._apply_aggregate_update(tickers, transactions)
        self._cleanup_load_worker()

    def _apply_aggregate_update(self, tickers: set, transactions: list):
        """Apply aggregate table update using cached data (runs on main thread)."""
        # Remove cached tickers that are no longer in use
        removed_tickers = self._cached_tickers - tickers
        for ticker in removed_tickers:
            self._cached_tickers.discard(ticker)
            self._cached_prices.pop(ticker, None)
            self._cached_names.pop(ticker, None)

        # Use cached prices for calculations
        current_prices = {t: self._cached_prices.get(t) for t in tickers}

        # Use cached names for display
        ticker_names = {t: self._cached_names.get(t) for t in tickers}

        # Update transaction table with current prices and names
        self.transaction_table.update_current_prices(current_prices)
        self.transaction_table.update_ticker_names(ticker_names)

        # Also fetch historical prices for new ticker/date combinations
        # (batch fetch handles caching internally)
        self.transaction_table.fetch_historical_prices_batch()

        # Calculate holdings (excludes FREE CASH)
        holdings = PortfolioService.calculate_aggregate_holdings(transactions, current_prices)

        # Calculate FREE CASH summary
        free_cash_summary = PortfolioService.calculate_free_cash_summary(transactions)

        # Update aggregate table with holdings, FREE CASH, and ticker names
        self.aggregate_table.update_holdings(holdings, free_cash_summary, ticker_names)

    def _refresh_prices(self):
        """Manually refresh current prices and names."""
        # Clear caches and force fetch all
        self._cached_prices.clear()
        self._cached_names.clear()
        self._cached_tickers.clear()
        self._update_aggregate_table(force_fetch=True)
        CustomMessageBox.information(
            self.theme_manager,
            self,
            "Prices Refreshed",
            "Current prices updated successfully."
        )

    def _save_portfolio(self):
        """Save current portfolio to disk."""
        if not self.current_portfolio:
            return

        # Update transactions in portfolio
        self.current_portfolio["transactions"] = self.transaction_table.get_all_transactions()

        # Save
        success = PortfolioPersistence.save_portfolio(self.current_portfolio)

        if success:
            self.unsaved_changes = False
            CustomMessageBox.information(
                self.theme_manager,
                self,
                "Saved",
                f"Portfolio '{self.current_portfolio['name']}' saved successfully."
            )
        else:
            CustomMessageBox.critical(
                self.theme_manager,
                self,
                "Save Error",
                "Failed to save portfolio."
            )

    def _load_portfolio_dialog(self):
        """Open load portfolio dialog."""
        # Check for unsaved changes
        if self.unsaved_changes:
            reply = CustomMessageBox.question(
                self.theme_manager,
                self,
                "Unsaved Changes",
                "You have unsaved changes. Do you want to save before loading?",
                CustomMessageBox.Yes | CustomMessageBox.No | CustomMessageBox.Cancel,
                CustomMessageBox.Cancel
            )

            if reply == CustomMessageBox.Yes:
                self._save_portfolio()
            elif reply == CustomMessageBox.Cancel:
                return

        # Open dialog
        portfolios = PortfolioPersistence.list_portfolios_by_recent()
        if not portfolios:
            CustomMessageBox.information(
                self.theme_manager,
                self,
                "No Portfolios",
                "No portfolios found. Create a new one first."
            )
            return

        dialog = LoadPortfolioDialog(self.theme_manager, portfolios, self)

        if dialog.exec():
            name = dialog.get_selected_name()
            if name:
                self._load_portfolio(name)

    def _load_portfolio(self, name: str):
        """Load portfolio by name using background thread for price fetching."""
        portfolio = PortfolioPersistence.load_portfolio(name)

        if not portfolio:
            CustomMessageBox.critical(
                self.theme_manager,
                self,
                "Load Error",
                f"Failed to load portfolio '{name}'."
            )
            return

        # Cancel any in-progress load
        self._cancel_load_worker()

        # Show loading overlay
        self._show_loading_overlay()

        # Clear caches when loading new portfolio
        self._cached_prices.clear()
        self._cached_names.clear()
        self._cached_tickers.clear()

        self.current_portfolio = portfolio
        self._populate_transaction_table()

        # Determine tickers that need price fetching
        transactions = self.transaction_table.get_all_transactions()
        tickers_to_fetch = list(set(
            t["ticker"] for t in transactions
            if t["ticker"] and t["ticker"].upper() != PortfolioService.FREE_CASH_TICKER
        ))

        if not tickers_to_fetch:
            # No tickers to fetch - finish immediately
            self._on_portfolio_load_complete({}, {})
            return

        # Store context for completion callback
        self._loading_portfolio_name = name
        self._loading_tickers = tickers_to_fetch

        # Start background fetch
        from app.services.calculation_worker import CalculationWorker

        self._load_thread = QThread()
        self._load_worker = CalculationWorker(
            _fetch_prices_and_names, tickers_to_fetch
        )
        self._load_worker.moveToThread(self._load_thread)

        self._load_thread.started.connect(self._load_worker.run)
        self._load_worker.finished.connect(self._on_prices_loaded)
        self._load_worker.error.connect(self._on_portfolio_load_error)
        self._load_thread.start()

    def _on_prices_loaded(self, result):
        """Unpack (prices, names) tuple from CalculationWorker."""
        prices, names = result
        self._on_portfolio_load_complete(prices, names)

    def _on_portfolio_load_complete(self, prices: dict, names: dict):
        """Handle successful price fetch - update UI on main thread."""
        name = self._loading_portfolio_name or (
            self.current_portfolio.get("name", "") if self.current_portfolio else ""
        )

        # Update caches
        self._cached_prices.update(prices)
        self._cached_names.update(names)
        self._cached_tickers.update(self._loading_tickers)

        # Update UI tables (no fetch needed - all tickers are cached)
        self._update_aggregate_table(force_fetch=False)

        # Record visit for recent ordering
        if name:
            PortfolioPersistence.record_visit(name)
            portfolios = PortfolioPersistence.list_portfolios_by_recent()
            self.controls.update_portfolio_list(portfolios, name)

        self.controls._update_button_states(True)

        # Start live price updates for this portfolio
        self._start_live_updates()

        # Hide loading overlay
        self._hide_loading_overlay()
        self._cleanup_load_worker()

    def _on_portfolio_load_error(self, error_msg: str):
        """Handle price fetch error - still show portfolio with available data."""
        name = self._loading_portfolio_name or (
            self.current_portfolio.get("name", "") if self.current_portfolio else ""
        )

        # Mark tickers as cached so _update_aggregate_table won't re-fetch
        self._cached_tickers.update(self._loading_tickers)

        # Update UI with whatever data we have
        self._update_aggregate_table(force_fetch=False)

        if name:
            PortfolioPersistence.record_visit(name)
            portfolios = PortfolioPersistence.list_portfolios_by_recent()
            self.controls.update_portfolio_list(portfolios, name)

        self.controls._update_button_states(True)
        self._start_live_updates()
        self._hide_loading_overlay()
        self._cleanup_load_worker()

    def _cancel_load_worker(self):
        """Cancel any in-progress load worker with proper Qt cleanup."""
        if self._load_worker is not None:
            try:
                self._load_worker.finished.disconnect()
                self._load_worker.error.disconnect()
            except (RuntimeError, TypeError):
                pass
        self._cleanup_load_worker()

    def _cleanup_load_worker(self):
        """Clean up load worker and thread after completion."""
        if self._load_thread is not None:
            self._load_thread.quit()
            if not self._load_thread.wait(5000):
                self._load_thread.terminate()
                self._load_thread.wait(1000)
        if self._load_worker is not None:
            self._load_worker.deleteLater()
        if self._load_thread is not None:
            self._load_thread.deleteLater()
        self._load_worker = None
        self._load_thread = None

    def _show_loading_overlay(self, message: str = "Loading Portfolio..."):
        """Show loading overlay over the tab bar and table area."""
        if self._loading_overlay is None:
            # Parent to self (the module) to cover both tab bar and tables
            self._loading_overlay = LoadingOverlay(
                self, self.theme_manager, message
            )

        # Calculate rect that covers view_tab_bar + table_stack
        # Get positions relative to self
        tab_bar_top = self.view_tab_bar.geometry().top()
        table_bottom = self.table_stack.geometry().bottom()
        content_rect = self.rect()
        content_rect.setTop(tab_bar_top)
        content_rect.setBottom(table_bottom)

        self._loading_overlay.setGeometry(content_rect)
        self._loading_overlay.show()
        self._loading_overlay.raise_()
        # Force UI update to render overlay before heavy work
        QApplication.processEvents()

    def _hide_loading_overlay(self):
        """Hide and cleanup loading overlay."""
        if self._loading_overlay is not None:
            self._loading_overlay.hide()
            self._loading_overlay.deleteLater()
            self._loading_overlay = None

    def _new_portfolio_dialog(self):
        """Open new portfolio dialog."""
        # Check for unsaved changes
        if self.unsaved_changes:
            reply = CustomMessageBox.question(
                self.theme_manager,
                self,
                "Unsaved Changes",
                "You have unsaved changes. Do you want to save before creating a new portfolio?",
                CustomMessageBox.Yes | CustomMessageBox.No | CustomMessageBox.Cancel,
                CustomMessageBox.Cancel
            )

            if reply == CustomMessageBox.Yes:
                self._save_portfolio()
            elif reply == CustomMessageBox.Cancel:
                return

        # Open dialog
        existing = PortfolioPersistence.list_portfolios()
        dialog = NewPortfolioDialog(self.theme_manager, existing, self)

        if dialog.exec():
            name = dialog.get_name()
            # Create new portfolio
            self.current_portfolio = PortfolioPersistence.create_new_portfolio(name)
            PortfolioPersistence.save_portfolio(self.current_portfolio)

            # Clear tables and caches
            self.transaction_table.clear_all_transactions()
            self.aggregate_table.setRowCount(0)
            self._cached_prices.clear()
            self._cached_names.clear()
            self._cached_tickers.clear()

            # Ensure blank row exists for immediate editing
            self.transaction_table._ensure_blank_row()

            # Record visit for recent ordering
            PortfolioPersistence.record_visit(name)

            # Update controls and enable buttons (with recent ordering)
            portfolios = PortfolioPersistence.list_portfolios_by_recent()
            self.controls.update_portfolio_list(portfolios, name)
            self.controls._update_button_states(True)

            self.unsaved_changes = False

    def _rename_portfolio_dialog(self):
        """Open rename portfolio dialog."""
        if not self.current_portfolio:
            return

        current_name = self.current_portfolio.get("name", "")
        existing = PortfolioPersistence.list_portfolios()
        dialog = RenamePortfolioDialog(self.theme_manager, current_name, existing, self)

        if dialog.exec():
            new_name = dialog.get_name()
            if new_name and new_name != current_name:
                success = PortfolioPersistence.rename_portfolio(current_name, new_name)
                if success:
                    # Update current portfolio name
                    self.current_portfolio["name"] = new_name
                    # Refresh dropdown (with recent ordering)
                    portfolios = PortfolioPersistence.list_portfolios_by_recent()
                    self.controls.update_portfolio_list(portfolios, new_name)
                else:
                    CustomMessageBox.critical(
                        self.theme_manager,
                        self,
                        "Rename Error",
                        f"Failed to rename portfolio to '{new_name}'."
                    )

    def _delete_portfolio_dialog(self):
        """Show confirmation dialog and delete current portfolio."""
        if not self.current_portfolio:
            return

        portfolio_name = self.current_portfolio.get("name", "")

        # Confirm deletion
        reply = CustomMessageBox.question(
            self.theme_manager,
            self,
            "Delete Portfolio",
            f"Are you sure you want to delete '{portfolio_name}'?\n\nThis action cannot be undone.",
            CustomMessageBox.Yes | CustomMessageBox.No,
            CustomMessageBox.No
        )

        if reply != CustomMessageBox.Yes:
            return

        # Delete portfolio
        success = PortfolioPersistence.delete_portfolio(portfolio_name)

        if success:
            # Remove from recent visits
            PortfolioPersistence.remove_from_recent(portfolio_name)

            # Get remaining portfolios (with recent ordering)
            portfolios = PortfolioPersistence.list_portfolios_by_recent()

            # Update dropdown (no portfolio selected)
            self.controls.update_portfolio_list(portfolios, None)

            # Show empty state - user must select another portfolio
            self._show_empty_state()
        else:
            CustomMessageBox.critical(
                self.theme_manager,
                self,
                "Delete Error",
                f"Failed to delete portfolio '{portfolio_name}'."
            )

    def _import_portfolio_dialog(self):
        """Show import dialog and process import."""
        # Validate portfolio is loaded
        if not self.current_portfolio:
            CustomMessageBox.warning(
                self.theme_manager,
                self,
                "No Portfolio",
                "Please load or create a portfolio first."
            )
            return

        # Get available portfolios (exclude current)
        current_name = self.current_portfolio.get("name", "")
        all_portfolios = PortfolioPersistence.list_portfolios()
        available = [p for p in all_portfolios if p != current_name]

        if not available:
            CustomMessageBox.warning(
                self.theme_manager,
                self,
                "No Portfolios",
                "No other portfolios available to import from."
            )
            return

        # Show dialog
        dialog = ImportPortfolioDialog(self.theme_manager, available, self)
        if dialog.exec() != 1:  # QDialog.Accepted = 1
            return

        config = dialog.get_import_config()
        if not config:
            return

        # Load source transactions
        source_data = PortfolioPersistence.load_portfolio(config["source_portfolio"])
        if not source_data:
            CustomMessageBox.critical(
                self.theme_manager,
                self,
                "Load Error",
                f"Failed to load source portfolio '{config['source_portfolio']}'."
            )
            return

        source_txs = source_data.get("transactions", [])

        if not source_txs:
            CustomMessageBox.information(
                self.theme_manager,
                self,
                "Empty Portfolio",
                "Source portfolio has no transactions to import."
            )
            return

        # Process based on mode
        if config["import_mode"] == "flat":
            new_txs = PortfolioService.process_flat_import(
                source_txs,
                config["include_fees"],
                config["skip_zero_positions"]
            )
        else:
            new_txs = PortfolioService.generate_imported_transactions(
                source_txs,
                config["include_fees"]
            )

        if not new_txs:
            CustomMessageBox.information(
                self.theme_manager,
                self,
                "No Transactions",
                "No transactions to import after processing."
            )
            return

        # Show loading overlay during import
        self._show_loading_overlay("Importing Transactions...")

        try:
            # Add to current portfolio using batch mode for O(N) performance
            self.transaction_table.begin_batch_loading()
            for tx in new_txs:
                self.transaction_table.add_transaction_row(tx)
            self.transaction_table.end_batch_loading()

            # Sort to maintain date-descending order after import
            self.transaction_table.sort_by_date_descending()

            self.unsaved_changes = True

            # Update aggregate table
            self._update_aggregate_table()

            # Fetch historical prices for new transactions
            self.transaction_table.fetch_historical_prices_batch()
        finally:
            # Hide loading overlay
            self._hide_loading_overlay()

        # Show success message
        count = len(new_txs)
        mode_desc = "consolidated positions" if config["import_mode"] == "flat" else "transactions"
        CustomMessageBox.information(
            self.theme_manager,
            self,
            "Import Complete",
            f"Successfully imported {count} {mode_desc} from '{config['source_portfolio']}'."
        )

    def _on_portfolio_changed(self, name: str):
        """Handle portfolio selection change in dropdown."""
        # Strip "[Port] " prefix if present
        name, _ = parse_portfolio_value(name)

        if not name:
            return

        # Track if this is first load
        is_first_load = self.current_portfolio is None

        # Skip same-portfolio check on first load
        if not is_first_load and self.current_portfolio and name == self.current_portfolio.get("name"):
            return

        # Check for unsaved changes (skip on first load)
        if not is_first_load and self.unsaved_changes:
            reply = CustomMessageBox.question(
                self.theme_manager,
                self,
                "Unsaved Changes",
                "You have unsaved changes. Do you want to save before switching?",
                CustomMessageBox.Yes | CustomMessageBox.No | CustomMessageBox.Cancel,
                CustomMessageBox.Cancel
            )

            if reply == CustomMessageBox.Yes:
                self._save_portfolio()
            elif reply == CustomMessageBox.Cancel:
                # Revert dropdown (with recent ordering)
                current_name = self.current_portfolio.get("name") if self.current_portfolio else None
                self.controls.update_portfolio_list(
                    PortfolioPersistence.list_portfolios_by_recent(),
                    current_name
                )
                return

        self._load_portfolio(name)

    def _on_home_clicked(self):
        """Handle home button click."""
        parent = self.parent()
        while parent:
            if hasattr(parent, 'show_home'):
                parent.show_home()
                break
            parent = parent.parent()

    def _apply_theme(self):
        """Apply theme to module."""
        theme = self.theme_manager.current_theme

        if theme == "light":
            bg_color = "#ffffff"
        elif theme == "bloomberg":
            bg_color = "#000814"
        else:
            bg_color = "#1e1e1e"

        self.setStyleSheet(f"""
            QWidget {{
                background-color: {bg_color};
            }}
        """)

    # ========== Live Price Updates ==========

    def _start_live_updates(self) -> None:
        """Start live price polling for holdings."""
        if self._live_poll_timer is not None:
            return  # Already running

        # Get tickers to poll - only start if there are eligible tickers
        tickers = self._get_eligible_tickers_for_update()
        if not tickers:
            print(f"[Live Updates] No eligible tickers for update (cached: {len(self._cached_tickers)})")
            return

        print(f"[Live Updates] Starting polling for {len(tickers)} tickers: {tickers}")

        self._live_poll_timer = QTimer(self)
        self._live_poll_timer.timeout.connect(self._on_live_poll_tick)
        self._live_poll_timer.start(self._POLL_INTERVAL_MS)

        # Do immediate update
        self._on_live_poll_tick()

    def _stop_live_updates(self) -> None:
        """Stop live price polling."""
        if self._live_poll_timer is not None:
            print("[Live Updates] Stopping polling")
            self._live_poll_timer.stop()
            self._live_poll_timer.deleteLater()
            self._live_poll_timer = None

    def _get_eligible_tickers_for_update(self) -> List[str]:
        """
        Get tickers eligible for live update based on market hours.

        - Crypto tickers (-USD, -USDT): Always eligible (24/7)
        - Stock tickers: Only during extended market hours (4am-8pm ET on trading days)

        Returns:
            List of tickers that should be polled for live prices
        """
        from app.utils.market_hours import is_crypto_ticker, is_market_open_extended

        all_tickers = list(self._cached_tickers)
        eligible = []

        for ticker in all_tickers:
            if is_crypto_ticker(ticker):
                eligible.append(ticker)  # Crypto: 24/7
            elif is_market_open_extended():
                eligible.append(ticker)  # Stocks: only during market hours

        return eligible

    def _on_live_poll_tick(self) -> None:
        """Handle live poll timer tick - fetch and update prices in background thread."""
        tickers = self._get_eligible_tickers_for_update()
        if not tickers:
            return

        print(f"[Live Updates] Fetching prices for: {tickers}")

        # Prevent segfault: capture weakref so thread won't emit to destroyed widget
        weak_self = weakref.ref(self)

        # Run in background thread to avoid blocking UI
        def fetch_and_update():
            try:
                from app.services.yahoo_finance_service import YahooFinanceService

                prices = YahooFinanceService.fetch_batch_current_prices(tickers)
                if prices:
                    print(f"[Live Updates] Received prices: {prices}")
                    obj = weak_self()
                    if obj is not None:
                        try:
                            obj._live_prices_received.emit(prices)
                        except RuntimeError:
                            pass
                else:
                    print("[Live Updates] No prices returned")
            except Exception as e:
                print(f"[Live Updates] Failed: {e}")

        thread = threading.Thread(target=fetch_and_update, daemon=True)
        thread.start()

    def _apply_live_prices(self, prices: Dict[str, float]) -> None:
        """
        Apply live prices to Holdings tab (called on main thread via signal).

        Args:
            prices: Dict mapping ticker -> current price
        """
        # Update cached prices
        self._cached_prices.update(prices)

        # Update aggregate table with new prices
        self.aggregate_table.update_live_prices(prices)

        # Update transaction table current prices
        self.transaction_table.update_current_prices(prices)

    def _open_settings_dialog(self):
        """Open settings dialog."""
        dialog = PortfolioSettingsDialog(
            self.theme_manager,
            self._settings_manager.get_all_settings(),
            self
        )

        if dialog.exec():
            new_settings = dialog.get_settings()
            if new_settings:
                # Save settings to disk
                self._settings_manager.update_settings(new_settings)
                # Apply settings to widgets
                self._apply_settings()

    def _apply_settings(self):
        """Apply current settings to widgets."""
        self.transaction_table.set_highlight_editable(
            self._settings_manager.get_setting("highlight_editable_fields")
        )
        self.transaction_table.set_hide_free_cash_summary(
            self._settings_manager.get_setting("hide_free_cash_summary")
        )

    # ========== Export Methods ==========

    def _export_dialog(self):
        """Show export format dialog and process export."""
        if not self.current_portfolio:
            CustomMessageBox.warning(
                self.theme_manager,
                self,
                "No Portfolio",
                "Please load or create a portfolio first."
            )
            return

        dialog = ExportDialog(self.theme_manager, self)
        if dialog.exec() != 1:  # QDialog.Accepted
            return

        export_format = dialog.get_format()
        if not export_format:
            return

        # Get data based on current view
        current_view = self.table_stack.currentIndex()
        portfolio_name = self.current_portfolio.get("name", "portfolio")

        if current_view == 0:  # Transaction Log
            data, columns, prefix = PortfolioExportService.get_transaction_export_data(
                self.transaction_table.get_all_transactions(),
                self._cached_prices,
                self._cached_names,
                self.transaction_table._historical_prices,
                portfolio_name,
            )
        else:  # Holdings
            data, columns, prefix = PortfolioExportService.get_holdings_export_data(
                self.aggregate_table._holdings_data,
                self._cached_names,
                portfolio_name,
            )

        if not data:
            CustomMessageBox.information(
                self.theme_manager,
                self,
                "No Data",
                "No data to export."
            )
            return

        if export_format == "csv":
            PortfolioExportService.export_to_csv(self, self.theme_manager, data, columns, prefix)
        else:
            PortfolioExportService.export_to_excel(self, self.theme_manager, data, columns, prefix)
