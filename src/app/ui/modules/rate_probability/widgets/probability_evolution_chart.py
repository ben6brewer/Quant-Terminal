"""Probability Evolution Chart - Historical stacked area chart of rate probabilities."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Dict, List, Optional

import pyqtgraph as pg
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QButtonGroup,
    QFrame,
    QMenu,
    QFileDialog,
    QApplication,
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QColor

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common.lazy_theme_mixin import LazyThemeMixin
from app.ui.widgets.common.no_scroll_combobox import NoScrollComboBox
from app.services.theme_stylesheet_service import ThemeStylesheetService

if TYPE_CHECKING:
    import pandas as pd

# Color palette for outcome buckets (consistent across themes)
OUTCOME_COLORS = {
    "Cut 75bp+": (0, 100, 200),      # Deep blue
    "Cut 50bp": (0, 150, 220),        # Blue
    "Cut 25bp": (0, 200, 180),        # Teal
    "Hold": (180, 180, 180),          # Gray
    "Hike 25bp": (220, 160, 0),       # Amber
    "Hike 50bp": (220, 100, 0),       # Orange
    "Hike 75bp+": (200, 50, 0),       # Red
}


class _DateAxisItem(pg.AxisItem):
    """Custom axis mapping integer x indices to date strings."""

    def __init__(self, orientation="bottom"):
        super().__init__(orientation)
        self._dates: List[str] = []

    def set_dates(self, dates: List[str]):
        self._dates = dates

    def tickStrings(self, values, scale, spacing):
        strings = []
        for v in values:
            idx = int(round(v))
            if 0 <= idx < len(self._dates):
                strings.append(self._dates[idx])
            else:
                strings.append("")
        return strings


class ProbabilityEvolutionChart(LazyThemeMixin, QWidget):
    """Historical probability evolution stacked area chart."""

    meeting_changed = Signal(str)  # Emits selected meeting date string

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._theme_dirty = False
        self._plot_items: list = []
        self._current_period = 90
        self._show_gridlines = True
        self._setup_ui()
        self._apply_theme()
        self.theme_manager.theme_changed.connect(self._on_theme_changed_lazy)

    def showEvent(self, event):
        super().showEvent(event)
        self._check_theme_dirty()

    def _setup_ui(self):
        """Setup chart with controls."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 10)
        layout.setSpacing(8)

        # Controls row
        controls = QHBoxLayout()
        controls.setSpacing(10)

        meeting_label = QLabel("Meeting:")
        meeting_label.setObjectName("control_label")
        controls.addWidget(meeting_label)

        self.meeting_combo = NoScrollComboBox()
        self.meeting_combo.setMinimumWidth(160)
        self.meeting_combo.setFixedHeight(36)
        self.meeting_combo.currentTextChanged.connect(
            lambda text: self.meeting_changed.emit(text) if text else None
        )
        controls.addWidget(self.meeting_combo)

        controls.addSpacing(20)

        # Period toggles
        period_label = QLabel("Period:")
        period_label.setObjectName("control_label")
        controls.addWidget(period_label)

        self._period_group = QButtonGroup(self)
        self._period_group.setExclusive(True)
        self._period_buttons = {}

        for days in [30, 60, 90]:
            btn = QPushButton(f"{days}d")
            btn.setCheckable(True)
            btn.setFixedSize(50, 36)
            btn.setObjectName("period_btn")
            if days == 90:
                btn.setChecked(True)
            btn.clicked.connect(lambda checked, d=days: self._on_period_changed(d))
            controls.addWidget(btn)
            self._period_group.addButton(btn)
            self._period_buttons[days] = btn

        controls.addStretch()
        layout.addLayout(controls)

        # Chart
        self._bottom_axis = _DateAxisItem(orientation="bottom")
        self.plot_widget = pg.GraphicsLayoutWidget()
        layout.addWidget(self.plot_widget, stretch=1)

        self.plot_item = self.plot_widget.addPlot(
            axisItems={"bottom": self._bottom_axis}
        )
        self.plot_item.showGrid(x=True, y=True, alpha=0.3)
        self.plot_item.setLabel("left", "Probability (%)")
        self.plot_item.setLabel("bottom", "Date")
        self.plot_item.setYRange(0, 100)

        # Legend
        self._legend_frame = QFrame()
        self._legend_layout = QHBoxLayout(self._legend_frame)
        self._legend_layout.setContentsMargins(10, 4, 10, 4)
        self._legend_layout.setSpacing(15)
        layout.addWidget(self._legend_frame)

        # Placeholder
        self.placeholder = QLabel("Select a meeting to view probability evolution")
        self.placeholder.setAlignment(Qt.AlignCenter)
        self.placeholder.setStyleSheet("font-size: 16px; color: #888888;")
        layout.addWidget(self.placeholder)
        self.plot_widget.hide()
        self._legend_frame.hide()

    def _on_period_changed(self, days: int):
        """Handle period toggle."""
        self._current_period = days
        # Re-emit meeting changed to trigger refetch with new period
        current = self.meeting_combo.currentText()
        if current:
            self.meeting_changed.emit(current)

    def get_lookback_days(self) -> int:
        """Get current lookback period in days."""
        return self._current_period

    def set_meetings(self, meetings: List[date]):
        """Populate meeting dropdown."""
        self.meeting_combo.blockSignals(True)
        self.meeting_combo.clear()
        for m in meetings:
            self.meeting_combo.addItem(m.strftime("%b %d, %Y"))
        self.meeting_combo.blockSignals(False)

        if self.meeting_combo.count() > 0:
            self.meeting_combo.setCurrentIndex(0)

    def update_data(self, evolution_df: "pd.DataFrame"):
        """Plot stacked area chart from historical probability data."""
        import numpy as np

        self._clear_plot()

        if evolution_df.empty:
            self.show_placeholder("No historical data available for this meeting.")
            return

        self.placeholder.hide()
        self.plot_widget.show()
        self._legend_frame.show()

        n_dates = len(evolution_df)
        x = np.arange(n_dates)

        # Set up date axis labels
        date_labels = []
        for idx in evolution_df.index:
            if hasattr(idx, "strftime"):
                date_labels.append(idx.strftime("%m/%d"))
            else:
                date_labels.append(str(idx))
        self._bottom_axis.set_dates(date_labels)

        # Build stacked areas
        columns = evolution_df.columns.tolist()
        cumulative = np.zeros(n_dates)

        for col in columns:
            values = evolution_df[col].fillna(0).values
            lower = cumulative.copy()
            upper = cumulative + values

            # Get color for this outcome
            color = OUTCOME_COLORS.get(col, (100, 100, 100))

            # Create fill between items
            lower_curve = pg.PlotDataItem(x, lower)
            upper_curve = pg.PlotDataItem(x, upper)
            lower_curve.setClipToView(True)
            upper_curve.setClipToView(True)

            fill = pg.FillBetweenItem(
                lower_curve, upper_curve,
                brush=(*color, 180),
            )
            self.plot_item.addItem(fill)
            self._plot_items.append(fill)

            cumulative = upper

        # Set axis ranges
        self.plot_item.setYRange(0, 100, padding=0.02)
        self.plot_item.setXRange(0, n_dates - 1, padding=0.02)

        # Update legend
        self._update_legend(columns)

    def _update_legend(self, columns: List[str]):
        """Update color legend below chart."""
        # Clear existing
        while self._legend_layout.count():
            item = self._legend_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        c = ThemeStylesheetService.get_colors(self.theme_manager.current_theme)

        for col in columns:
            color = OUTCOME_COLORS.get(col, (100, 100, 100))
            color_hex = f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}"

            swatch = QLabel()
            swatch.setFixedSize(14, 14)
            swatch.setStyleSheet(
                f"background-color: {color_hex}; border-radius: 2px;"
            )

            label = QLabel(col)
            label.setStyleSheet(
                f"color: {c['text_muted']}; font-size: 11px; background: transparent;"
            )

            self._legend_layout.addWidget(swatch)
            self._legend_layout.addWidget(label)

        self._legend_layout.addStretch()

    def apply_settings(self, settings: dict):
        """Apply settings to control gridlines."""
        self._show_gridlines = settings.get("show_gridlines", True)
        alpha = 0.3 if self._show_gridlines else 0.0
        self.plot_item.showGrid(x=self._show_gridlines, y=self._show_gridlines, alpha=alpha)

    def show_placeholder(self, message: str):
        """Show placeholder message."""
        self._clear_plot()
        self.placeholder.setText(message)
        self.placeholder.show()
        self.plot_widget.hide()
        self._legend_frame.hide()

    def _clear_plot(self):
        """Remove all plot items."""
        for item in self._plot_items:
            self.plot_item.removeItem(item)
        self._plot_items.clear()

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
                self, "Save Chart as PNG", "", "PNG Files (*.png)"
            )
            if path:
                self.grab().save(path, "PNG")

    def _apply_theme(self):
        """Apply theme styling."""
        c = ThemeStylesheetService.get_colors(self.theme_manager.current_theme)
        theme = self.theme_manager.current_theme

        if theme == "dark":
            bg_rgb = (30, 30, 30)
            bg_hover = "#3d3d3d"
            grid_color = (80, 80, 80)
        elif theme == "light":
            bg_rgb = (255, 255, 255)
            bg_hover = "#e8e8e8"
            grid_color = (200, 200, 200)
        else:
            bg_rgb = (13, 20, 32)
            bg_hover = "#1a2838"
            grid_color = (50, 60, 80)

        self.plot_widget.setBackground(bg_rgb)

        axis_pen = pg.mkPen(color=grid_color, width=1)
        for axis_name in ("bottom", "left"):
            axis = self.plot_item.getAxis(axis_name)
            axis.setPen(axis_pen)
            axis.setTextPen(c["text"])

        alpha = 0.3 if self._show_gridlines else 0.0
        self.plot_item.showGrid(x=self._show_gridlines, y=self._show_gridlines, alpha=alpha)

        self.setStyleSheet(f"""
            QWidget {{
                background-color: rgb{bg_rgb};
            }}
            QLabel#control_label {{
                color: {c['text']};
                font-size: 13px;
                font-weight: 500;
                background: transparent;
            }}
            QComboBox {{
                background-color: {c['bg_header']};
                color: {c['text']};
                border: 1px solid {c['border']};
                border-radius: 3px;
                padding: 5px 10px;
                font-size: 13px;
            }}
            QComboBox:hover {{
                border-color: {c['accent']};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid {c['text']};
                margin-right: 8px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {c['bg_header']};
                color: {c['text']};
                selection-background-color: {c['accent']};
                selection-color: {c['text_on_accent']};
                font-size: 13px;
            }}
            #period_btn {{
                background-color: {c['bg_header']};
                color: {c['text']};
                border: 1px solid {c['border']};
                border-radius: 3px;
                font-size: 12px;
                font-weight: bold;
            }}
            #period_btn:hover {{
                background-color: {bg_hover};
                border-color: {c['accent']};
            }}
            #period_btn:checked {{
                background-color: {c['accent']};
                color: {c['text_on_accent']};
                border-color: {c['accent']};
            }}
        """)

        self._legend_frame.setStyleSheet(f"background-color: rgb{bg_rgb}; border: none;")
        self.placeholder.setStyleSheet(
            f"font-size: 16px; color: #888888; background: transparent;"
        )
