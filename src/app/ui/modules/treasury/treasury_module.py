"""Treasury Module - US Treasury yield curve, rates, and spread visualization."""

from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING, Dict, List, Optional

from PySide6.QtWidgets import QVBoxLayout, QStackedWidget

from app.core.theme_manager import ThemeManager
from app.ui.modules.fred_base_module import FredDataModule

from .services.treasury_fred_service import TreasuryFredService, TENOR_LABELS, TENOR_YEARS
from .services.treasury_interpolation import TreasuryInterpolation
from .services.treasury_settings_manager import TreasurySettingsManager
from .widgets.treasury_toolbar import TreasuryToolbar
from .widgets.treasury_yield_curve_chart import TreasuryYieldCurveChart, CurveData
from .widgets.treasury_rates_chart import TreasuryRatesChart
from .widgets.treasury_spread_chart import TreasurySpreadChart

if TYPE_CHECKING:
    import pandas as pd

# Lookback period to number of trading days mapping
LOOKBACK_DAYS = {
    "1Y": 252, "2Y": 504, "5Y": 1260, "10Y": 2520, "20Y": 5040, "Max": None,
}


class TreasuryModule(FredDataModule):
    """Treasury module - yield curve, rates time series, and spread visualization."""

    def __init__(self, theme_manager: ThemeManager, parent=None):
        # Treasury-specific state (set before super().__init__ which calls _setup_ui)
        self._curve_stale = False
        self._rates_stale = False
        self._spread_stale = False
        self._active_overlays: Dict[str, date] = {}
        self._custom_dates: List[str] = []
        self._current_interpolation: str = "Cubic Spline"
        super().__init__(theme_manager, parent)

    # ── Required FredDataModule implementations ──────────────────────────

    def create_toolbar(self):
        return TreasuryToolbar(self.theme_manager)

    def create_chart(self):
        return TreasuryYieldCurveChart()

    def create_settings_manager(self):
        return TreasurySettingsManager()

    def get_fred_service(self):
        return TreasuryFredService.fetch_all_treasury_data

    def get_loading_message(self):
        return "Fetching Treasury data from FRED..."

    def extract_chart_data(self, result):
        return ()  # Not used — _render is overridden

    def get_lookback_map(self):
        return LOOKBACK_DAYS

    def get_fail_message(self):
        return "Failed to fetch Treasury data."

    # ── UI Setup (override for stacked widget) ───────────────────────────

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.toolbar = self.create_toolbar()
        layout.addWidget(self.toolbar)

        self.stack = QStackedWidget()
        layout.addWidget(self.stack, stretch=1)

        # View 0: Yield Curve
        self.curve_view = TreasuryYieldCurveChart()
        self.chart = self.curve_view  # Base class compat (show_placeholder, set_theme)
        self.stack.addWidget(self.curve_view)

        # View 1: Rates Time Series
        self.rates_view = TreasuryRatesChart()
        self.stack.addWidget(self.rates_view)

        # View 2: Spread
        self.spread_view = TreasurySpreadChart()
        self.stack.addWidget(self.spread_view)

    def _connect_extra_signals(self):
        self.toolbar.view_changed.connect(self._on_view_changed)
        self.toolbar.interpolation_changed.connect(self._on_interpolation_changed)
        self.toolbar.overlay_toggled.connect(self._on_overlay_toggled)
        self.toolbar.custom_date_selected.connect(self._on_custom_date_selected)
        self.toolbar.overlay_cleared.connect(self._on_overlay_cleared)

    # ── Data & Rendering ─────────────────────────────────────────────────

    def update_toolbar_info(self, result):
        latest = TreasuryFredService.get_latest_yields(result)
        if latest and "10y" in latest:
            self.toolbar.update_info(yield_10y=latest["10y"])

    def _render(self):
        """Push data to the visible chart; mark others stale."""
        if self._data is None or self._data.empty:
            return

        settings = self.settings_manager.get_all_settings()
        current = self.stack.currentIndex()

        if current == 0:
            self._build_curves()
            self._curve_stale = False
            self._rates_stale = True
            self._spread_stale = True
        elif current == 1:
            sliced = self.slice_data(self._data)
            self.rates_view.update_data(sliced, settings)
            self._rates_stale = False
            self._curve_stale = True
            self._spread_stale = True
        else:
            sliced = self.slice_data(self._data)
            self.spread_view.update_data(sliced, settings)
            self._spread_stale = False
            self._curve_stale = True
            self._rates_stale = True

    def _flush_stale_view(self, index: int):
        """Re-render the chart at *index* if it was marked stale."""
        if self._data is None or self._data.empty:
            return

        settings = self.settings_manager.get_all_settings()

        if index == 0 and self._curve_stale:
            self._build_curves()
            self._curve_stale = False
        elif index == 1 and self._rates_stale:
            sliced = self.slice_data(self._data)
            self.rates_view.update_data(sliced, settings)
            self._rates_stale = False
        elif index == 2 and self._spread_stale:
            sliced = self.slice_data(self._data)
            self.spread_view.update_data(sliced, settings)
            self._spread_stale = False

    def _on_view_changed(self, index: int):
        """Switch stacked widget view; render stale chart if needed."""
        self.stack.setCurrentIndex(index)
        self._flush_stale_view(index)

    # ========== Curve Overlay Management ==========

    def _on_interpolation_changed(self, method: str):
        self._current_interpolation = method
        self._build_curves()

    def _on_overlay_toggled(self, key: str, active: bool):
        if active:
            target = self._compute_overlay_date(key)
            if target:
                self._active_overlays[key] = target
        else:
            self._active_overlays.pop(key, None)
        self._build_curves()

    def _on_custom_date_selected(self, date_str: str):
        if date_str not in self._custom_dates:
            self._custom_dates.append(date_str)
        self._build_curves()

    def _on_overlay_cleared(self):
        self._active_overlays.clear()
        self._custom_dates.clear()
        self._build_curves()

    def _compute_overlay_date(self, period_key: str) -> Optional[date]:
        from dateutil.relativedelta import relativedelta

        today = date.today()
        period_map = {
            "1W": timedelta(weeks=1),
            "1M": relativedelta(months=1),
            "6M": relativedelta(months=6),
            "1Y": relativedelta(years=1),
            "2Y": relativedelta(years=2),
            "5Y": relativedelta(years=5),
        }
        delta = period_map.get(period_key)
        if delta is None:
            return None
        return today - delta

    def _build_curves(self):
        """Build curve data and update the chart."""
        if self._data is None or self._data.empty:
            return

        curves: List[CurveData] = []

        # Today's curve (always first, color index 0)
        today_curve = self._make_curve(date.today(), 0, "Today")
        if today_curve:
            curves.append(today_curve)

        # Overlay curves
        color_idx = 1
        for key, target_date in self._active_overlays.items():
            curve = self._make_curve(target_date, color_idx)
            if curve:
                curves.append(curve)
                color_idx += 1

        # Custom date curves
        for date_str in self._custom_dates:
            try:
                from datetime import datetime

                target = datetime.strptime(date_str, "%Y-%m-%d").date()
                curve = self._make_curve(target, color_idx)
                if curve:
                    curves.append(curve)
                    color_idx += 1
            except ValueError:
                pass

        # Get fed funds rate for reference line
        fed_funds_rate = None
        if "Fed Funds" in self._data.columns:
            last_ff = self._data["Fed Funds"].dropna()
            if not last_ff.empty:
                fed_funds_rate = float(last_ff.iloc[-1])

        settings = self.settings_manager.get_all_settings()
        self.curve_view.plot_curves(curves, settings, fed_funds_rate)

    def _make_curve(
        self, target_date: date, color_index: int, label: Optional[str] = None
    ) -> Optional[CurveData]:
        yields_dict = TreasuryFredService.get_yields_for_date(self._data, target_date)
        if not yields_dict:
            return None

        actual_date = TreasuryFredService.get_actual_date(self._data, target_date)
        if label is None:
            label = actual_date.strftime("%Y-%m-%d") if actual_date else str(target_date)

        maturities = []
        yield_values = []
        for tenor in TENOR_LABELS:
            if tenor in yields_dict:
                maturities.append(TENOR_YEARS[tenor])
                yield_values.append(yields_dict[tenor])

        if len(maturities) < 3:
            return None

        if self._current_interpolation == "Nelson-Siegel":
            smooth_x, smooth_y = TreasuryInterpolation.interpolate_nelson_siegel(
                maturities, yield_values
            )
        elif self._current_interpolation == "Linear":
            smooth_x, smooth_y = TreasuryInterpolation.interpolate_linear(
                maturities, yield_values
            )
        else:
            smooth_x, smooth_y = TreasuryInterpolation.interpolate_cubic_spline(
                maturities, yield_values
            )

        return CurveData(
            label=label,
            maturities=maturities,
            yields=yield_values,
            smooth_x=smooth_x,
            smooth_y=smooth_y,
            color_index=color_index,
            yields_dict=yields_dict,
        )

    # ========== Settings ==========

    def create_settings_dialog(self, current_settings):
        from .widgets.treasury_settings_dialog import TreasurySettingsDialog
        return TreasurySettingsDialog(
            self.theme_manager,
            current_settings=current_settings,
            parent=self,
        )

    def _apply_settings(self):
        lookback = self.settings_manager.get_setting("lookback") or "2Y"
        self._current_lookback = lookback
        if hasattr(self, "toolbar"):
            self.toolbar.set_active_lookback(lookback)
            self.toolbar.set_active_view(0)
        if hasattr(self, "stack"):
            self.stack.setCurrentIndex(0)

    # ========== Theme ==========

    def _apply_theme(self):
        super()._apply_theme()
        theme = self.theme_manager.current_theme
        if hasattr(self, "rates_view"):
            self.rates_view.set_theme(theme)
        if hasattr(self, "spread_view"):
            self.spread_view.set_theme(theme)
