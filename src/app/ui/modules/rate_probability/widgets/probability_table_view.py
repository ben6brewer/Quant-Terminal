"""Probability Table View - CME FedWatch-style conditional probability table."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Tuple

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMenu,
    QFileDialog,
    QApplication,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common.lazy_theme_mixin import LazyThemeMixin
from app.services.theme_stylesheet_service import ThemeStylesheetService

if TYPE_CHECKING:
    import pandas as pd


class ProbabilityTableView(LazyThemeMixin, QWidget):
    """CME FedWatch-style conditional probability table."""

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._theme_dirty = False
        self._prob_df: Optional[pd.DataFrame] = None
        self._show_prob_table = True
        self._show_futures_table = True
        self._setup_ui()
        self._apply_theme()
        self.theme_manager.theme_changed.connect(self._on_theme_changed_lazy)

    def showEvent(self, event):
        super().showEvent(event)
        self._check_theme_dirty()

    def _setup_ui(self):
        """Setup table UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 10)
        layout.setSpacing(8)

        # Horizontal layout: probability table (left) + futures table (right)
        tables_layout = QHBoxLayout()
        tables_layout.setContentsMargins(0, 0, 0, 0)
        tables_layout.setSpacing(12)

        # Main probability table
        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.Stretch)

        # Futures contracts table (right side)
        self.futures_table = QTableWidget()
        self.futures_table.setAlternatingRowColors(True)
        self.futures_table.setSelectionMode(QTableWidget.NoSelection)
        self.futures_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.futures_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.futures_table.verticalHeader().setVisible(False)
        self.futures_table.verticalHeader().setSectionResizeMode(QHeaderView.Stretch)

        # Probability table gets more space (more columns)
        tables_layout.addWidget(self.table, stretch=3)
        tables_layout.addWidget(self.futures_table, stretch=1)
        layout.addLayout(tables_layout, stretch=1)

        # Placeholder
        self.placeholder = QLabel("Loading rate probabilities...")
        self.placeholder.setAlignment(Qt.AlignCenter)
        self.placeholder.setStyleSheet("font-size: 16px; color: #888888;")
        layout.addWidget(self.placeholder)
        self.table.hide()
        self.futures_table.hide()

    def update_data(
        self,
        futures_df: "pd.DataFrame",
        probabilities_df: "pd.DataFrame",
        target_rate: Tuple[float, float],
    ):
        """Populate table with fresh probability data."""
        self._prob_df = probabilities_df

        if probabilities_df.empty:
            self.placeholder.setText("No probability data available.")
            self.placeholder.show()
            self.table.hide()
            self.futures_table.hide()
            return

        self.placeholder.hide()
        if self._show_prob_table:
            self.table.show()
        if self._show_futures_table:
            self.futures_table.show()

        self._populate_futures_table(futures_df)
        self._populate_probability_table(probabilities_df)

    def _populate_futures_table(self, futures_df: "pd.DataFrame"):
        """Build the futures contracts table."""
        if futures_df.empty:
            self.futures_table.hide()
            return

        headers = ["Contract", "Price", "Implied Rate"]
        self.futures_table.setRowCount(len(futures_df))
        self.futures_table.setColumnCount(len(headers))
        self.futures_table.setHorizontalHeaderLabels(headers)

        for row_idx, (_, row) in enumerate(futures_df.iterrows()):
            contract = str(row["contract"]).replace(".CBT", "")
            price = float(row["price"])
            implied = float(row["implied_rate"])

            for col_idx, text in enumerate([contract, f"{price:.3f}", f"{implied:.3f}%"]):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignCenter)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.futures_table.setItem(row_idx, col_idx, item)

    @staticmethod
    def _blend_color(bg_hex: str, accent_hex: str, alpha: float) -> QColor:
        """Blend accent color into background at given alpha (0-1)."""
        bg = QColor(bg_hex)
        ac = QColor(accent_hex)
        r = int(bg.red() + (ac.red() - bg.red()) * alpha)
        g = int(bg.green() + (ac.green() - bg.green()) * alpha)
        b = int(bg.blue() + (ac.blue() - bg.blue()) * alpha)
        return QColor(r, g, b)

    def _populate_probability_table(self, prob_df: "pd.DataFrame"):
        """Fill table cells with probability data and intensity heatmap."""
        c = ThemeStylesheetService.get_colors(self.theme_manager.current_theme)

        meetings = prob_df.index.tolist()
        rate_ranges = prob_df.columns.tolist()

        # Add "Meeting" as first column header
        headers = ["Meeting"] + rate_ranges
        self.table.setRowCount(len(meetings))
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)

        # Global max for intensity scaling
        global_max = prob_df.max().max()
        if global_max <= 0:
            global_max = 1.0

        for row_idx, meeting in enumerate(meetings):
            # Meeting date column
            meeting_item = QTableWidgetItem(str(meeting))
            meeting_item.setTextAlignment(Qt.AlignCenter)
            meeting_item.setFlags(meeting_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row_idx, 0, meeting_item)

            # Alternating row background
            row_bg = c["bg_alt"] if row_idx % 2 else c["bg"]

            for col_idx, rate_range in enumerate(rate_ranges):
                prob = float(prob_df.loc[meeting, rate_range])
                item = QTableWidgetItem(f"{prob:.1f}%" if prob > 0 else "")
                item.setTextAlignment(Qt.AlignCenter)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)

                if prob > 0:
                    intensity = prob / global_max
                    cell_color = self._blend_color(row_bg, c["accent"], intensity)
                    item.setBackground(QBrush(cell_color))
                    # Pick text color based on luminance
                    lum = 0.299 * cell_color.red() + 0.587 * cell_color.green() + 0.114 * cell_color.blue()
                    text_color = "#000000" if lum > 140 else "#ffffff"
                    item.setForeground(QBrush(QColor(text_color)))

                self.table.setItem(row_idx, col_idx + 1, item)


    def apply_settings(self, settings: dict):
        """Apply settings to control table visibility."""
        self._show_prob_table = settings.get("show_probability_table", True)
        self._show_futures_table = settings.get("show_futures_table", True)

        # Only toggle visibility when data is loaded (placeholder hidden)
        if self.placeholder.isHidden():
            self.table.setVisible(self._show_prob_table)
            self.futures_table.setVisible(self._show_futures_table)

    def show_placeholder(self, message: str):
        """Show placeholder message."""
        self.placeholder.setText(message)
        self.placeholder.show()
        self.table.hide()
        self.futures_table.hide()

    def contextMenuEvent(self, event):
        """Show right-click context menu with export options."""
        menu = QMenu(self)
        c = ThemeStylesheetService.get_colors(self.theme_manager.current_theme)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {c['bg_header']};
                color: {c['text']};
                border: 1px solid {c['accent']};
                padding: 4px;
            }}
            QMenu::item:selected {{
                background-color: {c['accent']};
                color: {c['text_on_accent']};
            }}
        """)
        copy_action = menu.addAction("Copy to Clipboard")
        save_action = menu.addAction("Save as PNG...")
        action = menu.exec(event.globalPos())
        if action == copy_action:
            QApplication.clipboard().setPixmap(self.grab())
        elif action == save_action:
            path, _ = QFileDialog.getSaveFileName(
                self, "Save Table as PNG", "", "PNG Files (*.png)"
            )
            if path:
                self.grab().save(path, "PNG")

    def _apply_theme(self):
        """Apply theme styling."""
        c = ThemeStylesheetService.get_colors(self.theme_manager.current_theme)

        self.setStyleSheet(f"""
            QWidget {{
                background-color: {c['bg']};
            }}
        """)

        table_ss = f"""
            QTableWidget {{
                background-color: {c['bg']};
                alternate-background-color: {c['bg_alt']};
                color: {c['text']};
                gridline-color: {c['border']};
                border: 1px solid {c['border']};
                font-size: 12px;
            }}
            QTableWidget::item {{
                padding: 4px 6px;
            }}
            QHeaderView::section {{
                background-color: {c['bg_header']};
                color: {c['text_muted']};
                padding: 6px 4px;
                border: 1px solid {c['border']};
                font-weight: bold;
                font-size: 11px;
            }}
        """
        self.table.setStyleSheet(table_ss)
        self.futures_table.setStyleSheet(table_ss)

        self.placeholder.setStyleSheet(
            f"font-size: 16px; color: #888888; background: transparent;"
        )

        # Re-populate table if data exists (to apply new highlight colors)
        if self._prob_df is not None and not self._prob_df.empty:
            self._populate_probability_table(self._prob_df)
