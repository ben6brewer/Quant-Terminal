"""CPI Module - Consumer Price Index visualization with headline and breakdown views."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6.QtWidgets import QVBoxLayout, QStackedWidget

from app.ui.modules.fred_base_module import FredDataModule
from app.ui.modules.inflation.services import InflationFredService
from .widgets.cpi_toolbar import CpiToolbar
from .widgets.cpi_headline_chart import CpiHeadlineChart
from .widgets.cpi_component_breakdown_chart import CpiComponentBreakdownChart

if TYPE_CHECKING:
    import pandas as pd


class CpiModule(FredDataModule):
    """CPI module - Consumer Price Index visualization from FRED data.

    Uses QStackedWidget for dual views (headline + breakdown),
    overriding _setup_ui and _render for custom layout.
    """

    SETTINGS_FILENAME = "cpi_settings.json"
    DEFAULT_SETTINGS = {
        "show_breakdown": True,
        "show_gridlines": True,
        "show_reference_lines": True,
        "show_crosshair": True,
        "show_value_label": True,
        "show_date_label": True,
        "show_hover_tooltip": True,
        "show_headline_overlay": True,
        "show_legend": True,
    }

    def create_toolbar(self):
        return CpiToolbar(self.theme_manager)

    def create_chart(self):
        # Dummy — not used; we use dual charts via _setup_ui override
        return CpiHeadlineChart()

    def get_fred_service(self):
        return InflationFredService.fetch_all_data

    def get_loading_message(self):
        return "Fetching CPI data from FRED..."

    def get_fail_message(self):
        return "Failed to fetch CPI data."

    # ── Custom UI (dual chart views) ──────────────────────────────────────

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.toolbar = self.create_toolbar()
        layout.addWidget(self.toolbar)

        self.stack = QStackedWidget()
        layout.addWidget(self.stack, stretch=1)

        self.headline_view = CpiHeadlineChart()
        self.stack.addWidget(self.headline_view)

        self.breakdown_view = CpiComponentBreakdownChart()
        self.stack.addWidget(self.breakdown_view)

        # Set self.chart to headline for API key dialog placeholder
        self.chart = self.headline_view

    # ── Data handling ─────────────────────────────────────────────────────

    def update_toolbar_info(self, result):
        stats = InflationFredService.get_latest_stats(result)
        if stats and "headline_cpi" in stats:
            self.toolbar.update_info(
                headline=stats["headline_cpi"],
                date_str=stats.get("date", ""),
            )

    def extract_chart_data(self, result):
        # Not used — _render is overridden
        return ()

    def _on_data_fetched(self, result):
        if result is None:
            self.headline_view.show_placeholder("Failed to fetch CPI data.")
            self.breakdown_view.show_placeholder("Failed to fetch CPI data.")
            return

        cpi_df = result.get("cpi")
        if cpi_df is None or cpi_df.empty:
            self.headline_view.show_placeholder("Failed to fetch CPI data.")
            self.breakdown_view.show_placeholder("Failed to fetch CPI data.")
            return

        self._data = result
        self.update_toolbar_info(result)
        self._render()

    def _render(self):
        if self._data is None:
            return
        cpi_df = self._data.get("cpi")
        if cpi_df is None or cpi_df.empty:
            return
        sliced = self.slice_data(cpi_df)
        settings = self.settings_manager.get_all_settings()
        if self.stack.currentIndex() == 1:
            self.breakdown_view.update_data(sliced, settings)
        else:
            self.headline_view.update_data(sliced, settings)

    def _on_fetch_error(self, error_msg: str):
        self.headline_view.show_placeholder(f"Error fetching CPI data: {error_msg}")
        self.breakdown_view.show_placeholder(f"Error fetching CPI data: {error_msg}")

    # ── Settings ──────────────────────────────────────────────────────────

    def create_settings_dialog(self, current_settings):
        from .widgets.cpi_settings_dialog import CpiSettingsDialog
        return CpiSettingsDialog(
            self.theme_manager,
            current_settings=current_settings,
            parent=self,
        )

    def _apply_extra_settings(self):
        show_breakdown = self.settings_manager.get_setting("show_breakdown")
        self.stack.setCurrentIndex(1 if show_breakdown else 0)

    # ── Theme ─────────────────────────────────────────────────────────────

    def _apply_theme(self):
        # Call BaseModule._apply_theme for background, skip FredDataModule's chart.set_theme
        from app.ui.modules.base_module import BaseModule
        BaseModule._apply_theme(self)
        theme = self.theme_manager.current_theme
        self.headline_view.set_theme(theme)
        self.breakdown_view.set_theme(theme)
