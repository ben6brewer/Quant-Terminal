"""Rate Path Chart - Implied rate path line chart using PyQtGraph."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Tuple

import pyqtgraph as pg
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QMenu, QFileDialog, QApplication
from PySide6.QtCore import Qt

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common.lazy_theme_mixin import LazyThemeMixin
from app.services.theme_stylesheet_service import ThemeStylesheetService


class _MeetingDateAxisItem(pg.AxisItem):
    """Custom axis that maps integer indices to meeting date strings."""

    def __init__(self, orientation="bottom"):
        super().__init__(orientation)
        self._labels: List[str] = []

    def set_labels(self, labels: List[str]):
        self._labels = labels

    def tickValues(self, minVal, maxVal, size):
        """Force ticks at every integer index where we have a label."""
        if not self._labels:
            return super().tickValues(minVal, maxVal, size)
        ticks = [i for i in range(len(self._labels))
                 if minVal - 0.5 <= i <= maxVal + 0.5]
        return [(1, ticks)]

    def tickStrings(self, values, scale, spacing):
        strings = []
        for v in values:
            idx = int(round(v))
            if 0 <= idx < len(self._labels):
                strings.append(self._labels[idx])
            else:
                strings.append("")
        return strings


class RatePathChart(LazyThemeMixin, QWidget):
    """Implied rate path line chart."""

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._theme_dirty = False
        self._plot_items: list = []
        self._show_gridlines = True
        self._setup_ui()
        self._apply_theme()
        self.theme_manager.theme_changed.connect(self._on_theme_changed_lazy)

    def showEvent(self, event):
        super().showEvent(event)
        self._check_theme_dirty()

    def _setup_ui(self):
        """Setup chart UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Chart widget
        self._bottom_axis = _MeetingDateAxisItem(orientation="bottom")
        self.plot_widget = pg.GraphicsLayoutWidget()
        layout.addWidget(self.plot_widget, stretch=1)

        self.plot_item = self.plot_widget.addPlot(
            axisItems={"bottom": self._bottom_axis}
        )
        self.plot_item.showGrid(x=True, y=True, alpha=0.3)
        self.plot_item.setLabel("left", "Rate (%)")
        self.plot_item.setLabel("bottom", "FOMC Meeting")

        # Placeholder
        self.placeholder = QLabel("Loading rate path...")
        self.placeholder.setAlignment(Qt.AlignCenter)
        self.placeholder.setStyleSheet("font-size: 16px; color: #888888;")
        layout.addWidget(self.placeholder)
        self.plot_widget.hide()

    def update_data(
        self,
        rate_path: List[Tuple[str, float]],
        current_rate: float,
    ):
        """Plot the implied rate path with current rate reference line."""
        self._clear_plot()

        if not rate_path:
            self.show_placeholder("No rate path data available.")
            return

        self.placeholder.hide()
        self.plot_widget.show()

        labels = [r[0] for r in rate_path]
        rates = [r[1] for r in rate_path]
        x = list(range(len(rate_path)))

        self._bottom_axis.set_labels(labels)

        c = ThemeStylesheetService.get_colors(self.theme_manager.current_theme)

        # Current rate reference line
        ref_line = pg.InfiniteLine(
            pos=current_rate,
            angle=0,
            pen=pg.mkPen(color=(150, 150, 150), width=1, style=Qt.DashLine),
            label=f"Current: {current_rate:.2f}%",
            labelOpts={
                "color": c["text_muted"],
                "position": 0.05,
                "fill": None,
            },
        )
        self.plot_item.addItem(ref_line)
        self._plot_items.append(ref_line)

        # Rate path line
        accent_color = c["accent"]
        pen = pg.mkPen(color=accent_color, width=3)
        line = self.plot_item.plot(x, rates, pen=pen, name="Implied Rate")
        self._plot_items.append(line)

        # Scatter points at each meeting
        scatter = pg.ScatterPlotItem(
            x=x, y=rates, size=12, pen=pg.mkPen(accent_color, width=2),
            brush=pg.mkBrush(accent_color),
        )
        self.plot_item.addItem(scatter)
        self._plot_items.append(scatter)

        # Text labels at each point
        for i, (label, rate) in enumerate(rate_path):
            text = pg.TextItem(
                text=f"{rate:.2f}%",
                color=c["text"],
                anchor=(0.5, 1.5),
            )
            text.setPos(i, rate)
            self.plot_item.addItem(text)
            self._plot_items.append(text)

        # Auto-range with padding
        self.plot_item.autoRange()
        self.plot_item.setXRange(-0.5, len(rate_path) - 0.5, padding=0.05)

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
            grid_color = (80, 80, 80)
        elif theme == "light":
            bg_rgb = (255, 255, 255)
            grid_color = (200, 200, 200)
        else:
            bg_rgb = (13, 20, 32)
            grid_color = (50, 60, 80)

        self.plot_widget.setBackground(bg_rgb)
        self.setStyleSheet(f"background-color: rgb{bg_rgb};")

        axis_pen = pg.mkPen(color=grid_color, width=1)
        for axis_name in ("bottom", "left"):
            axis = self.plot_item.getAxis(axis_name)
            axis.setPen(axis_pen)
            axis.setTextPen(c["text"])

        alpha = 0.3 if self._show_gridlines else 0.0
        self.plot_item.showGrid(x=self._show_gridlines, y=self._show_gridlines, alpha=alpha)
        self.placeholder.setStyleSheet(
            f"font-size: 16px; color: #888888; background: transparent;"
        )
