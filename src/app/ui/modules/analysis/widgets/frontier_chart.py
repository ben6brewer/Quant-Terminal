"""Frontier Chart Widget - Efficient Frontier scatter plot with optimization overlays."""

from __future__ import annotations

from typing import Dict, Any, List

import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from app.ui.widgets.charting.base_chart import BaseChart


COLORMAPS = {
    "Magma": (
        [0.0, 0.25, 0.5, 0.75, 1.0],
        [(10, 5, 40, 180), (100, 20, 120, 180), (200, 50, 50, 180),
         (250, 160, 30, 180), (255, 255, 100, 200)],
    ),
    "Viridis": (
        [0.0, 0.25, 0.5, 0.75, 1.0],
        [(68, 1, 84, 180), (59, 82, 139, 180), (33, 145, 140, 180),
         (94, 201, 98, 180), (253, 231, 37, 200)],
    ),
    "Plasma": (
        [0.0, 0.25, 0.5, 0.75, 1.0],
        [(13, 8, 135, 180), (126, 3, 168, 180), (204, 71, 120, 180),
         (248, 149, 64, 180), (240, 249, 33, 200)],
    ),
    "Inferno": (
        [0.0, 0.25, 0.5, 0.75, 1.0],
        [(0, 0, 4, 180), (87, 16, 110, 180), (188, 55, 84, 180),
         (249, 142, 9, 180), (252, 255, 164, 200)],
    ),
    "Cool-Warm": (
        [0.0, 0.25, 0.5, 0.75, 1.0],
        [(59, 76, 192, 180), (141, 176, 254, 180), (221, 221, 221, 180),
         (245, 160, 105, 180), (180, 4, 38, 200)],
    ),
}


class PercentAxisItem(pg.AxisItem):
    """Axis that displays values as percentages."""

    def tickStrings(self, values, scale, spacing):
        return [f"{v * 100:.1f}%" if v is not None else "" for v in values]


