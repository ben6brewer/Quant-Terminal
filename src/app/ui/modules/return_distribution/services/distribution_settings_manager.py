"""Distribution Settings Manager - Manages return distribution settings with persistence."""

from __future__ import annotations

from typing import Dict, Any
from PySide6.QtCore import Qt

from app.services.base_settings_manager import BaseSettingsManager
from app.services.qt_settings_mixin import QtSettingsSerializationMixin


class DistributionSettingsManager(QtSettingsSerializationMixin, BaseSettingsManager):
    """
    Manages return distribution module settings with persistent storage.

    Uses QtSettingsSerializationMixin for Qt.PenStyle and RGB tuple serialization.
    """

    @property
    def DEFAULT_SETTINGS(self) -> Dict[str, Any]:
        """Default distribution settings."""
        return {
            # === Section 1: General ===
            "show_gridlines": False,
            "background_color": None,  # None = use theme default, else (r, g, b) tuple

            # === Section 2: Cash Handling ===
            "exclude_cash": True,  # Default: exclude cash from returns

            # === Section 3: Portfolio Visualization (when no benchmark) ===
            # Histogram bars
            "histogram_color": None,  # None = theme default, else (r, g, b)

            # KDE Curve
            "show_kde_curve": True,
            "kde_color": None,
            "kde_line_style": Qt.SolidLine,
            "kde_line_width": 2,

            # Normal Distribution
            "show_normal_distribution": True,
            "normal_color": None,
            "normal_line_style": Qt.DashLine,
            "normal_line_width": 2,

            # Median Line
            "show_median_line": True,
            "median_color": None,
            "median_line_style": Qt.SolidLine,
            "median_line_width": 2,

            # Mean Line
            "show_mean_line": True,
            "mean_color": None,
            "mean_line_style": Qt.SolidLine,
            "mean_line_width": 2,

            # CDF
            "show_cdf_view": False,

            # === Section 4: Portfolio vs Benchmark Visualization ===
            # Portfolio Histogram
            "benchmark_portfolio_histogram_color": None,

            # Benchmark Histogram
            "benchmark_benchmark_histogram_color": None,

            # Portfolio KDE (when benchmark present)
            "benchmark_show_portfolio_kde": True,
            "benchmark_portfolio_kde_color": None,
            "benchmark_portfolio_kde_line_style": Qt.SolidLine,
            "benchmark_portfolio_kde_line_width": 2,

            # Benchmark KDE
            "benchmark_show_benchmark_kde": True,
            "benchmark_kde_color": None,
            "benchmark_kde_line_style": Qt.SolidLine,
            "benchmark_kde_line_width": 2,

            # Normal Distribution (with benchmark)
            "benchmark_show_normal_distribution": True,
            "benchmark_normal_color": None,
            "benchmark_normal_line_style": Qt.DashLine,
            "benchmark_normal_line_width": 2,

            # Portfolio Median (with benchmark)
            "benchmark_show_portfolio_median": False,
            "benchmark_portfolio_median_color": None,
            "benchmark_portfolio_median_line_style": Qt.SolidLine,
            "benchmark_portfolio_median_line_width": 2,

            # Portfolio Mean (with benchmark)
            "benchmark_show_portfolio_mean": False,
            "benchmark_portfolio_mean_color": None,
            "benchmark_portfolio_mean_line_style": Qt.SolidLine,
            "benchmark_portfolio_mean_line_width": 2,

            # Benchmark Median
            "benchmark_show_benchmark_median": False,
            "benchmark_benchmark_median_color": None,
            "benchmark_benchmark_median_line_style": Qt.DashLine,
            "benchmark_benchmark_median_line_width": 2,

            # Benchmark Mean
            "benchmark_show_benchmark_mean": False,
            "benchmark_benchmark_mean_color": None,
            "benchmark_benchmark_mean_line_style": Qt.DashLine,
            "benchmark_benchmark_mean_line_width": 2,

            # CDF with benchmark
            "benchmark_show_cdf_view": False,
        }

    @property
    def settings_filename(self) -> str:
        """Settings file name."""
        return "distribution_settings.json"

