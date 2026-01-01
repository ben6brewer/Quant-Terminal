"""Distribution Chart Widget - Histogram visualization with statistics panel."""

from typing import Dict, Optional

import numpy as np
import pandas as pd
import pyqtgraph as pg
from scipy import stats as scipy_stats
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QGridLayout,
)
from PySide6.QtCore import Qt

from app.core.theme_manager import ThemeManager


class StatisticsPanel(QWidget):
    """Panel displaying return distribution statistics."""

    # Metric display names for labels
    METRIC_LABELS = {
        "Returns": "Return",
        "Volatility": "Volatility",
        "Rolling Volatility": "Volatility",
        "Drawdown": "Drawdown",
        "Rolling Return": "Return",
        "Time Under Water": "Days",
    }

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._current_metric = "Returns"
        self._setup_ui()
        self._apply_theme()
        self.theme_manager.theme_changed.connect(self._apply_theme)

    def _setup_ui(self):
        """Setup the statistics panel UI."""
        layout = QGridLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)
        layout.setHorizontalSpacing(8)
        layout.setVerticalSpacing(8)

        # Row 1: Mean, Std Dev, Skew, Kurtosis
        self.mean_label = self._create_stat_label("Mean:")
        self.mean_value = self._create_value_label("--")
        layout.addWidget(self.mean_label, 0, 0)
        layout.addWidget(self.mean_value, 0, 1)

        self.std_label = self._create_stat_label("Std Dev:")
        self.std_value = self._create_value_label("--")
        layout.addWidget(self.std_label, 0, 2)
        layout.addWidget(self.std_value, 0, 3)

        self.skew_label = self._create_stat_label("Skew:")
        self.skew_value = self._create_value_label("--")
        layout.addWidget(self.skew_label, 0, 4)
        layout.addWidget(self.skew_value, 0, 5)

        self.kurtosis_label = self._create_stat_label("Kurtosis:")
        self.kurtosis_value = self._create_value_label("--")
        layout.addWidget(self.kurtosis_label, 0, 6)
        layout.addWidget(self.kurtosis_value, 0, 7)

        # Row 2: Min, Max, Count, Cash Drag
        self.min_label = self._create_stat_label("Min:")
        self.min_value = self._create_value_label("--")
        layout.addWidget(self.min_label, 1, 0)
        layout.addWidget(self.min_value, 1, 1)

        self.max_label = self._create_stat_label("Max:")
        self.max_value = self._create_value_label("--")
        layout.addWidget(self.max_label, 1, 2)
        layout.addWidget(self.max_value, 1, 3)

        self.count_label = self._create_stat_label("Count:")
        self.count_value = self._create_value_label("--")
        layout.addWidget(self.count_label, 1, 4)
        layout.addWidget(self.count_value, 1, 5)

        self.cash_drag_label = self._create_stat_label("Cash Drag:")
        self.cash_drag_value = self._create_value_label("--")
        layout.addWidget(self.cash_drag_label, 1, 6)
        layout.addWidget(self.cash_drag_value, 1, 7)

        # Set fixed widths for label columns to ensure alignment
        layout.setColumnMinimumWidth(0, 70)  # Mean/Min labels
        layout.setColumnMinimumWidth(2, 70)  # Std Dev/Max labels
        layout.setColumnMinimumWidth(4, 70)  # Skew/Count labels
        layout.setColumnMinimumWidth(6, 80)  # Kurtosis/Cash Drag labels

        # Set fixed widths for value columns
        layout.setColumnMinimumWidth(1, 80)
        layout.setColumnMinimumWidth(3, 80)
        layout.setColumnMinimumWidth(5, 80)
        layout.setColumnMinimumWidth(7, 80)

        # Add stretch to fill remaining space
        layout.setColumnStretch(8, 1)

    def _create_stat_label(self, text: str) -> QLabel:
        """Create a statistic name label."""
        label = QLabel(text)
        label.setObjectName("statLabel")
        label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        return label

    def _create_value_label(self, text: str) -> QLabel:
        """Create a statistic value label."""
        label = QLabel(text)
        label.setObjectName("statValue")
        label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        return label

    def set_metric(self, metric: str):
        """
        Set the current metric and update labels accordingly.

        Args:
            metric: The metric name (e.g., "Returns", "Volatility", "Time Under Water")
        """
        self._current_metric = metric
        metric_label = self.METRIC_LABELS.get(metric, "Value")

        # Update row 1 labels
        self.mean_label.setText(f"Mean {metric_label}:")
        self.std_label.setText("Std Dev:")
        # Skew and Kurtosis stay the same

        # Update row 2 labels
        self.min_label.setText(f"Min {metric_label}:")
        self.max_label.setText(f"Max {metric_label}:")
        # Count and Cash Drag stay the same

    def update_statistics(
        self,
        stats: Dict[str, float],
        cash_drag: Optional[Dict[str, float]] = None,
        show_cash_drag: bool = True,
    ):
        """
        Update the statistics display.

        Args:
            stats: Dictionary with mean, std, skew, kurtosis, min, max, count,
                   jb_stat, jb_pvalue
            cash_drag: Dictionary with avg_cash_weight, cash_drag_bps, period_days
            show_cash_drag: Whether to show cash drag (hidden when cash excluded)
        """
        is_time_under_water = self._current_metric == "Time Under Water"

        # Format functions based on metric type
        def fmt_value(val, decimals=2):
            if val is None or np.isnan(val):
                return "N/A"
            if is_time_under_water:
                # Time Under Water is in days (count)
                return f"{val:.0f} days"
            else:
                # All other metrics are percentages
                return f"{val * 100:.{decimals}f}%"

        def fmt_num(val, decimals=2):
            if val is None or np.isnan(val):
                return "N/A"
            return f"{val:.{decimals}f}"

        # Update value labels
        self.mean_value.setText(fmt_value(stats.get("mean")))
        self.std_value.setText(fmt_value(stats.get("std")))
        self.skew_value.setText(fmt_num(stats.get("skew")))
        self.kurtosis_value.setText(fmt_num(stats.get("kurtosis")))
        self.min_value.setText(fmt_value(stats.get("min")))
        self.max_value.setText(fmt_value(stats.get("max")))
        self.count_value.setText(str(stats.get("count", 0)))

        # Update cash drag - only show for Returns metric
        if self._current_metric == "Returns" and show_cash_drag and cash_drag:
            drag_bps = cash_drag.get("cash_drag_bps", 0)
            self.cash_drag_value.setText(f"{drag_bps:.1f} bps")
            self.cash_drag_label.setVisible(True)
            self.cash_drag_value.setVisible(True)
        elif self._current_metric == "Returns":
            self.cash_drag_value.setText("Excluded")
            self.cash_drag_label.setVisible(True)
            self.cash_drag_value.setVisible(True)
        else:
            # Hide cash drag for non-Returns metrics
            self.cash_drag_label.setVisible(False)
            self.cash_drag_value.setVisible(False)

    def clear(self):
        """Clear all statistics."""
        self.mean_value.setText("--")
        self.std_value.setText("--")
        self.skew_value.setText("--")
        self.kurtosis_value.setText("--")
        self.min_value.setText("--")
        self.max_value.setText("--")
        self.count_value.setText("--")
        self.cash_drag_value.setText("--")

    def _apply_theme(self):
        """Apply theme-specific styling."""
        theme = self.theme_manager.current_theme

        if theme == "light":
            bg_color = "#f5f5f5"
            text_color = "#000000"
            label_color = "#555555"
            border_color = "#cccccc"
        elif theme == "bloomberg":
            bg_color = "#0d1420"
            text_color = "#e8e8e8"
            label_color = "#888888"
            border_color = "#1a2332"
        else:  # dark
            bg_color = "#2d2d2d"
            text_color = "#ffffff"
            label_color = "#888888"
            border_color = "#3d3d3d"

        self.setStyleSheet(f"""
            StatisticsPanel {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 4px;
            }}
            QLabel#statLabel {{
                color: {label_color};
                font-size: 12px;
                background-color: transparent;
            }}
            QLabel#statValue {{
                color: {text_color};
                font-size: 13px;
                font-weight: bold;
                background-color: transparent;
            }}
        """)


