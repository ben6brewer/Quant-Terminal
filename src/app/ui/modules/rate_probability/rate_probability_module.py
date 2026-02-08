"""Rate Probability Module - FOMC rate decision probabilities from fed funds futures."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, List, Optional, Tuple

from PySide6.QtWidgets import QWidget, QVBoxLayout, QStackedWidget
from PySide6.QtCore import Signal, QThread, QObject

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common.loading_overlay import LoadingOverlay
from app.ui.widgets.common.lazy_theme_mixin import LazyThemeMixin

from .services.fomc_calendar_service import FomcCalendarService
from .services.rate_probability_service import RateProbabilityService
from .services.rate_probability_settings_manager import RateProbabilitySettingsManager
from .widgets.rate_probability_toolbar import RateProbabilityToolbar
from .widgets.probability_table_view import ProbabilityTableView
from .widgets.rate_path_chart import RatePathChart
from .widgets.probability_evolution_chart import ProbabilityEvolutionChart

if TYPE_CHECKING:
    import pandas as pd


class _FetchWorker(QObject):
    """Background worker for fetching futures data and calculating probabilities."""

    finished = Signal(object)  # dict with all results
    error = Signal(str)

    def run(self):
        try:
            # 1. Get FOMC meetings
            meetings = FomcCalendarService.get_upcoming_meetings(count=12)

            # 2. Fetch futures prices
            futures_df = RateProbabilityService.fetch_futures_prices()

            # 3. Fetch target rate from FRED
            target_rate = RateProbabilityService.fetch_target_rate()

            # 4. Calculate probabilities
            import pandas as pd

            if not futures_df.empty and meetings:
                prob_df = RateProbabilityService.calculate_meeting_probabilities(
                    futures_df, target_rate, meetings,
                )
            else:
                prob_df = pd.DataFrame()

            # 5. Get implied rate path
            rate_path = RateProbabilityService.get_implied_rate_path(prob_df)

            result = {
                "meetings": meetings,
                "futures_df": futures_df,
                "target_rate": target_rate,
                "probabilities_df": prob_df,
                "rate_path": rate_path,
                "next_meeting": FomcCalendarService.get_next_meeting(),
                "days_until": FomcCalendarService.days_until_next_meeting(),
            }

            self.finished.emit(result)

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.error.emit(str(e))


class _EvolutionFetchWorker(QObject):
    """Background worker for fetching historical probability evolution."""

    finished = Signal(object)  # DataFrame
    error = Signal(str)

    def __init__(self, meeting_date: date, meetings: List[date],
                 target_rate: Tuple[float, float], lookback_days: int):
        super().__init__()
        self._meeting_date = meeting_date
        self._meetings = meetings
        self._target_rate = target_rate
        self._lookback_days = lookback_days

    def run(self):
        try:
            from .services.rate_probability_service import (
                RateProbabilityService,
                CODE_TO_MONTH,
            )

            # Generate ticker for the meeting month contract
            month_code = CODE_TO_MONTH.get(self._meeting_date.month)
            if not month_code:
                self.finished.emit(None)
                return

            year_suffix = str(self._meeting_date.year)[-2:]
            target_ticker = f"ZQ{month_code}{year_suffix}.CBT"

            # Also fetch next-month contract for late-month meeting handling
            tickers_to_fetch = [target_ticker]
            import calendar
            total_days = calendar.monthrange(self._meeting_date.year, self._meeting_date.month)[1]
            pre_days = self._meeting_date.day - 1
            post_days = total_days - pre_days
            if post_days <= 7:
                next_month = self._meeting_date.month + 1
                next_year = self._meeting_date.year
                if next_month > 12:
                    next_month = 1
                    next_year += 1
                next_code = CODE_TO_MONTH.get(next_month)
                if next_code:
                    next_suffix = str(next_year)[-2:]
                    tickers_to_fetch.append(f"ZQ{next_code}{next_suffix}.CBT")

            # Fetch historical futures data
            historical = RateProbabilityService.fetch_historical_futures(
                tickers_to_fetch, lookback_days=self._lookback_days
            )

            if historical.empty:
                self.finished.emit(None)
                return

            # Calculate evolution
            evolution_df = RateProbabilityService.calculate_historical_probabilities(
                self._meeting_date,
                historical,
                self._target_rate,
                self._meetings,
            )

            self.finished.emit(evolution_df)

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.error.emit(str(e))


class RateProbabilityModule(LazyThemeMixin, QWidget):
    """Rate Probability module - CME FedWatch-style FOMC rate probabilities."""

    home_clicked = Signal()

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._theme_dirty = False

        # Settings
        self.settings_manager = RateProbabilitySettingsManager()

        # State
        self._data_initialized = False
        self._futures_data = None
        self._target_rate = None
        self._probabilities = None
        self._meetings: List[date] = []
        self._rate_path = None

        # Loading
        self._loading_overlay: Optional[LoadingOverlay] = None
        self._fetch_thread: Optional[QThread] = None
        self._fetch_worker: Optional[_FetchWorker] = None
        self._evolution_thread: Optional[QThread] = None
        self._evolution_worker: Optional[_EvolutionFetchWorker] = None

        self._setup_ui()
        self._connect_signals()
        self._apply_settings()
        self._apply_theme()

    def _setup_ui(self):
        """Setup module UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.toolbar = RateProbabilityToolbar(self.theme_manager)
        layout.addWidget(self.toolbar)

        self.stack = QStackedWidget()
        layout.addWidget(self.stack, stretch=1)

        # View 0: FedWatch probability table
        self.table_view = ProbabilityTableView(self.theme_manager)
        self.stack.addWidget(self.table_view)

        # View 1: Rate path chart
        self.rate_path_view = RatePathChart(self.theme_manager)
        self.stack.addWidget(self.rate_path_view)

        # View 2: Evolution chart
        self.evolution_view = ProbabilityEvolutionChart(self.theme_manager)
        self.stack.addWidget(self.evolution_view)

    def _connect_signals(self):
        """Connect signals to slots."""
        self.toolbar.home_clicked.connect(self.home_clicked.emit)
        self.toolbar.view_changed.connect(self._on_view_changed)
        self.toolbar.settings_clicked.connect(self._on_settings_clicked)
        self.evolution_view.meeting_changed.connect(self._on_evolution_meeting_changed)
        self.theme_manager.theme_changed.connect(self._on_theme_changed_lazy)

    def showEvent(self, event):
        super().showEvent(event)
        self._check_theme_dirty()
        if not self._data_initialized:
            self._data_initialized = True
            self._initialize_data()

    def _initialize_data(self):
        """Check for API key and start data fetch."""
        from app.services.fred_api_key_service import FredApiKeyService

        if not FredApiKeyService.has_api_key():
            self._show_api_key_dialog()
        else:
            self._fetch_data()

    def _show_api_key_dialog(self):
        """Show the FRED API key dialog."""
        from app.ui.widgets.common.api_key_dialog import APIKeyDialog
        from app.services.fred_api_key_service import FredApiKeyService

        dialog = APIKeyDialog(self.theme_manager, parent=self)
        if dialog.exec():
            key = dialog.get_api_key()
            if key:
                FredApiKeyService.set_api_key(key)
                self._fetch_data()
        else:
            self.table_view.show_placeholder(
                "FRED API key required for target rate data.\n"
                "Futures data can still be fetched without it."
            )
            # Try fetching anyway - futures data doesn't need FRED
            self._fetch_data()

    def _fetch_data(self):
        """Fetch all data in background thread."""
        self._cancel_fetch()
        self._show_loading("Fetching fed funds futures...")

        self._fetch_thread = QThread()
        self._fetch_worker = _FetchWorker()
        self._fetch_worker.moveToThread(self._fetch_thread)

        self._fetch_thread.started.connect(self._fetch_worker.run)
        self._fetch_worker.finished.connect(self._on_data_fetched)
        self._fetch_worker.error.connect(self._on_fetch_error)
        self._fetch_worker.finished.connect(self._fetch_thread.quit)
        self._fetch_worker.error.connect(self._fetch_thread.quit)

        self._fetch_thread.start()

    def _cancel_fetch(self):
        """Cancel any in-progress fetch."""
        if self._fetch_thread is not None and self._fetch_thread.isRunning():
            self._fetch_thread.quit()
            self._fetch_thread.wait(1000)
        self._fetch_thread = None
        self._fetch_worker = None

    def _cancel_evolution_fetch(self):
        """Cancel any in-progress evolution fetch."""
        if self._evolution_thread is not None and self._evolution_thread.isRunning():
            self._evolution_thread.quit()
            self._evolution_thread.wait(1000)
        self._evolution_thread = None
        self._evolution_worker = None

    def _on_data_fetched(self, result):
        """Handle successful data fetch."""
        self._hide_loading()

        if result is None:
            self.table_view.show_placeholder("Failed to fetch data.")
            return

        self._futures_data = result["futures_df"]
        self._target_rate = result["target_rate"]
        self._probabilities = result["probabilities_df"]
        self._meetings = result["meetings"]
        self._rate_path = result["rate_path"]

        # Update toolbar info
        self.toolbar.update_info(
            target_rate=self._target_rate,
            next_meeting=result["next_meeting"],
            days_until=result["days_until"],
        )

        # Update table view
        import pandas as pd
        if self._probabilities is not None and not self._probabilities.empty:
            self.table_view.update_data(
                self._futures_data, self._probabilities, self._target_rate
            )
        else:
            self.table_view.show_placeholder("No probability data available. Check futures data.")

        # Update rate path view
        if self._rate_path:
            current_mid = (self._target_rate[0] + self._target_rate[1]) / 2.0
            self.rate_path_view.update_data(self._rate_path, current_mid)
        else:
            self.rate_path_view.show_placeholder("No rate path data available.")

        # Set up evolution view meetings
        if self._meetings:
            self.evolution_view.set_meetings(self._meetings)

    def _on_fetch_error(self, error_msg: str):
        """Handle fetch error."""
        self._hide_loading()
        self.table_view.show_placeholder(f"Error fetching data: {error_msg}")

    def _on_view_changed(self, index: int):
        """Switch stacked widget view."""
        self.stack.setCurrentIndex(index)

        # If switching to evolution view and no data loaded yet, trigger fetch
        if index == 2 and self._meetings:
            current_text = self.evolution_view.meeting_combo.currentText()
            if current_text:
                self._on_evolution_meeting_changed(current_text)

    def _on_evolution_meeting_changed(self, meeting_str: str):
        """Fetch historical data for selected meeting in background."""
        if not meeting_str or not self._meetings or not self._target_rate:
            return

        # Parse meeting date from string
        try:
            meeting_date = datetime.strptime(meeting_str, "%b %d, %Y").date()
        except ValueError:
            return

        self._cancel_evolution_fetch()
        self._show_loading("Fetching historical probabilities...")

        lookback = self.evolution_view.get_lookback_days()

        self._evolution_thread = QThread()
        self._evolution_worker = _EvolutionFetchWorker(
            meeting_date, self._meetings, self._target_rate, lookback
        )
        self._evolution_worker.moveToThread(self._evolution_thread)

        self._evolution_thread.started.connect(self._evolution_worker.run)
        self._evolution_worker.finished.connect(self._on_evolution_fetched)
        self._evolution_worker.error.connect(self._on_evolution_error)
        self._evolution_worker.finished.connect(self._evolution_thread.quit)
        self._evolution_worker.error.connect(self._evolution_thread.quit)

        self._evolution_thread.start()

    def _on_evolution_fetched(self, evolution_df):
        """Handle evolution data fetch."""
        self._hide_loading()
        import pandas as pd
        if evolution_df is not None and isinstance(evolution_df, pd.DataFrame) and not evolution_df.empty:
            self.evolution_view.update_data(evolution_df)
        else:
            self.evolution_view.show_placeholder(
                "No historical data available for this meeting."
            )

    def _on_evolution_error(self, error_msg: str):
        """Handle evolution fetch error."""
        self._hide_loading()
        self.evolution_view.show_placeholder(f"Error: {error_msg}")

    # ========== Settings ==========

    def _on_settings_clicked(self):
        """Open settings dialog."""
        from PySide6.QtWidgets import QDialog
        from .widgets.rate_probability_settings_dialog import RateProbabilitySettingsDialog

        dialog = RateProbabilitySettingsDialog(
            self.theme_manager,
            current_settings=self.settings_manager.get_all_settings(),
            parent=self,
        )
        if dialog.exec() == QDialog.Accepted:
            new_settings = dialog.get_settings()
            if new_settings:
                self.settings_manager.update_settings(new_settings)
                self._apply_settings()

    def _apply_settings(self):
        """Push current settings to all views."""
        settings = self.settings_manager.get_all_settings()
        self.table_view.apply_settings(settings)
        self.rate_path_view.apply_settings(settings)
        self.evolution_view.apply_settings(settings)

    # ========== Loading Overlay ==========

    def _show_loading(self, message: str = "Loading..."):
        if self._loading_overlay is None:
            self._loading_overlay = LoadingOverlay(self, self.theme_manager, message)
        else:
            self._loading_overlay.set_message(message)
        self._loading_overlay.show()
        self._loading_overlay.raise_()

    def _hide_loading(self):
        if self._loading_overlay:
            self._loading_overlay.hide()

    # ========== Theme ==========

    def _apply_theme(self):
        """Apply theme styling."""
        theme = self.theme_manager.current_theme
        if theme == "dark":
            bg_color = "#1e1e1e"
        elif theme == "light":
            bg_color = "#ffffff"
        else:
            bg_color = "#0d1420"
        self.setStyleSheet(f"background-color: {bg_color};")

    def resizeEvent(self, event):
        """Handle resize to reposition loading overlay."""
        super().resizeEvent(event)
        if self._loading_overlay:
            self._loading_overlay.resize(self.size())
