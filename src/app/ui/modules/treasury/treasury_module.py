"""Treasury Module - US Treasury yield curve, rates, and spread visualization."""

from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING, Dict, List, Optional

from PySide6.QtWidgets import QVBoxLayout, QStackedWidget

from app.core.theme_manager import ThemeManager
from app.ui.modules.base_module import BaseModule

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
    "1Y": 252,
    "2Y": 504,
    "5Y": 1260,
    "10Y": 2520,
    "20Y": 5040,
    "Max": None,
}


class TreasuryModule(BaseModule):
    """Treasury module - yield curve, rates time series, and spread visualization."""

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(theme_manager, parent)

        # Settings
        self.settings_manager = TreasurySettingsManager()

        # State
        self._data_initialized = False
        self._df: Optional["pd.DataFrame"] = None
        self._current_lookback = "2Y"
        self._curve_stale = False
        self._rates_stale = False
        self._spread_stale = False

        # Curve overlay state
        self._active_overlays: Dict[str, date] = {}  # period_key -> target date
        self._custom_dates: List[str] = []  # YYYY-MM-DD strings
        self._current_interpolation: str = "Cubic Spline"

        self._setup_ui()
        self._connect_signals()
        self._apply_settings()
        self._apply_theme()

    def _setup_ui(self):
        """Setup module UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.toolbar = TreasuryToolbar(self.theme_manager)
        layout.addWidget(self.toolbar)

        self.stack = QStackedWidget()
        layout.addWidget(self.stack, stretch=1)

        # View 0: Yield Curve
        self.curve_view = TreasuryYieldCurveChart()
        self.stack.addWidget(self.curve_view)

        # View 1: Rates Time Series
        self.rates_view = TreasuryRatesChart()
        self.stack.addWidget(self.rates_view)

        # View 2: Spread
        self.spread_view = TreasurySpreadChart()
        self.stack.addWidget(self.spread_view)

    def _connect_signals(self):
        """Connect signals to slots."""
        self.toolbar.home_clicked.connect(self.home_clicked.emit)
        self.toolbar.view_changed.connect(self._on_view_changed)
        self.toolbar.lookback_changed.connect(self._on_lookback_changed)
        self.toolbar.settings_clicked.connect(self._on_settings_clicked)
        self.toolbar.interpolation_changed.connect(self._on_interpolation_changed)
        self.toolbar.overlay_toggled.connect(self._on_overlay_toggled)
        self.toolbar.custom_date_selected.connect(self._on_custom_date_selected)
        self.toolbar.overlay_cleared.connect(self._on_overlay_cleared)
        self.theme_manager.theme_changed.connect(self._on_theme_changed_lazy)

    def showEvent(self, event):
        super().showEvent(event)
        if not self._data_initialized:
            self._data_initialized = True
            self._initialize_data()

    def hideEvent(self, event):
        self._cancel_worker()
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
            self.curve_view.show_placeholder(
                "FRED API key required for Treasury data.\n"
                "Set your key in Settings > API Keys."
            )

    def _fetch_data(self):
        """Fetch all Treasury data in background thread."""
        self._run_worker(
            TreasuryFredService.fetch_all_treasury_data,
            loading_message="Fetching Treasury data from FRED...",
            on_complete=self._on_data_fetched,
            on_error=self._on_fetch_error,
        )

    def _on_data_fetched(self, result):
        """Handle successful data fetch."""
        self._hide_loading()
        self._cleanup_worker()

        if result is None:
            self.curve_view.show_placeholder("Failed to fetch Treasury data.")
            return

        self._df = result

        # Update toolbar info
        latest = TreasuryFredService.get_latest_yields(result)
        if latest and "10y" in latest:
            self.toolbar.update_info(yield_10y=latest["10y"])

        # Push data to all views
        self._update_all_views()

    def _on_fetch_error(self, error_msg: str):
        """Handle fetch error."""
        self._hide_loading()
        self._cleanup_worker()
        self.curve_view.show_placeholder(f"Error fetching Treasury data: {error_msg}")

    def _update_all_views(self):
        """Push data to the visible chart; mark others stale."""
        if self._df is None or self._df.empty:
            return

        settings = self.settings_manager.get_all_settings()
        current = self.stack.currentIndex()

        if current == 0:
            self._build_curves()
            self._curve_stale = False
            self._rates_stale = True
            self._spread_stale = True
        elif current == 1:
            sliced = self._slice_by_lookback(self._df)
            self.rates_view.update_data(sliced, settings)
            self._rates_stale = False
            self._curve_stale = True
            self._spread_stale = True
        else:
            sliced = self._slice_by_lookback(self._df)
            self.spread_view.update_data(sliced, settings)
            self._spread_stale = False
            self._curve_stale = True
            self._rates_stale = True

    def _slice_by_lookback(self, df: "pd.DataFrame") -> "pd.DataFrame":
        """Slice DataFrame to the current lookback period."""
        lb = self._current_lookback
        # Custom ISO date string
        if "-" in lb:
            return df.loc[lb:]
        days = LOOKBACK_DAYS.get(lb)
        if days is None:
            return df
        return df.tail(days)

    def _on_view_changed(self, index: int):
        """Switch stacked widget view; render stale chart if needed."""
        self.stack.setCurrentIndex(index)
        self._flush_stale_view(index)

    def _flush_stale_view(self, index: int):
        """Re-render the chart at *index* if it was marked stale."""
        if self._df is None or self._df.empty:
            return

        settings = self.settings_manager.get_all_settings()

        if index == 0 and self._curve_stale:
            self._build_curves()
            self._curve_stale = False
        elif index == 1 and self._rates_stale:
            sliced = self._slice_by_lookback(self._df)
            self.rates_view.update_data(sliced, settings)
            self._rates_stale = False
        elif index == 2 and self._spread_stale:
            sliced = self._slice_by_lookback(self._df)
            self.spread_view.update_data(sliced, settings)
            self._spread_stale = False

    def _on_lookback_changed(self, lookback: str):
        """Handle lookback period change."""
        self._current_lookback = lookback
        self._update_all_views()

    # ========== Curve Overlay Management ==========

    def _on_interpolation_changed(self, method: str):
        """Handle interpolation method change."""
        self._current_interpolation = method
        self._build_curves()

    def _on_overlay_toggled(self, key: str, active: bool):
        """Handle overlay period toggle."""
        if active:
            target = self._compute_overlay_date(key)
            if target:
                self._active_overlays[key] = target
        else:
            self._active_overlays.pop(key, None)
        self._build_curves()

    def _on_custom_date_selected(self, date_str: str):
        """Handle custom date overlay."""
        if date_str not in self._custom_dates:
            self._custom_dates.append(date_str)
        self._build_curves()

    def _on_overlay_cleared(self):
        """Handle clear all overlays."""
        self._active_overlays.clear()
        self._custom_dates.clear()
        self._build_curves()

    def _compute_overlay_date(self, period_key: str) -> Optional[date]:
        """Compute target date for an overlay period key."""
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
        if self._df is None or self._df.empty:
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
        if "Fed Funds" in self._df.columns:
            last_ff = self._df["Fed Funds"].dropna()
            if not last_ff.empty:
                fed_funds_rate = float(last_ff.iloc[-1])

        settings = self.settings_manager.get_all_settings()
        self.curve_view.plot_curves(curves, settings, fed_funds_rate)

    def _make_curve(
        self, target_date: date, color_index: int, label: Optional[str] = None
    ) -> Optional[CurveData]:
        """
        Build a CurveData for a given date.

        Args:
            target_date: Date to extract yields for
            color_index: Index into color palette
            label: Optional override label (e.g., "Today")

        Returns:
            CurveData with raw + interpolated data, or None if unavailable
        """
        yields_dict = TreasuryFredService.get_yields_for_date(self._df, target_date)
        if not yields_dict:
            return None

        actual_date = TreasuryFredService.get_actual_date(self._df, target_date)
        if label is None:
            label = actual_date.strftime("%Y-%m-%d") if actual_date else str(target_date)

        # Build parallel lists of maturities and yields
        maturities = []
        yield_values = []
        for tenor in TENOR_LABELS:
            if tenor in yields_dict:
                maturities.append(TENOR_YEARS[tenor])
                yield_values.append(yields_dict[tenor])

        if len(maturities) < 3:
            return None

        # Interpolate
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

    def _on_settings_clicked(self):
        """Open settings dialog."""
        from PySide6.QtWidgets import QDialog
        from .widgets.treasury_settings_dialog import TreasurySettingsDialog

        dialog = TreasurySettingsDialog(
            self.theme_manager,
            current_settings=self.settings_manager.get_all_settings(),
            parent=self,
        )
        if dialog.exec() == QDialog.Accepted:
            new_settings = dialog.get_settings()
            if new_settings:
                self.settings_manager.update_settings(new_settings)
                self._apply_settings()
                self._update_all_views()

    def _apply_settings(self):
        """Push current settings to all views and toolbar."""
        # Always start on curve view
        self.toolbar.set_active_view(0)
        self.stack.setCurrentIndex(0)

    def _apply_theme(self):
        """Apply theme to all child widgets."""
        super()._apply_theme()
        theme = self.theme_manager.current_theme
        self.curve_view.set_theme(theme)
        self.rates_view.set_theme(theme)
        self.spread_view.set_theme(theme)