class DistributionChart(QWidget):
    """
    Histogram visualization of portfolio returns with statistics panel.
    """

    # X-axis labels for each metric
    X_AXIS_LABELS = {
        "Returns": "Return (%)",
        "Volatility": "Annualized Volatility (%)",
        "Rolling Volatility": "Rolling Volatility (%)",
        "Drawdown": "Drawdown (%)",
        "Rolling Return": "Rolling Return (%)",
        "Time Under Water": "Days Under Water",
    }

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager

        # Store current returns for redraws
        self._current_returns: Optional[pd.Series] = None
        self._current_settings: Dict = {}
        self._current_metric: str = "Returns"

        # Overlay items
        self.bar_graph = None
        self.kde_curve = None
        self.normal_curve = None
        self.mean_line = None
        self.median_line = None
        self.cdf_curve = None
        self.legend = None

        self._setup_ui()
        self._apply_theme()

        self.theme_manager.theme_changed.connect(self._apply_theme)

    def _setup_ui(self):
        """Setup the chart UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # Histogram using PyQtGraph
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setLabel("bottom", "Return (%)")
        self.plot_widget.setLabel("left", "Frequency")
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)

        layout.addWidget(self.plot_widget, stretch=1)

        # Placeholder message (shown when no data)
        self.placeholder = QLabel("Select a portfolio to view return distribution")
        self.placeholder.setAlignment(Qt.AlignCenter)
        self.placeholder.setObjectName("placeholder")
        self.placeholder.setVisible(False)
        layout.addWidget(self.placeholder)

        # Statistics panel at bottom
        self.stats_panel = StatisticsPanel(self.theme_manager)
        self.stats_panel.setFixedHeight(80)
        layout.addWidget(self.stats_panel)

    def set_metric(self, metric: str):
        """
        Set the current metric and update axis labels.

        Args:
            metric: The metric name (e.g., "Returns", "Volatility", "Time Under Water")
        """
        self._current_metric = metric
        x_label = self.X_AXIS_LABELS.get(metric, "Value (%)")
        self.plot_widget.setLabel("bottom", x_label)
        self.stats_panel.set_metric(metric)

    def set_returns(
        self,
        returns: pd.Series,
        cash_drag: Optional[Dict[str, float]] = None,
        show_cash_drag: bool = True,
        num_bins: int = 30,
        show_kde_curve: bool = False,
        show_normal_distribution: bool = False,
        show_mean_median_lines: bool = False,
        show_cdf_view: bool = False,
    ):
        """
        Update the histogram with new return data.

        Args:
            returns: Series of portfolio returns (as decimals, e.g., 0.05 = 5%)
            cash_drag: Cash drag statistics
            show_cash_drag: Whether to show cash drag statistic
            num_bins: Number of histogram bins
            show_kde_curve: Whether to show KDE density curve
            show_normal_distribution: Whether to show normal distribution overlay
            show_mean_median_lines: Whether to show mean/median vertical lines
            show_cdf_view: Whether to show CDF instead of histogram
        """
        # Clear existing plot and overlays
        self._clear_overlays()

        # Store for potential redraws
        self._current_returns = returns
        self._current_settings = {
            "show_kde_curve": show_kde_curve,
            "show_normal_distribution": show_normal_distribution,
            "show_mean_median_lines": show_mean_median_lines,
            "show_cdf_view": show_cdf_view,
        }

        if returns is None or returns.empty:
            self.show_placeholder("No return data available")
            self.stats_panel.clear()
            return

        # Hide placeholder
        self.placeholder.setVisible(False)
        self.plot_widget.setVisible(True)

        # Drop NaN values
        returns = returns.dropna()

        if len(returns) < 2:
            self.show_placeholder("Insufficient data for distribution")
            self.stats_panel.clear()
            return

        # Convert to display format based on metric type
        if self._current_metric == "Time Under Water":
            # Time Under Water is already in days, no conversion needed
            values_display = returns.copy()
        else:
            # All other metrics: convert from decimal to percentage
            values_display = returns * 100

        if show_cdf_view:
            # Draw CDF instead of histogram
            self._draw_cdf(values_display)
            self.plot_widget.setLabel("left", "Cumulative Probability")
        else:
            # Draw histogram
            self._draw_histogram(values_display, num_bins)
            self.plot_widget.setLabel("left", "Frequency")

            # Draw overlays on histogram
            if show_kde_curve:
                self._draw_kde_curve(values_display, num_bins)

            if show_normal_distribution:
                self._draw_normal_distribution(values_display, num_bins)

        # Mean/median lines apply to both views
        if show_mean_median_lines:
            self._draw_mean_median_lines(values_display)

        # Add legend if any overlays are enabled
        self._update_legend(
            values_display,
            show_kde_curve=show_kde_curve,
            show_normal_distribution=show_normal_distribution,
            show_mean_median_lines=show_mean_median_lines,
            show_cdf_view=show_cdf_view,
        )

        # Auto-range
        self.plot_widget.autoRange()

        # Calculate and display statistics
        stats = self._calculate_statistics(returns)
        self.stats_panel.update_statistics(stats, cash_drag, show_cash_drag)

    def _clear_overlays(self):
        """Clear all overlay items."""
        # Remove legend from ViewBox before clearing (it's parented to vb, not PlotItem)
        if self.legend is not None:
            self.legend.scene().removeItem(self.legend)
            self.legend = None

        self.plot_widget.clear()
        self.bar_graph = None
        self.kde_curve = None
        self.normal_curve = None
        self.mean_line = None
        self.median_line = None
        self.cdf_curve = None

    def _draw_histogram(self, returns_pct: pd.Series, num_bins: int):
        """Draw histogram bars."""
        counts, bin_edges = np.histogram(returns_pct, bins=num_bins)
        bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
        bin_width = bin_edges[1] - bin_edges[0]

        self.bar_graph = pg.BarGraphItem(
            x=bin_centers,
            height=counts,
            width=bin_width * 0.9,
            brush=self._get_bar_color(),
            pen=self._get_bar_pen(),
        )
        self.plot_widget.addItem(self.bar_graph)

    def _draw_kde_curve(self, returns_pct: pd.Series, num_bins: int):
        """Draw KDE (Kernel Density Estimation) curve overlay."""
        if len(returns_pct) < 3:
            return

        try:
            # Calculate KDE
            kde = scipy_stats.gaussian_kde(returns_pct.values)

            # Generate x values for smooth curve
            x_min, x_max = returns_pct.min(), returns_pct.max()
            x_range = x_max - x_min
            x = np.linspace(x_min - x_range * 0.1, x_max + x_range * 0.1, 200)
            y = kde(x)

            # Scale KDE to match histogram height
            counts, bin_edges = np.histogram(returns_pct, bins=num_bins)
            bin_width = bin_edges[1] - bin_edges[0]
            y_scaled = y * len(returns_pct) * bin_width

            # Draw curve
            pen = self._get_kde_pen()
            self.kde_curve = self.plot_widget.plot(x, y_scaled, pen=pen)

        except Exception as e:
            print(f"Error drawing KDE curve: {e}")

    def _draw_normal_distribution(self, returns_pct: pd.Series, num_bins: int):
        """Draw normal distribution overlay (dashed line)."""
        if len(returns_pct) < 3:
            return

        try:
            mean = returns_pct.mean()
            std = returns_pct.std()

            # Generate x values
            x_min, x_max = returns_pct.min(), returns_pct.max()
            x_range = x_max - x_min
            x = np.linspace(x_min - x_range * 0.1, x_max + x_range * 0.1, 200)

            # Calculate normal PDF
            y = scipy_stats.norm.pdf(x, mean, std)

            # Scale to match histogram height
            counts, bin_edges = np.histogram(returns_pct, bins=num_bins)
            bin_width = bin_edges[1] - bin_edges[0]
            y_scaled = y * len(returns_pct) * bin_width

            # Draw dashed curve
            pen = self._get_normal_pen()
            self.normal_curve = self.plot_widget.plot(x, y_scaled, pen=pen)

        except Exception as e:
            print(f"Error drawing normal distribution: {e}")

    def _draw_mean_median_lines(self, returns_pct: pd.Series):
        """Draw vertical lines for mean and median."""
        mean_val = returns_pct.mean()
        median_val = returns_pct.median()

        # Mean line (solid green)
        mean_pen = self._get_mean_pen()
        self.mean_line = pg.InfiniteLine(pos=mean_val, angle=90, pen=mean_pen)
        self.plot_widget.addItem(self.mean_line)

        # Median line (solid purple)
        median_pen = self._get_median_pen()
        self.median_line = pg.InfiniteLine(pos=median_val, angle=90, pen=median_pen)
        self.plot_widget.addItem(self.median_line)

    def _draw_cdf(self, returns_pct: pd.Series):
        """Draw cumulative distribution function."""
        # Sort values for CDF
        sorted_returns = np.sort(returns_pct.values)
        cdf_y = np.arange(1, len(sorted_returns) + 1) / len(sorted_returns)

        # Draw CDF curve
        pen = self._get_cdf_pen()
        self.cdf_curve = self.plot_widget.plot(sorted_returns, cdf_y, pen=pen)

    def _update_legend(
        self,
        values_display: pd.Series,
        show_kde_curve: bool,
        show_normal_distribution: bool,
        show_mean_median_lines: bool,
        show_cdf_view: bool,
    ):
        """Add legend to top-left of plot if any overlays are enabled."""
        # Check if any overlay is enabled
        if not any([show_kde_curve, show_normal_distribution, show_mean_median_lines, show_cdf_view]):
            return

        # Create legend anchored to top-left inside the plot area
        self.legend = pg.LegendItem(offset=(10, 1), labelTextSize="11pt")
        self.legend.setParentItem(self.plot_widget.getPlotItem().vb)

        # Add items based on what's enabled
        if show_cdf_view:
            # CDF view
            cdf_pen = self._get_cdf_pen()
            self.legend.addItem(
                pg.PlotDataItem(pen=cdf_pen),
                "CDF"
            )
        else:
            # Histogram mode overlays
            if show_kde_curve and self.kde_curve:
                kde_pen = self._get_kde_pen()
                self.legend.addItem(
                    pg.PlotDataItem(pen=kde_pen),
                    "KDE Curve"
                )

            if show_normal_distribution and self.normal_curve:
                normal_pen = self._get_normal_pen()
                self.legend.addItem(
                    pg.PlotDataItem(pen=normal_pen),
                    "Normal Dist."
                )

        # Mean/median lines apply to both views
        if show_mean_median_lines:
            mean_val = values_display.mean()
            median_val = values_display.median()

            # Format based on metric type
            if self._current_metric == "Time Under Water":
                mean_label = f"Mean ({mean_val:.0f} days)"
                median_label = f"Median ({median_val:.0f} days)"
            else:
                mean_label = f"Mean ({mean_val:.2f}%)"
                median_label = f"Median ({median_val:.2f}%)"

            mean_pen = self._get_mean_pen()
            self.legend.addItem(
                pg.PlotDataItem(pen=mean_pen),
                mean_label
            )

            median_pen = self._get_median_pen()
            self.legend.addItem(
                pg.PlotDataItem(pen=median_pen),
                median_label
            )

    def _calculate_statistics(self, returns: pd.Series) -> Dict[str, float]:
        """Calculate distribution statistics."""
        return {
            "mean": returns.mean(),
            "std": returns.std(ddof=1),
            "skew": returns.skew(),
            "kurtosis": returns.kurtosis(),
            "min": returns.min(),
            "max": returns.max(),
            "count": len(returns),
        }

    def show_placeholder(self, message: str):
        """Show placeholder message."""
        self._clear_overlays()
        self.placeholder.setText(message)
        self.placeholder.setVisible(True)

    def clear(self):
        """Clear the chart and statistics."""
        self._clear_overlays()
        self._current_returns = None
        self._current_settings = {}
        self.stats_panel.clear()
        self.show_placeholder("Select a portfolio to view return distribution")

    def _get_bar_color(self):
        """Get bar color based on theme."""
        theme = self.theme_manager.current_theme
        if theme == "light":
            return pg.mkBrush(0, 102, 204, 180)  # Blue
        elif theme == "bloomberg":
            return pg.mkBrush(255, 128, 0, 180)  # Orange
        else:
            return pg.mkBrush(0, 212, 255, 180)  # Cyan

    def _get_bar_pen(self):
        """Get bar border pen based on theme."""
        theme = self.theme_manager.current_theme
        if theme == "light":
            return pg.mkPen(0, 80, 160, 255, width=1)
        elif theme == "bloomberg":
            return pg.mkPen(200, 100, 0, 255, width=1)
        else:
            return pg.mkPen(0, 170, 200, 255, width=1)

    def _get_kde_pen(self):
        """Get pen for KDE curve (solid, contrasting color)."""
        theme = self.theme_manager.current_theme
        if theme == "light":
            return pg.mkPen(220, 50, 50, 255, width=2)  # Red
        elif theme == "bloomberg":
            return pg.mkPen(0, 200, 255, 255, width=2)  # Cyan
        else:
            return pg.mkPen(255, 100, 100, 255, width=2)  # Light red

    def _get_normal_pen(self):
        """Get pen for normal distribution curve (solid purple)."""
        theme = self.theme_manager.current_theme
        if theme == "light":
            return pg.mkPen(150, 0, 150, 220, width=2)
        elif theme == "bloomberg":
            return pg.mkPen(200, 100, 255, 220, width=2)
        else:
            return pg.mkPen(180, 100, 255, 220, width=2)

    def _get_mean_pen(self):
        """Get pen for mean vertical line (solid red)."""
        theme = self.theme_manager.current_theme
        if theme == "light":
            return pg.mkPen(200, 50, 50, 255, width=2)
        elif theme == "bloomberg":
            return pg.mkPen(255, 80, 80, 255, width=2)
        else:
            return pg.mkPen(255, 100, 100, 255, width=2)

    def _get_median_pen(self):
        """Get pen for median vertical line (solid green)."""
        theme = self.theme_manager.current_theme
        if theme == "light":
            return pg.mkPen(0, 150, 0, 255, width=2)
        elif theme == "bloomberg":
            return pg.mkPen(0, 200, 100, 255, width=2)
        else:
            return pg.mkPen(0, 200, 0, 255, width=2)

    def _get_cdf_pen(self):
        """Get pen for CDF curve."""
        theme = self.theme_manager.current_theme
        if theme == "light":
            return pg.mkPen(0, 102, 204, 255, width=2)  # Blue
        elif theme == "bloomberg":
            return pg.mkPen(255, 128, 0, 255, width=2)  # Orange
        else:
            return pg.mkPen(0, 212, 255, 255, width=2)  # Cyan

    def _apply_theme(self):
        """Apply theme-specific styling."""
        theme = self.theme_manager.current_theme

        if theme == "light":
            bg_color = "#ffffff"
            text_color = "#000000"
            grid_color = "#cccccc"
            placeholder_color = "#666666"
        elif theme == "bloomberg":
            bg_color = "#000814"
            text_color = "#e8e8e8"
            grid_color = "#1a2332"
            placeholder_color = "#888888"
        else:  # dark
            bg_color = "#1e1e1e"
            text_color = "#ffffff"
            grid_color = "#3d3d3d"
            placeholder_color = "#888888"

        # Update plot widget
        self.plot_widget.setBackground(bg_color)

        # Update axis colors
        axis_pen = pg.mkPen(text_color, width=1)
        self.plot_widget.getAxis("bottom").setPen(axis_pen)
        self.plot_widget.getAxis("bottom").setTextPen(axis_pen)
        self.plot_widget.getAxis("left").setPen(axis_pen)
        self.plot_widget.getAxis("left").setTextPen(axis_pen)

        # Update bar colors if they exist
        if self.bar_graph:
            self.bar_graph.setOpts(
                brush=self._get_bar_color(),
                pen=self._get_bar_pen(),
            )

        # Update placeholder
        self.placeholder.setStyleSheet(f"""
            QLabel#placeholder {{
                color: {placeholder_color};
                font-size: 16px;
                background-color: {bg_color};
            }}
        """)

        # Main widget background
        self.setStyleSheet(f"DistributionChart {{ background-color: {bg_color}; }}")
