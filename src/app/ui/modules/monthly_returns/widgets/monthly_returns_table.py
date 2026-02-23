"""Monthly Returns Table Widget - Year×Month heatmap with configurable colors."""

from __future__ import annotations

from typing import Dict, Tuple, TYPE_CHECKING

from PySide6.QtWidgets import (
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common.lazy_theme_mixin import LazyThemeMixin

if TYPE_CHECKING:
    import pandas as pd

MONTH_COLUMNS = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "YTD",
]

# Diverging color pairs: neg_rgb (negative returns), pos_rgb (positive returns)
COLORSCALES = {
    "Red-Green": {"neg": (183, 28, 28),   "pos": (27, 94, 32)},
    "Magma":     {"neg": (72, 20, 120),  "pos": (195, 100, 10)},
    "Viridis":   {"neg": (68, 1, 84),    "pos": (53, 140, 50)},
    "Plasma":    {"neg": (100, 5, 150),   "pos": (210, 120, 30)},
    "Inferno":   {"neg": (100, 10, 50),   "pos": (200, 130, 10)},
    "Cool-Warm": {"neg": (50, 70, 175),   "pos": (185, 30, 30)},
}


class MonthlyReturnsTable(LazyThemeMixin, QTableWidget):
    """Heatmap table showing monthly returns by year with configurable coloring."""

    THEME_COLORS = {
        "dark": {
            "base_bg": (30, 30, 30),
            "header_bg": "#2d2d2d",
            "header_text": "#cccccc",
            "year_text": "#ffffff",
            "grid": "#3d3d3d",
            "bg": "#1e1e1e",
        },
        "light": {
            "base_bg": (255, 255, 255),
            "header_bg": "#e8e8e8",
            "header_text": "#333333",
            "year_text": "#000000",
            "grid": "#cccccc",
            "bg": "#ffffff",
        },
        "bloomberg": {
            "base_bg": (0, 8, 20),
            "header_bg": "#0d1420",
            "header_text": "#b0b0b0",
            "year_text": "#e8e8e8",
            "grid": "#1a2838",
            "bg": "#000814",
        },
    }

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._theme_dirty = False
        self._grid_data: "pd.DataFrame | None" = None

        # Display settings (defaults)
        self._colorscale = "Magma"
        self._use_gradient = True
        self._decimals = 2
        self._show_ytd = True

        self._setup_table()
        self._apply_theme()
        self.theme_manager.theme_changed.connect(self._on_theme_changed_lazy)

    def showEvent(self, event):
        super().showEvent(event)
        self._check_theme_dirty()

    def _setup_table(self):
        self.setAlternatingRowColors(False)
        self.setShowGrid(True)
        self.setSelectionMode(QAbstractItemView.NoSelection)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)

        self.horizontalHeader().setVisible(True)
        self.verticalHeader().setVisible(False)

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    def update_grid(
        self,
        grid: "pd.DataFrame",
        colorscale: str = None,
        use_gradient: bool = None,
        decimals: int = None,
        show_ytd: bool = None,
    ):
        """Populate the table from a year×month grid DataFrame.

        Optional keyword args override stored display settings.
        """
        import numpy as np

        if colorscale is not None:
            self._colorscale = colorscale
        if use_gradient is not None:
            self._use_gradient = use_gradient
        if decimals is not None:
            self._decimals = decimals
        if show_ytd is not None:
            self._show_ytd = show_ytd

        self._grid_data = grid
        if grid.empty:
            return

        # Determine which columns to display
        display_cols = MONTH_COLUMNS if self._show_ytd else MONTH_COLUMNS[:-1]

        num_rows = len(grid)
        num_cols = len(display_cols) + 1  # +1 for year column
        self.setRowCount(num_rows)
        self.setColumnCount(num_cols)

        headers = ["Year"] + display_cols
        self.setHorizontalHeaderLabels(headers)
        self.horizontalHeader().setVisible(True)

        # Stretch columns to fill available width
        self.setMinimumWidth(0)
        self.setMaximumWidth(16777215)  # Reset any previous fixed width
        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        for i in range(1, num_cols):
            header.setSectionResizeMode(i, QHeaderView.Stretch)

        # Collect all values for normalization
        all_values = []
        for year in grid.index:
            for col_name in display_cols:
                val = grid.loc[year, col_name]
                if not (isinstance(val, float) and np.isnan(val)):
                    all_values.append(val)

        cap = min(max(abs(v) for v in all_values), 0.50) if all_values else 0.50

        theme = self.theme_manager.current_theme
        colors = self.THEME_COLORS.get(theme, self.THEME_COLORS["dark"])
        scale = COLORSCALES.get(self._colorscale, COLORSCALES["Magma"])
        fmt = f".{self._decimals}f"

        for row_idx, year in enumerate(grid.index):
            # Year column
            year_item = QTableWidgetItem(str(year))
            year_item.setFlags(Qt.ItemIsEnabled)
            year_item.setTextAlignment(Qt.AlignCenter)
            year_item.setForeground(QBrush(QColor(colors["year_text"])))
            year_item.setBackground(QBrush(QColor(colors["header_bg"])))
            self.setItem(row_idx, 0, year_item)

            for col_idx, col_name in enumerate(display_cols):
                val = grid.loc[year, col_name]
                item = QTableWidgetItem()
                item.setFlags(Qt.ItemIsEnabled)
                item.setTextAlignment(Qt.AlignCenter)

                if isinstance(val, float) and np.isnan(val):
                    item.setText("")
                else:
                    item.setText(f"{val * 100:{fmt}}%")
                    bg_color, text_color = self._cell_color(
                        val, cap, colors, scale
                    )
                    item.setBackground(QBrush(bg_color))
                    item.setForeground(QBrush(text_color))

                self.setItem(row_idx, col_idx + 1, item)

        self._style_headers(colors)

    def _cell_color(
        self, value: float, cap: float, colors: dict, scale: dict
    ) -> Tuple[QColor, QColor]:
        """Compute background and text color for a cell value."""
        if self._use_gradient:
            intensity = min(abs(value) / cap, 1.0) if cap != 0 else 0.0
        else:
            # Binary mode: full intensity for any non-zero value
            intensity = 1.0

        base = colors["base_bg"]
        target = scale["pos"] if value >= 0 else scale["neg"]

        r = int(base[0] + (target[0] - base[0]) * intensity)
        g = int(base[1] + (target[1] - base[1]) * intensity)
        b = int(base[2] + (target[2] - base[2]) * intensity)

        bg = QColor(r, g, b)
        text = QColor("#ffffff") if intensity > 0.5 else QColor(colors["year_text"])
        return bg, text

    def _style_headers(self, colors: dict):
        """Apply theme colors to horizontal header."""
        header = self.horizontalHeader()
        header.setStyleSheet(f"""
            QHeaderView::section {{
                background-color: {colors['header_bg']};
                color: {colors['header_text']};
                font-weight: bold;
                font-size: 13px;
                padding: 4px;
                border: 1px solid {colors['grid']};
            }}
        """)

    def _apply_theme(self):
        """Apply theme stylesheet."""
        theme = self.theme_manager.current_theme
        colors = self.THEME_COLORS.get(theme, self.THEME_COLORS["dark"])

        self.setStyleSheet(f"""
            QTableWidget {{
                background-color: {colors['bg']};
                gridline-color: {colors['grid']};
                border: 1px solid {colors['grid']};
                font-size: 13px;
            }}
            QTableWidget::item {{
                padding: 4px 6px;
            }}
        """)

        # Re-render data with new theme colors if data exists
        if self._grid_data is not None and not self._grid_data.empty:
            self.update_grid(self._grid_data)
