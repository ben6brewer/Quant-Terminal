"""Yield Curve Module - US Treasury yield curve visualization with historical overlays."""

from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING, Dict, List, Optional

from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtCore import Signal, QThread, QObject

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common.loading_overlay import LoadingOverlay
from app.ui.widgets.common.lazy_theme_mixin import LazyThemeMixin

from .services.fred_service import FredService, TENOR_LABELS, TENOR_YEARS
from .services.yield_curve_interpolation import YieldCurveInterpolation
from .widgets.yield_curve_chart import YieldCurveChart, CurveData
from .widgets.yield_curve_toolbar import YieldCurveToolbar

if TYPE_CHECKING:
    import pandas as pd


class _FetchWorker(QObject):
    """Background worker for fetching FRED data."""

    finished = Signal(object)  # DataFrame or None
    error = Signal(str)

    def run(self):
        try:
            df = FredService.fetch_all_yields()
            self.finished.emit(df)
        except Exception as e:
            self.error.emit(str(e))


class YieldCurveModule(LazyThemeMixin, QWidget):
    """
    Yield Curve module.

    Displays the US Treasury yield curve using FRED API data, with
    historical overlay comparisons and interpolation toggle.
    """

    home_clicked = Signal()

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._theme_dirty = False

        # State
        self._yield_data: Optional[pd.DataFrame] = None
        self._active_overlays: Dict[str, date] = {}  # period_key -> target date
        self._custom_dates: List[str] = []  # YYYY-MM-DD strings
        self._current_interpolation: str = "Cubic Spline"

        # Loading
        self._loading_overlay: Optional[LoadingOverlay] = None
        self._fetch_thread: Optional[QThread] = None
        self._fetch_worker: Optional[_FetchWorker] = None
        self._data_initialized = False

        self._setup_ui()
        self._connect_signals()
        self._apply_theme()

    def _setup_ui(self):
        """Setup module UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.toolbar = YieldCurveToolbar(self.theme_manager)
        layout.addWidget(self.toolbar)

        self.chart = YieldCurveChart(self.theme_manager)
        layout.addWidget(self.chart, stretch=1)

    def _connect_signals(self):
        """Connect signals to slots."""
        self.toolbar.home_clicked.connect(self.home_clicked.emit)
        self.toolbar.interpolation_changed.connect(self._on_interpolation_changed)
        self.toolbar.overlay_toggled.connect(self._on_overlay_toggled)
        self.toolbar.custom_date_selected.connect(self._on_custom_date_selected)
        self.toolbar.overlay_cleared.connect(self._on_overlay_cleared)
        self.theme_manager.theme_changed.connect(self._on_theme_changed_lazy)

    def showEvent(self, event):
        super().showEvent(event)
        self._check_theme_dirty()
        if not self._data_initialized:
            self._data_initialized = True
            self._initialize_data()

    def _initialize_data(self):
        """Check for API key and start data fetch."""
        if not FredService.has_api_key():
            self._show_api_key_dialog()
        else:
            self._fetch_data()

    def _show_api_key_dialog(self):
        """Show the FRED API key dialog on initial load when key is missing."""
        from app.ui.widgets.common.api_key_dialog import APIKeyDialog

        dialog = APIKeyDialog(self.theme_manager, parent=self)
        if dialog.exec():
            key = dialog.get_api_key()
            if key:
                FredService.set_api_key(key)
                self._fetch_data()
        else:
            self.chart.show_placeholder(
                "FRED API key required to display yield curve data."
            )

    def _fetch_data(self):
        """Fetch yield data in background thread."""
        # Cancel any existing fetch
        self._cancel_fetch()

        self._show_loading("Fetching Treasury yields...")

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

    def _on_data_fetched(self, df):
        """Handle successful data fetch."""
        import pandas as pd

        self._hide_loading()

        if df is None or (isinstance(df, pd.DataFrame) and df.empty):
            self.chart.show_placeholder("No yield data available. Check your FRED API key.")
            return

        self._yield_data = df
        self._build_curves()

    def _on_fetch_error(self, error_msg: str):
        """Handle fetch error."""
        self._hide_loading()
        self.chart.show_placeholder(f"Error fetching data: {error_msg}")

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
        if self._yield_data is None or self._yield_data.empty:
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

        self.chart.plot_curves(curves)

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
        yields_dict = FredService.get_yields_for_date(self._yield_data, target_date)
        if not yields_dict:
            return None

        actual_date = FredService.get_actual_date(self._yield_data, target_date)
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
            smooth_x, smooth_y = YieldCurveInterpolation.interpolate_nelson_siegel(
                maturities, yield_values
            )
        elif self._current_interpolation == "Linear":
            smooth_x, smooth_y = YieldCurveInterpolation.interpolate_linear(
                maturities, yield_values
            )
        else:
            smooth_x, smooth_y = YieldCurveInterpolation.interpolate_cubic_spline(
                maturities, yield_values
            )

        return CurveData(
            label=label,
            maturities=maturities,
            yields=yield_values,
            smooth_x=smooth_x,
            smooth_y=smooth_y,
            color_index=color_index,
        )

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
        else:  # bloomberg
            bg_color = "#0d1420"
        self.setStyleSheet(f"background-color: {bg_color};")

    def resizeEvent(self, event):
        """Handle resize to reposition loading overlay."""
        super().resizeEvent(event)
        if self._loading_overlay:
            self._loading_overlay.resize(self.size())
