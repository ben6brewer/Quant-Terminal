"""Rate Probability Module - FOMC rate decision probabilities from fed funds futures."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, List, Optional, Tuple

from PySide6.QtWidgets import QVBoxLayout, QStackedWidget
from PySide6.QtCore import QThread

from app.core.theme_manager import ThemeManager
from app.ui.modules.fred_base_module import FredDataModule

from .services.rate_probability_service import RateProbabilityService
from .services.rate_probability_settings_manager import RateProbabilitySettingsManager
from .widgets.rate_probability_toolbar import RateProbabilityToolbar
from .widgets.probability_table_view import ProbabilityTableView
from .widgets.rate_path_chart import RatePathChart
from .widgets.probability_evolution_chart import ProbabilityEvolutionChart

if TYPE_CHECKING:
    import pandas as pd


class RateProbabilityModule(FredDataModule):
    """Rate Probability module - CME FedWatch-style FOMC rate probabilities."""

    def __init__(self, theme_manager: ThemeManager, parent=None):
        # Rate probability state (set before super().__init__)
        self._futures_data = None
        self._target_rate = None
        self._probabilities = None
        self._meetings: List[date] = []
        self._rate_path = None

        # Second worker pair for evolution fetch
        self._evolution_thread: Optional[QThread] = None
        self._evolution_worker = None

        super().__init__(theme_manager, parent)

    # ── Required FredDataModule implementations ──────────────────────────

    def create_toolbar(self):
        return RateProbabilityToolbar(self.theme_manager)

    def create_chart(self):
        return ProbabilityTableView(self.theme_manager)

    def create_settings_manager(self):
        return RateProbabilitySettingsManager()

    def get_fred_service(self):
        return RateProbabilityService.fetch_all_data

    def get_loading_message(self):
        return "Fetching fed funds futures..."

    def extract_chart_data(self, result):
        return ()  # Not used — _on_data_fetched is overridden

    def get_fail_message(self):
        return "Failed to fetch data."

    # ── UI Setup (override for stacked widget) ───────────────────────────

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.toolbar = self.create_toolbar()
        layout.addWidget(self.toolbar)

        self.stack = QStackedWidget()
        layout.addWidget(self.stack, stretch=1)

        # View 0: FedWatch probability table
        self.table_view = ProbabilityTableView(self.theme_manager)
        self.chart = self.table_view  # Base class compat
        self.stack.addWidget(self.table_view)

        # View 1: Rate path chart
        self.rate_path_view = RatePathChart(self.theme_manager)
        self.stack.addWidget(self.rate_path_view)

        # View 2: Evolution chart
        self.evolution_view = ProbabilityEvolutionChart(self.theme_manager)
        self.stack.addWidget(self.evolution_view)

    def _connect_extra_signals(self):
        self.toolbar.view_changed.connect(self._on_view_changed)
        self.evolution_view.meeting_changed.connect(self._on_evolution_meeting_changed)

    # ── API Key (special: fetch even without key) ────────────────────────

    def _show_api_key_dialog(self):
        from app.ui.widgets.common.api_key_dialog import APIKeyDialog
        from app.services.fred_api_key_service import FredApiKeyService

        dialog = APIKeyDialog(self.theme_manager, parent=self)
        if dialog.exec():
            key = dialog.get_api_key()
            if key:
                FredApiKeyService.set_api_key(key)
        # Always fetch — futures data doesn't need FRED
        self._fetch_data()

    # ── Data & Rendering ─────────────────────────────────────────────────

    def _on_data_fetched(self, result):
        if result is None:
            self.table_view.show_placeholder("Failed to fetch data.")
            return

        self._data = result
        self._futures_data = result["futures_df"]
        self._target_rate = result["target_rate"]
        self._probabilities = result["probabilities_df"]
        self._meetings = result["meetings"]
        self._rate_path = result["rate_path"]

        self.toolbar.update_info(
            target_rate=self._target_rate,
            next_meeting=result["next_meeting"],
            days_until=result["days_until"],
        )

        self._render()

    def _render(self):
        if self._data is None:
            return

        # Update table view
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

    # ── View switching ───────────────────────────────────────────────────

    def _on_view_changed(self, index: int):
        self.stack.setCurrentIndex(index)
        # If switching to evolution view and meetings loaded, trigger fetch
        if index == 2 and self._meetings:
            current_text = self.evolution_view.meeting_combo.currentText()
            if current_text:
                self._on_evolution_meeting_changed(current_text)

    # ── Evolution data (second worker) ───────────────────────────────────

    def hideEvent(self, event):
        self._cancel_evolution_fetch()
        super().hideEvent(event)

    def _on_evolution_meeting_changed(self, meeting_str: str):
        if not meeting_str or not self._meetings or not self._target_rate:
            return

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
        self._hide_loading()
        self._cleanup_evolution_worker()
        self.evolution_view.show_placeholder(f"Error: {error_msg}")

    def _cancel_evolution_fetch(self):
        if self._evolution_worker is not None:
            try:
                self._evolution_worker.finished.disconnect()
                self._evolution_worker.error.disconnect()
            except (RuntimeError, TypeError):
                pass
        self._cleanup_evolution_worker()

    def _cleanup_evolution_worker(self):
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

    # ── Settings ─────────────────────────────────────────────────────────

    def create_settings_dialog(self, current_settings):
        from .widgets.rate_probability_settings_dialog import RateProbabilitySettingsDialog
        return RateProbabilitySettingsDialog(
            self.theme_manager,
            current_settings=current_settings,
            parent=self,
        )

    def _apply_extra_settings(self):
        settings = self.settings_manager.get_all_settings()
        if hasattr(self, "table_view"):
            self.table_view.apply_settings(settings)
        if hasattr(self, "rate_path_view"):
            self.rate_path_view.apply_settings(settings)
        if hasattr(self, "evolution_view"):
            self.evolution_view.apply_settings(settings)
