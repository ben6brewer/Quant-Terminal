"""OLS Scatter Chart - Scatter plot with regression line and confidence bands."""

from __future__ import annotations

from typing import TYPE_CHECKING, List

import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from app.ui.widgets.charting.base_chart import BaseChart

if TYPE_CHECKING:
    from ..services.ols_regression_service import OLSRegressionResult


class OLSScatterChart(BaseChart):
    """Scatter plot with OLS regression line, confidence bands, and equation overlay."""

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # Create plot
        self.plot_item = self.addPlot()
        self.view_box = self.plot_item.getViewBox()
        self.view_box.setMenuEnabled(False)
        self.view_box.setMouseEnabled(x=False, y=False)
        self.view_box.disableAutoRange()
        self.view_box.setRange(xRange=(0, 1), yRange=(0, 1), padding=0)

        # Lock mouse interaction
        self.view_box.wheelEvent = lambda ev: ev.ignore()
        self.view_box.mouseDragEvent = lambda ev, axis=None: ev.ignore()
        self.view_box.mouseClickEvent = lambda ev: ev.ignore()

        # Disable SI prefix
        self.plot_item.getAxis("bottom").enableAutoSIPrefix(False)
        self.plot_item.getAxis("left").enableAutoSIPrefix(False)

        # Axis styling
        axis_label_style = {"font-size": "14px", "font-weight": "bold"}
        self.plot_item.setLabel("bottom", "X", **axis_label_style)
        self.plot_item.setLabel("left", "Y", **axis_label_style)
        self.plot_item.getAxis("bottom").setHeight(60)
        self.plot_item.getAxis("bottom").setStyle(tickTextOffset=12)
        self.plot_item.getAxis("left").setWidth(100)
        self.plot_item.getAxis("left").setStyle(tickTextOffset=12)

        # Settings
        self._show_gridlines = True
        self._show_confidence_bands = True
        self._show_equation = True

        # Tracked items for clearing
        self._scatter = None
        self._reg_line = None
        self._ci_fill = None
        self._ci_upper_curve = None
        self._ci_lower_curve = None
        self._equation_text = None
        self._placeholder = None

        self.set_theme("dark")

    def apply_settings(self, settings: dict) -> None:
        """Apply display settings."""
        self._show_gridlines = settings.get("show_gridlines", True)
        self._show_confidence_bands = settings.get("show_confidence_bands", True)
        self._show_equation = settings.get("show_equation", True)

    def set_theme(self, theme: str) -> None:
        """Apply theme, then fix axis text color."""
        super().set_theme(theme)
        text_color = self._get_label_text_color()
        text_pen = pg.mkPen(color=text_color)
        for axis_name in ("bottom", "left"):
            self.plot_item.getAxis(axis_name).setTextPen(text_pen)
        self.plot_item.showGrid(x=self._show_gridlines, y=self._show_gridlines)

    def plot_results(self, result: "OLSRegressionResult") -> None:
        """Plot scatter, regression line, and optional confidence bands."""
        self._clear_items()

        text_color = self._get_label_text_color()

        # Axis labels
        axis_label_style = {"font-size": "14px", "font-weight": "bold"}
        self.plot_item.setLabel("bottom", result.x_label, **axis_label_style)
        self.plot_item.setLabel("left", result.y_label, **axis_label_style)

        # Scatter points
        accent = self._get_accent_color()
        self._scatter = pg.ScatterPlotItem(
            x=result.x_values,
            y=result.y_values,
            brush=pg.mkBrush(*accent, 100),
            pen=pg.mkPen(*accent, 180),
            size=5,
        )
        self.plot_item.addItem(self._scatter)

        # Regression line (red)
        self._reg_line = self.plot_item.plot(
            x=result.line_x,
            y=result.line_y,
            pen=pg.mkPen(color=(220, 50, 50), width=2.5),
        )

        # Confidence bands
        if self._show_confidence_bands:
            band_color = (220, 50, 50, 40)
            self._ci_upper_curve = pg.PlotCurveItem(
                x=result.ci_band_x, y=result.ci_band_upper,
                pen=pg.mkPen(color=(220, 50, 50, 80), width=1, style=Qt.DashLine),
            )
            self._ci_lower_curve = pg.PlotCurveItem(
                x=result.ci_band_x, y=result.ci_band_lower,
                pen=pg.mkPen(color=(220, 50, 50, 80), width=1, style=Qt.DashLine),
            )
            self._ci_fill = pg.FillBetweenItem(
                self._ci_upper_curve, self._ci_lower_curve,
                brush=pg.mkBrush(*band_color),
            )
            self.plot_item.addItem(self._ci_upper_curve)
            self.plot_item.addItem(self._ci_lower_curve)
            self.plot_item.addItem(self._ci_fill)

        # Equation text overlay
        if self._show_equation:
            sign = "+" if result.alpha >= 0 else "-"
            alpha_abs = abs(result.alpha)

            # Format numbers appropriately based on magnitude
            if result.data_mode == "price_levels":
                eq_text = f"Y = {result.alpha:.2f} + {result.beta:.4f}X"
                r2_text = f"R\u00b2 = {result.r_squared:.4f}"
            else:
                eq_text = f"Y = {result.alpha:.6f} {sign} {result.beta:.4f}X"
                if sign == "-":
                    eq_text = f"Y = -{alpha_abs:.6f} + {result.beta:.4f}X"
                r2_text = f"R\u00b2 = {result.r_squared:.4f}"

            full_text = f"{eq_text}  ({r2_text})"
            self._equation_text = pg.TextItem(
                text=full_text,
                color=text_color,
                anchor=(0, 1),
            )
            font = QFont()
            font.setPointSize(11)
            self._equation_text.setFont(font)
            self.plot_item.addItem(self._equation_text)

        # Set view range
        x_min = float(result.x_values.min())
        x_max = float(result.x_values.max())
        y_min = float(result.y_values.min())
        y_max = float(result.y_values.max())

        if self._show_confidence_bands:
            y_min = min(y_min, float(result.ci_band_lower.min()))
            y_max = max(y_max, float(result.ci_band_upper.max()))

        x_pad = (x_max - x_min) * 0.05
        y_pad = (y_max - y_min) * 0.08

        self.view_box.setRange(
            xRange=(x_min - x_pad, x_max + x_pad),
            yRange=(y_min - y_pad, y_max + y_pad),
            padding=0,
        )

        # Position equation text at bottom-left of view
        if self._equation_text is not None:
            self._equation_text.setPos(x_min - x_pad * 0.5, y_min - y_pad * 0.5)

        self.plot_item.showGrid(x=self._show_gridlines, y=self._show_gridlines)

    def show_placeholder(self, message: str = "Enter two tickers and click 'Run'"):
        """Show a placeholder message."""
        self._clear_items()
        self.view_box.setRange(xRange=(0, 1), yRange=(0, 1), padding=0)
        self._placeholder = pg.TextItem(
            text=message,
            color=self._get_label_text_color(),
            anchor=(0.5, 0.5),
        )
        font = QFont()
        font.setPointSize(14)
        self._placeholder.setFont(font)
        self._placeholder.setPos(0.5, 0.5)
        self.plot_item.addItem(self._placeholder)

    def _clear_items(self):
        """Clear all plotted items."""
        if self._scatter is not None:
            self.plot_item.removeItem(self._scatter)
            self._scatter = None

        if self._reg_line is not None:
            self.plot_item.removeItem(self._reg_line)
            self._reg_line = None

        if self._ci_fill is not None:
            self.plot_item.removeItem(self._ci_fill)
            self._ci_fill = None

        if self._ci_upper_curve is not None:
            self.plot_item.removeItem(self._ci_upper_curve)
            self._ci_upper_curve = None

        if self._ci_lower_curve is not None:
            self.plot_item.removeItem(self._ci_lower_curve)
            self._ci_lower_curve = None

        if self._equation_text is not None:
            self.plot_item.removeItem(self._equation_text)
            self._equation_text = None

        if self._placeholder is not None:
            self.plot_item.removeItem(self._placeholder)
            self._placeholder = None

    def _get_accent_color(self) -> tuple:
        """Get accent color RGB for current theme."""
        if self._theme == "dark":
            return (0, 212, 255)
        elif self._theme == "light":
            return (0, 102, 204)
        else:  # bloomberg
            return (255, 128, 0)
