"""Rate Probability Module - FOMC rate decision probabilities from fed funds futures."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, List, Optional, Tuple

from PySide6.QtWidgets import QVBoxLayout, QStackedWidget
from PySide6.QtCore import QThread

from app.core.theme_manager import ThemeManager
from app.ui.modules.base_module import BaseModule

from .services.rate_probability_service import RateProbabilityService
from .services.rate_probability_settings_manager import RateProbabilitySettingsManager
from .widgets.rate_probability_toolbar import RateProbabilityToolbar
from .widgets.probability_table_view import ProbabilityTableView
from .widgets.rate_path_chart import RatePathChart
from .widgets.probability_evolution_chart import ProbabilityEvolutionChart

if TYPE_CHECKING:
    import pandas as pd


class RateProbabilityModule(BaseModule):
    """Rate Probability module - CME FedWatch-style FOMC rate probabilities."""

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(theme_manager, parent)

        # Settings
        self.settings_manager = RateProbabilitySettingsManager()

        # State
        self._data_initialized = False
        self._futures_data = None
        self._target_rate = None
        self._probabilities = None
        self._meetings: List[date] = []
        self._rate_path = None

        # Second worker pair for evolution fetch (runs concurrently with primary)
        self._evolution_thread: Optional[QThread] = None
        self._evolution_worker = None

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
        if not self._data_initialized:
            self._data_initialized = True
            self._initialize_data()

    def hideEvent(self, event):
        self._cancel_worker()
        self._cancel_evolution_fetch()
        super().hideEvent(event)

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
        self._run_worker(
            RateProbabilityService.fetch_all_data,
            loading_message="Fetching fed funds futures...",
            on_complete=self._on_data_fetched,
            on_error=self._on_fetch_error,
        )

    def _cancel_evolution_fetch(self):
        """Cancel any in-progress evolution fetch with proper Qt cleanup."""
        if self._evolution_worker is not None:
            try:
                self._evolution_worker.finished.disconnect()
                self._evolution_worker.error.disconnect()
            except (RuntimeError, TypeError):
                pass
        self._cleanup_evolution_worker()

    def _on_data_fetched(self, result):
        """Handle successful data fetch."""
        self._hide_loading()
        self._cleanup_worker()

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
        self._cleanup_worker()
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

        from app.services.calculation_worker import CalculationWorker

        self._evolution_thread = QThread()
        self._evolution_worker = CalculationWorker(
            RateProbabilityService.fetch_evolution_data,
            meeting_date, self._meetings, self._target_rate, lookback,
        )
        self._evolution_worker.moveToThread(self._evolution_thread)

        self._evolution_thread.started.connect(self._evolution_worker.run)
        self._evolution_worker.finished.connect(self._on_evolution_fetched)
        self._evolution_worker.error.connect(self._on_evolution_error)

        self._evolution_thread.start()

    def _on_evolution_fetched(self, evolution_df):
        """Handle evolution data fetch."""
        self._hide_loading()
        self._cleanup_evolution_worker()
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
        self._cleanup_evolution_worker()
        self.evolution_view.show_placeholder(f"Error: {error_msg}")

    def _cleanup_evolution_worker(self):
        """Clean up the evolution worker and thread."""
        if self._evolution_thread is not None:
            self._evolution_thread.quit()
            if not self._evolution_thread.wait(5000):
                self._evolution_thread.terminate()
                self._evolution_thread.wait(1000)
        if self._evolution_worker is not None:
            self._evolution_worker.deleteLater()
        if self._evolution_thread is not None:
            self._evolution_thread.deleteLater()
        self._evolution_worker = None
        self._evolution_thread = None

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
