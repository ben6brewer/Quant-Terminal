"""Asset Class Returns Table - Dual table with scrollable years + frozen CAGR."""

from __future__ import annotations

import math

from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
)
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QColor, QFont, QCursor

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common import LazyThemeMixin

COL_WIDTH = 100
MIN_ROW_HEIGHT = 40
CAGR_COL_WIDTH = 110


class _DragPanFilter(QWidget):
    """Event filter for click-and-drag horizontal panning on a table viewport."""

    def __init__(self, table: QTableWidget, parent=None):
        super().__init__(parent)
        self._table = table
        self._dragging = False
        self._start_x = 0
        self._start_scroll = 0

    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            self._dragging = True
            self._start_x = event.globalPosition().toPoint().x()
            self._start_scroll = self._table.horizontalScrollBar().value()
            self._table.viewport().setCursor(QCursor(Qt.ClosedHandCursor))
            return True
        elif event.type() == QEvent.MouseMove and self._dragging:
            delta = self._start_x - event.globalPosition().toPoint().x()
            self._table.horizontalScrollBar().setValue(self._start_scroll + delta)
            return True
        elif event.type() == QEvent.MouseButtonRelease and self._dragging:
            self._dragging = False
            self._table.viewport().setCursor(QCursor(Qt.ArrowCursor))
            return True
        return False


