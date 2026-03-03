"""PCE Chart - Multi-line PCE and Core PCE with Fed 2% reference."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, List

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from app.ui.widgets.charting.base_chart import BaseChart
from app.ui.widgets.charting.axes.date_index_axis import DraggableIndexDateAxisItem
from app.ui.widgets.charting.axes.draggable_axis import DraggableAxisItem

if TYPE_CHECKING:
    import pandas as pd

# PCE = accent color (from theme), Core PCE = fixed secondary color
_CORE_PCE_COLOR = "#EF5350"  # Red — distinct from all 3 theme accents


class PceChart(BaseChart):
    """Multi-line PCE + Core PCE chart with optional Fed 2% target line."""

    def __init__(self, parent=None):
        self._placeholder = None
        super().__init__(parent=parent)

        self._dates: Optional[np.ndarray] = None
        self._pce_values: Optional[np.ndarray] = None
        self._core_pce_values: Optional[np.ndarray] = None
        self._date_labels: list = []
        self._pce_line = None
        self._core_pce_line = None
        self._ref_line = None
        self._legend = None
        self._show_gridlines = True
        self._show_crosshair = True
        self._show_legend = True
        self._show_hover_tooltip = True
        self._show_reference_line = True

        self._setup_plots()
        self._setup_crosshair()
        self._setup_tooltip()
        self._setup_placeholder()

    def _setup_plots(self):
        self._bottom_axis = DraggableIndexDateAxisItem(orientation="bottom")
        self._right_axis = DraggableAxisItem(orientation="right")
        self._right_axis.setWidth(60)

        self.plot_item = self.addPlot(
            axisItems={"bottom": self._bottom_axis, "right": self._right_axis}
        )
        self.view_box = self.plot_item.getViewBox()
        self.view_box.setMouseEnabled(x=True, y=True)

        self.plot_item.showAxis("left", False)
        self.plot_item.showAxis("right", True)
        self.plot_item.showGrid(x=True, y=True, alpha=0.3)
        self._legend = self.plot_item.addLegend(offset=(10, 10))

    def _setup_crosshair(self):
        self._crosshair_v, self._crosshair_h = self._create_crosshair(
            self.plot_item, self.view_box
        )
        self.setMouseTracking(True)

    def _setup_tooltip(self):
        self._tooltip = QLabel(self)
        self._tooltip.setVisible(False)
        self._tooltip.setWordWrap(False)
        self._tooltip.setTextFormat(Qt.RichText)
        self._apply_tooltip_style()

    def _apply_tooltip_style(self):
        bg = self._get_background_rgb()
        text = self._get_label_text_color()
        accent = self._get_theme_accent_color()
        self._tooltip.setStyleSheet(
            f"background-color: rgba({bg[0]}, {bg[1]}, {bg[2]}, 230);"
            f"color: rgb({text[0]}, {text[1]}, {text[2]});"
            f"border: 1px solid rgb({accent[0]}, {accent[1]}, {accent[2]});"
            f"border-radius: 4px; padding: 8px 10px; font-size: 12px;"
            f'font-family: "Menlo", "Consolas", "Courier New";'
        )

    def _setup_placeholder(self):
        self._placeholder = QLabel("Loading PCE data...", self)
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._placeholder.setStyleSheet("font-size: 16px; color: #888888; background: transparent;")
        self._placeholder.setVisible(True)
        self._placeholder.setGeometry(self.rect())

    def show_placeholder(self, message: str = "Loading..."):
        self._placeholder.setText(message)
        self._placeholder.setVisible(True)
        if self.plot_item:
            self.plot_item.clear()
            self._pce_line = None
            self._core_pce_line = None
            self._ref_line = None
            self._legend.clear()
            self._setup_crosshair()

    def update_data(self, pce_df: "Optional[pd.DataFrame]", settings: dict):
        import pandas as pd

        if pce_df is None or pce_df.empty:
            self.show_placeholder("No PCE data available.")
            return

        self._show_gridlines = settings.get("show_gridlines", True)
        self._show_crosshair = settings.get("show_crosshair", True)
        self._show_legend = settings.get("show_legend", True)
        self._show_hover_tooltip = settings.get("show_hover_tooltip", True)
        self._show_reference_line = settings.get("show_reference_line", True)
        show_pce = settings.get("show_pce", True)
        show_core_pce = settings.get("show_core_pce", True)

        if not show_pce and not show_core_pce:
            self.show_placeholder("No series selected.")
            return

        pce_series = pce_df["PCE"].dropna() if "PCE" in pce_df.columns else None
        if pce_series is None or pce_series.empty:
            self.show_placeholder("No PCE data available.")
            return

        self._placeholder.setVisible(False)
        self._dates = pce_series.index.values
        self._pce_values = pce_series.values.astype(float)
        self._date_labels = [pd.Timestamp(d).strftime("%b %Y") for d in self._dates]

        if "Core PCE" in pce_df.columns:
            core_aligned = pce_df["Core PCE"].reindex(pce_series.index)
            self._core_pce_values = core_aligned.values.astype(float)
        else:
            self._core_pce_values = None

        self.plot_item.clear()
        self._pce_line = None
        self._core_pce_line = None
        self._ref_line = None
        self._legend.clear()
        self._setup_crosshair()

        dt_index = pd.DatetimeIndex(self._dates)
        self._bottom_axis.set_index(dt_index)

        x = np.arange(len(self._pce_values))
        accent = self._get_theme_accent_color()

        all_vals = []

        if show_pce:
            self._pce_line = self.plot_item.plot(
                x, self._pce_values,
                pen=pg.mkPen(color=accent, width=2), name="PCE"
            )
            self._pce_line.setClipToView(True)
            all_vals.append(self._pce_values)

        if show_core_pce and self._core_pce_values is not None:
            self._core_pce_line = self.plot_item.plot(
                x, self._core_pce_values,
                pen=pg.mkPen(color=_CORE_PCE_COLOR, width=2), name="Core PCE"
            )
            self._core_pce_line.setClipToView(True)
            all_vals.append(self._core_pce_values)

        if self._show_reference_line:
            self._ref_line = pg.InfiniteLine(
                pos=2.0, angle=0, movable=False,
                pen=pg.mkPen(color=(255, 80, 80), width=1.5, style=Qt.DashLine),
                label="Fed Target: 2%",
                labelOpts={"color": (255, 80, 80), "position": 0.05, "fill": None},
            )
            self.plot_item.addItem(self._ref_line, ignoreBounds=True)

        if all_vals:
            combined = np.concatenate([v for v in all_vals])
            combined = combined[~np.isnan(combined)]
            if len(combined) > 0:
                y_min = float(np.nanmin(combined))
                y_max = float(np.nanmax(combined))
                y_range = y_max - y_min if y_max != y_min else 1.0
                pad = y_range * 0.08
                self.plot_item.setYRange(y_min - pad, y_max + pad, padding=0)

        self.plot_item.setXRange(0, len(self._pce_values) - 1, padding=0.02)
        self.plot_item.showGrid(x=self._show_gridlines, y=self._show_gridlines, alpha=0.3)
        self._legend.setVisible(self._show_legend)

    def _on_mouse_move(self, ev):
        if self._pce_values is None or len(self._pce_values) == 0:
            return
        mouse_pos = ev.pos()
        scene_pos = self.mapToScene(mouse_pos)
        vb_rect = self.view_box.sceneBoundingRect()
        if not vb_rect.contains(scene_pos):
            self._hide_interactive()
            return
        view_pos = self.view_box.mapSceneToView(scene_pos)
        n = len(self._pce_values)
        idx = int(max(0, min(round(view_pos.x()), n - 1)))
        if self._show_crosshair:
            self._crosshair_v.setPos(view_pos.x())
            self._crosshair_h.setPos(view_pos.y())
            self._crosshair_v.setVisible(True)
            self._crosshair_h.setVisible(True)
        self._update_tooltip(idx, mouse_pos)

    def _on_mouse_leave(self, ev):
        self._hide_interactive()

    def _hide_interactive(self):
        if self._crosshair_v:
            self._crosshair_v.setVisible(False)
        if self._crosshair_h:
            self._crosshair_h.setVisible(False)
        if self._tooltip:
            self._tooltip.setVisible(False)

    def _update_tooltip(self, idx: int, mouse_pos):
        if not self._show_hover_tooltip:
            self._tooltip.setVisible(False)
            return
        n = len(self._pce_values)
        if idx < 0 or idx >= n:
            self._tooltip.setVisible(False)
            return

        date_str = self._date_labels[idx] if idx < len(self._date_labels) else "?"
        lines = [f"<b>{date_str}</b>"]

        accent = self._get_theme_accent_color()
        if self._pce_line is not None and self._pce_values is not None:
            pce_val = self._pce_values[idx]
            if not np.isnan(pce_val):
                lines.append(
                    f'<span style="color:rgb({accent[0]},{accent[1]},{accent[2]});">\u25a0</span>'
                    f" PCE: {pce_val:.2f}%"
                )

        if self._core_pce_line is not None and self._core_pce_values is not None and idx < len(self._core_pce_values):
            core_val = self._core_pce_values[idx]
            if not np.isnan(core_val):
                lines.append(
                    f'<span style="color:{_CORE_PCE_COLOR};">\u25a0</span>'
                    f" Core PCE: {core_val:.2f}%"
                )

        self._tooltip.setText("<br>".join(lines))
        self._tooltip.adjustSize()

        tip_w = self._tooltip.width()
        tip_h = self._tooltip.height()
        x = int(mouse_pos.x()) + 16
        y = int(mouse_pos.y()) - tip_h // 2

        if x + tip_w > self.width() - 8:
            x = int(mouse_pos.x()) - tip_w - 16
        if y < 8:
            y = 8
        if y + tip_h > self.height() - 8:
            y = self.height() - tip_h - 8

        self._tooltip.move(x, y)
        self._tooltip.setVisible(True)
        self._tooltip.raise_()

    def set_theme(self, theme: str):
        super().set_theme(theme)
        self._apply_tooltip_style()
        if self._pce_line is not None:
            accent = self._get_theme_accent_color()
            self._pce_line.setPen(pg.mkPen(color=accent, width=2))
        if self._core_pce_line is not None:
            self._core_pce_line.setPen(pg.mkPen(color=_CORE_PCE_COLOR, width=2))
        self._placeholder.setStyleSheet("font-size: 16px; color: #888888; background: transparent;")
        text_color = self._get_label_text_color()
        for axis_name in ("bottom", "right"):
            axis = self.plot_item.getAxis(axis_name)
            if axis:
                axis.setTextPen(text_color)
                axis.label.setDefaultTextColor(pg.mkColor(text_color))

    def showEvent(self, event):
        super().showEvent(event)
        if self._placeholder and self._placeholder.isVisible():
            self._placeholder.setGeometry(self.rect())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._placeholder and self._placeholder.isVisible():
            self._placeholder.setGeometry(self.rect())