class FrontierChart(BaseChart):
    """Efficient frontier chart with Monte Carlo scatter, frontier curve, and special portfolios."""

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # Create plot with percentage axes
        self.plot_item = self.addPlot(
            axisItems={
                "bottom": PercentAxisItem(orientation="bottom"),
                "left": PercentAxisItem(orientation="left"),
            }
        )
        self.view_box = self.plot_item.getViewBox()
        self.view_box.setMenuEnabled(False)
        self.view_box.setMouseEnabled(x=False, y=False)
        self.view_box.disableAutoRange()
        self.view_box.setRange(xRange=(0, 1), yRange=(0, 1), padding=0)

        # Fully lock the view — reject all mouse interaction
        self.view_box.wheelEvent = lambda ev: ev.ignore()
        self.view_box.mouseDragEvent = lambda ev, axis=None: ev.ignore()
        self.view_box.mouseClickEvent = lambda ev: ev.ignore()

        # Disable SI prefix (removes "x0.001" from axis labels)
        self.plot_item.getAxis("bottom").enableAutoSIPrefix(False)
        self.plot_item.getAxis("left").enableAutoSIPrefix(False)

        # Style axis labels
        axis_label_style = {"font-size": "14px", "font-weight": "bold"}
        self.plot_item.setLabel("bottom", "Volatility", **axis_label_style)
        self.plot_item.setLabel("left", "CAGR", **axis_label_style)
        self.plot_item.getAxis("bottom").setHeight(60)
        self.plot_item.getAxis("bottom").setStyle(tickTextOffset=12)
        self.plot_item.getAxis("left").setWidth(100)
        self.plot_item.getAxis("left").setStyle(tickTextOffset=12)

        # Settings
        self._show_gridlines = True
        self._colorscale = "Magma"
        self._show_individuals = True
        self._show_frontier = True
        self._show_cml = True
        self._show_max_sharpe = True
        self._show_min_vol = True
        self._show_max_sortino = True

        # Items tracked for clearing
        self._scatter = None
        self._frontier_line = None
        self._cml_line = None
        self._asset_labels: List[pg.TextItem] = []
        self._marker_items: list = []
        self._legend = None

        # Placeholder
        self._placeholder = None

        self.set_theme("dark")

    def apply_settings(self, settings: dict) -> None:
        """Apply EF display settings."""
        self._show_gridlines = settings.get("ef_show_gridlines", True)
        self._colorscale = settings.get("ef_colorscale", "Magma")
        self._show_individuals = settings.get("ef_show_individual_securities", True)
        self._show_frontier = settings.get("ef_show_frontier", True)
        self._show_cml = settings.get("ef_show_cml", True)
        self._show_max_sharpe = settings.get("ef_show_max_sharpe", True)
        self._show_min_vol = settings.get("ef_show_min_vol", True)
        self._show_max_sortino = settings.get("ef_show_max_sortino", True)

    def set_theme(self, theme: str) -> None:
        """Apply theme, then fix axis text color overridden by BaseChart._apply_gridlines."""
        super().set_theme(theme)
        text_color = self._get_label_text_color()
        text_pen = pg.mkPen(color=text_color)
        for axis_name in ("bottom", "left"):
            self.plot_item.getAxis(axis_name).setTextPen(text_pen)
        self.plot_item.showGrid(x=self._show_gridlines, y=self._show_gridlines)

    def plot_results(self, results: Dict[str, Any]):
        """Plot the full efficient frontier visualization.

        Args:
            results: Dict from FrontierCalculationService.calculate_efficient_frontier()
        """
        import numpy as np

        self._clear_items()

        # Monte Carlo scatter colored by Sharpe ratio
        sim_vols = np.array(results["sim_vols"])
        sim_rets = np.array(results["sim_rets"])
        sim_sharpes = np.array(results["sim_sharpes"])

        # Normalize Sharpe ratios for colormap
        s_min, s_max = sim_sharpes.min(), sim_sharpes.max()
        s_range = s_max - s_min if s_max != s_min else 1.0
        s_norm = (sim_sharpes - s_min) / s_range

        # Build colormap from settings
        positions, color_stops = COLORMAPS.get(self._colorscale, COLORMAPS["Magma"])
        cmap = pg.ColorMap(positions, color_stops)
        colors = cmap.map(s_norm, mode="byte")

        brushes = [pg.mkBrush(*c) for c in colors]
        self._scatter = pg.ScatterPlotItem(
            x=sim_vols,
            y=sim_rets,
            brush=brushes,
            pen=pg.mkPen(None),
            size=4,
        )
        self.plot_item.addItem(self._scatter)

        # Efficient frontier curve
        if self._show_frontier and results["frontier_vols"]:
            frontier_pen = pg.mkPen(color=(0, 255, 100), width=2.5)
            self._frontier_line = self.plot_item.plot(
                x=results["frontier_vols"],
                y=results["frontier_rets"],
                pen=frontier_pen,
            )

        # Capital Market Line
        rf = results["risk_free_rate"]
        tangency_vol = results["tangency_vol"]
        tangency_ret = results["tangency_ret"]

        if self._show_cml:
            if results["frontier_vols"]:
                max_vol = max(results["frontier_vols"]) * 1.3
            else:
                max_vol = max(sim_vols) * 1.2
            cml_x = np.linspace(0, max_vol, 100)
            sharpe = (tangency_ret - rf) / tangency_vol if tangency_vol > 1e-10 else 0
            cml_y = rf + sharpe * cml_x

            cml_pen = pg.mkPen(color=(180, 180, 180), width=1.5, style=Qt.DashLine)
            self._cml_line = self.plot_item.plot(x=cml_x, y=cml_y, pen=cml_pen)

        # Special portfolio markers
        label_font = QFont()
        label_font.setPointSize(10)
        text_color = self._get_label_text_color()

        tangency_scatter = None
        if self._show_max_sharpe:
            tangency_scatter = pg.ScatterPlotItem(
                x=[tangency_vol],
                y=[tangency_ret],
                symbol="star",
                size=18,
                brush=pg.mkBrush(255, 165, 0),
                pen=pg.mkPen("w", width=1),
            )
            self.plot_item.addItem(tangency_scatter)
            self._marker_items.append(tangency_scatter)

        min_vol_scatter = None
        if self._show_min_vol:
            min_vol_scatter = pg.ScatterPlotItem(
                x=[results["min_vol_vol"]],
                y=[results["min_vol_ret"]],
                symbol="d",
                size=14,
                brush=pg.mkBrush(0, 212, 255),
                pen=pg.mkPen("w", width=1),
            )
            self.plot_item.addItem(min_vol_scatter)
            self._marker_items.append(min_vol_scatter)

        sortino_scatter = None
        if self._show_max_sortino:
            sortino_scatter = pg.ScatterPlotItem(
                x=[results["sortino_vol"]],
                y=[results["sortino_ret"]],
                symbol="t",
                size=14,
                brush=pg.mkBrush(255, 0, 255),
                pen=pg.mkPen("w", width=1),
            )
            self.plot_item.addItem(sortino_scatter)
            self._marker_items.append(sortino_scatter)

        # Legend
        self._legend = self.plot_item.addLegend(
            offset=(10, 10), labelTextColor=text_color,
        )
        if self._show_frontier:
            self._legend.addItem(
                pg.PlotDataItem(pen=pg.mkPen(color=(0, 255, 100), width=2.5)),
                "Efficient Frontier",
            )
        if self._show_cml:
            self._legend.addItem(
                pg.PlotDataItem(pen=pg.mkPen(color=(180, 180, 180), width=1.5, style=Qt.DashLine)),
                f"Capital Market Line (Rf={rf * 100:.2f}%)",
            )
        if tangency_scatter is not None:
            self._legend.addItem(tangency_scatter, f"Max Sharpe ({results['sharpe_ratio']:.2f})")
        if min_vol_scatter is not None:
            self._legend.addItem(min_vol_scatter, f"Min Volatility ({results['min_vol_vol'] * 100:.1f}%)")
        if sortino_scatter is not None:
            self._legend.addItem(sortino_scatter, f"Max Sortino ({results['sortino_ratio']:.2f})")

        # Individual asset labels
        tickers = results["tickers"]
        individual_vols = results["individual_vols"]
        individual_rets = results["individual_rets"]

        if self._show_individuals:
            asset_scatter = pg.ScatterPlotItem(
                x=individual_vols,
                y=individual_rets,
                symbol="o",
                size=8,
                brush=pg.mkBrush(*text_color, 200),
                pen=pg.mkPen(None),
            )
            self.plot_item.addItem(asset_scatter)
            self._marker_items.append(asset_scatter)

            for i, ticker in enumerate(tickers):
                label = pg.TextItem(
                    text=ticker,
                    color=text_color,
                    anchor=(0.5, 1.2),
                )
                label.setFont(label_font)
                label.setPos(individual_vols[i], individual_rets[i])
                self.plot_item.addItem(label)
                self._asset_labels.append(label)

        # Set ranges — left-align chart to y-axis (x starts at 0)
        all_vols = list(sim_vols) + individual_vols + [tangency_vol, results["min_vol_vol"], results["sortino_vol"]]
        all_rets = list(sim_rets) + individual_rets + [tangency_ret, results["min_vol_ret"], results["sortino_ret"]]
        max_x = max(all_vols) if all_vols else 0.5
        min_y = min(all_rets) if all_rets else -0.1
        max_y = max(all_rets) if all_rets else 0.3
        y_pad = (max_y - min_y) * 0.08
        self.view_box.setRange(
            xRange=(0, max_x * 1.1),
            yRange=(min_y - y_pad, max_y + y_pad),
            padding=0,
        )

    def show_placeholder(self, message: str = "Click 'Run' to generate efficient frontier"):
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

        if self._frontier_line is not None:
            self.plot_item.removeItem(self._frontier_line)
            self._frontier_line = None

        if self._cml_line is not None:
            self.plot_item.removeItem(self._cml_line)
            self._cml_line = None

        for item in self._asset_labels:
            self.plot_item.removeItem(item)
        self._asset_labels.clear()

        for item in self._marker_items:
            self.plot_item.removeItem(item)
        self._marker_items.clear()

        if self._legend is not None:
            self.plot_item.legend.clear()
            self.plot_item.removeItem(self._legend)
            self.plot_item.legend = None
            self._legend = None

        if self._placeholder is not None:
            self.plot_item.removeItem(self._placeholder)
            self._placeholder = None