class AssetClassReturnsTable(LazyThemeMixin, QWidget):
    """Dual-table quilt chart: scrollable year columns + frozen CAGR column."""

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._theme_dirty = False
        self._data = None
        self._decimals = 1
        self._label_mode = "label"
        self._cagr_header = "CAGR"
        self._show_cagr = True
        self._asset_count = 0

        self._setup_ui()
        self._apply_theme()
        self.theme_manager.theme_changed.connect(self._on_theme_changed_lazy)

    def showEvent(self, event):
        super().showEvent(event)
        self._check_theme_dirty()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Left: main scrollable table (scrollbar hidden, drag-to-pan)
        self.main_table = QTableWidget()
        self.main_table.setSelectionMode(QAbstractItemView.NoSelection)
        self.main_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.main_table.setFocusPolicy(Qt.NoFocus)
        self.main_table.setShowGrid(False)
        self.main_table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.main_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.main_table.verticalHeader().setVisible(False)
        self.main_table.horizontalHeader().setMinimumSectionSize(COL_WIDTH)
        self.main_table.horizontalHeader().setDefaultSectionSize(COL_WIDTH)
        layout.addWidget(self.main_table, stretch=1)

        # Install drag-to-pan on main table viewport
        self._drag_filter = _DragPanFilter(self.main_table, self)
        self.main_table.viewport().installEventFilter(self._drag_filter)

        # Right: frozen CAGR column
        self.cagr_table = QTableWidget()
        self.cagr_table.setSelectionMode(QAbstractItemView.NoSelection)
        self.cagr_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.cagr_table.setFocusPolicy(Qt.NoFocus)
        self.cagr_table.setShowGrid(False)
        self.cagr_table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.cagr_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.cagr_table.verticalHeader().setVisible(False)
        self.cagr_table.setFixedWidth(CAGR_COL_WIDTH)
        layout.addWidget(self.cagr_table)

    def update_data(self, data: dict, decimals: int = 1, label_mode: str = "label", cagr_header: str = "CAGR", show_cagr: bool = True):
        """Populate both tables from service result dict."""
        self._data = data
        self._decimals = decimals
        self._label_mode = label_mode
        self._cagr_header = cagr_header
        self._show_cagr = show_cagr

        years = data.get("years", [])
        year_data = data.get("data", {})
        cagr_data = data.get("cagr", [])
        asset_count = data.get("asset_count", 0)
        self._asset_count = asset_count

        if not years or asset_count == 0:
            self.main_table.clear()
            self.cagr_table.clear()
            return

        self._populate_main_table(years, year_data, asset_count, decimals, label_mode)
        self._populate_cagr_table(cagr_data, asset_count, decimals, label_mode)
        self.cagr_table.setVisible(show_cagr)
        self._update_row_heights()

    def _populate_main_table(self, years, year_data, asset_count, decimals, label_mode):
        n_cols = len(years)
        self.main_table.setColumnCount(n_cols)
        self.main_table.setRowCount(asset_count)

        # Headers
        headers = [str(y) for y in years]
        self.main_table.setHorizontalHeaderLabels(headers)
        header = self.main_table.horizontalHeader()
        for col in range(n_cols):
            header.setSectionResizeMode(col, QHeaderView.Fixed)
            self.main_table.setColumnWidth(col, COL_WIDTH)

        # Populate cells
        for col, year in enumerate(years):
            entries = year_data.get(year, [])
            for row, entry in enumerate(entries):
                display_name = entry.get("ticker", entry["label"]) if label_mode == "ticker" else entry["label"]
                self._set_cell(
                    self.main_table, row, col,
                    display_name, entry["return"], entry["color"], decimals,
                )

    def _populate_cagr_table(self, cagr_data, asset_count, decimals, label_mode):
        self.cagr_table.setColumnCount(1)
        self.cagr_table.setRowCount(asset_count)
        self.cagr_table.setHorizontalHeaderLabels([self._cagr_header])

        cagr_header = self.cagr_table.horizontalHeader()
        cagr_header.setSectionResizeMode(0, QHeaderView.Stretch)

        for row, entry in enumerate(cagr_data):
            display_name = entry.get("ticker", entry["label"]) if label_mode == "ticker" else entry["label"]
            self._set_cell(
                self.cagr_table, row, 0,
                display_name, entry["cagr"], entry["color"], decimals,
            )

    def _set_cell(self, table, row, col, label, value, color, decimals):
        """Create a two-line cell: label + return%."""
        if value is not None and not (isinstance(value, float) and math.isnan(value)):
            fmt = f"{{:.{decimals}f}}"
            pct_str = fmt.format(value * 100) + "%"
        else:
            pct_str = "N/A"

        item = QTableWidgetItem(f"{label}\n{pct_str}")
        item.setTextAlignment(Qt.AlignCenter)

        font = QFont()
        font.setPointSize(10)
        font.setBold(True)
        item.setFont(font)

        # White text on asset-class-colored background
        r, g, b = color
        if pct_str == "N/A":
            # Desaturate: blend toward gray
            gray = (r + g + b) // 3
            r = (r + gray) // 2
            g = (g + gray) // 2
            b = (b + gray) // 2
            bg = QColor(r, g, b, 140)
        else:
            bg = QColor(r, g, b)

        item.setBackground(bg)
        item.setForeground(QColor(255, 255, 255))

        table.setItem(row, col, item)

    def _update_row_heights(self):
        """Dynamically scale row heights to fill available vertical space."""
        if self._asset_count == 0:
            return

        header_height = self.main_table.horizontalHeader().height()
        available = self.height() - header_height - 2  # small padding
        row_height = max(MIN_ROW_HEIGHT, available // self._asset_count)

        for row in range(self._asset_count):
            self.main_table.setRowHeight(row, row_height)
            self.cagr_table.setRowHeight(row, row_height)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_row_heights()

    def scroll_to_recent(self):
        """Scroll main table to show the most recent (rightmost) columns."""
        col_count = self.main_table.columnCount()
        if col_count > 0:
            self.main_table.scrollToItem(
                self.main_table.item(0, col_count - 1),
                QAbstractItemView.PositionAtCenter,
            )

    def re_render(self, decimals: int, label_mode: str = "label", cagr_header: str = "CAGR", show_cagr: bool = True):
        """Re-render with new settings from cached data."""
        if self._data is not None:
            self.update_data(self._data, decimals, label_mode, cagr_header, show_cagr)

    def _apply_theme(self):
        theme = self.theme_manager.current_theme
        if theme == "light":
            self.setStyleSheet(self._get_light_stylesheet())
        elif theme == "bloomberg":
            self.setStyleSheet(self._get_bloomberg_stylesheet())
        else:
            self.setStyleSheet(self._get_dark_stylesheet())

    def _get_dark_stylesheet(self) -> str:
        return """
            QTableWidget {
                background-color: #1e1e1e;
                gridline-color: #2d2d2d;
                border: none;
            }
            QHeaderView::section {
                background-color: #2d2d2d;
                color: #ffffff;
                font-size: 12px;
                font-weight: 600;
                padding: 6px;
                border: 1px solid #3d3d3d;
            }
        """

    def _get_light_stylesheet(self) -> str:
        return """
            QTableWidget {
                background-color: #ffffff;
                gridline-color: #e0e0e0;
                border: none;
            }
            QHeaderView::section {
                background-color: #f0f0f0;
                color: #000000;
                font-size: 12px;
                font-weight: 600;
                padding: 6px;
                border: 1px solid #d0d0d0;
            }
        """

    def _get_bloomberg_stylesheet(self) -> str:
        return """
            QTableWidget {
                background-color: #000814;
                gridline-color: #1a2838;
                border: none;
            }
            QHeaderView::section {
                background-color: #0d1420;
                color: #e8e8e8;
                font-size: 12px;
                font-weight: 600;
                padding: 6px;
                border: 1px solid #1a2838;
            }
        """
