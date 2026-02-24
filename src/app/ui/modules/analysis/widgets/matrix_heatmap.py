"""Matrix Heatmap Widget - Lower-triangle heatmap for correlation/covariance matrices."""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional

import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel

from app.ui.widgets.charting.base_chart import BaseChart

if TYPE_CHECKING:
    import pandas as pd


COLORSCALES = {
    "Green-Yellow-Red": ([0.0, 0.5, 1.0], [(0, 128, 0, 255), (255, 255, 0, 255), (215, 48, 39, 255)]),
    "Blue-White-Red": ([0.0, 0.5, 1.0], [(44, 123, 182, 255), (255, 255, 255, 255), (215, 48, 39, 255)]),
    "Purple-White-Orange": ([0.0, 0.5, 1.0], [(118, 42, 131, 255), (255, 255, 255, 255), (230, 145, 56, 255)]),
    "Viridis": ([0.0, 0.25, 0.5, 0.75, 1.0], [(68, 1, 84, 255), (59, 82, 139, 255), (33, 145, 140, 255), (94, 201, 98, 255), (253, 231, 37, 255)]),
    "Plasma": ([0.0, 0.25, 0.5, 0.75, 1.0], [(13, 8, 135, 255), (126, 3, 168, 255), (204, 71, 120, 255), (248, 149, 64, 255), (240, 249, 33, 255)]),
}


class MatrixHeatmap(BaseChart):
    """Reusable lower-triangle heatmap chart for correlation and covariance matrices.

    Uses PyQtGraph ImageItem with green-yellow-red colormap and text overlays.
    """

    def __init__(self, parent=None):
        self._update_depth = 0
        super().__init__(parent=parent)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # Plot item for the heatmap
        self.plot_item = self.addPlot()
        self.view_box = self.plot_item.getViewBox()
        self.view_box.setMenuEnabled(False)
        self.view_box.setMouseEnabled(x=False, y=False)
        self.view_box.disableAutoRange()

        # Fully lock the view — reject all mouse interaction
        self.view_box.wheelEvent = lambda ev: ev.ignore()
        self.view_box.mouseDragEvent = lambda ev, axis=None: ev.ignore()
        self.view_box.mouseClickEvent = lambda ev: ev.ignore()

        # Image item for the heatmap cells
        self._image_item = pg.ImageItem()
        self.plot_item.addItem(self._image_item)

        # Text overlays for cell values
        self._text_items: List[pg.TextItem] = []

        # Placeholder text
        self._placeholder = None

        # Summary overlay (pixel-based QLabel)
        self._overlay_label = None
        self._overlay_data = None

        self.set_theme("dark")

    def begin_update(self):
        """Begin a batch update — suppresses repaints until matching end_update()."""
        if self._update_depth == 0:
            self.setUpdatesEnabled(False)
        self._update_depth += 1

    def end_update(self):
        """End a batch update — re-enables repaints when all batches complete."""
        self._update_depth -= 1
        if self._update_depth <= 0:
            self._update_depth = 0
            self.setUpdatesEnabled(True)

    def flush_and_repaint(self):
        """Invalidate cached viewport content and force synchronous repaint."""
        self.resetCachedContent()
        self.viewport().repaint()

    def _apply_gridlines(self):
        """No gridlines for matrix heatmap."""
        self.plot_item.showGrid(x=False, y=False)

    def set_theme(self, theme: str) -> None:
        self.begin_update()
        super().set_theme(theme)
        self._update_overlay_theme()
        self.end_update()

    def set_data(self, matrix: "pd.DataFrame", value_format: str = ".3f", colorscale: str = "Green-Yellow-Red", absolute_colors: bool = False, metadata: Optional[Dict] = None):
        """Render the matrix as a lower-triangle heatmap.

        Args:
            matrix: Square DataFrame (correlation or covariance matrix)
            value_format: Format string for cell values (e.g., ".3f", ".4f")
            colorscale: Name of colorscale from COLORSCALES dict
            absolute_colors: When True, map abs(value) to 0→1 so correlation
                             strength drives color regardless of sign.
            metadata: Optional dict with num_observations, date_start, date_end, periodicity.
        """
        import numpy as np

        self.begin_update()
        self._clear_items()

        labels = list(matrix.index)
        n = len(labels)
        vals = matrix.values

        # Determine color normalization range
        if absolute_colors:
            v_min, v_max = 0.0, 1.0
        else:
            lower = [vals[i, j] for i in range(n) for j in range(i)]
            if lower:
                v_min, v_max = min(lower), max(lower)
            else:
                v_min, v_max = float(vals.min()), float(vals.max())
        v_range = v_max - v_min if v_max != v_min else 1.0

        # Build RGBA image (n x n x 4)
        img = np.zeros((n, n, 4), dtype=np.uint8)

        # Look up colorscale (fall back to default)
        positions, colors = COLORSCALES.get(colorscale, COLORSCALES["Green-Yellow-Red"])
        cmap = pg.ColorMap(positions, colors)

        show_text = value_format != ".0f"

        # Scale font size based on matrix dimension
        # Larger cells (fewer tickers) get bigger text
        cell_font_size = max(9, min(24, int(72 / n)))
        axis_font_size = max(9, min(14, int(48 / n)))

        cell_font = QFont()
        cell_font.setPointSize(cell_font_size)
        label_font = QFont()
        label_font.setPointSize(axis_font_size)

        for i in range(n):
            for j in range(n):
                if j >= i:
                    # Upper triangle + diagonal: transparent
                    img[j, i] = [0, 0, 0, 0]
                else:
                    val = vals[i, j]
                    color_val = abs(val) if absolute_colors else val
                    norm = max(0.0, min(1.0, (color_val - v_min) / v_range))
                    rgba = cmap.map([norm], mode="byte")[0]
                    img[j, i] = rgba

                    if show_text:
                        # Text color based on luminance
                        r, g, b = int(rgba[0]), int(rgba[1]), int(rgba[2])
                        luminance = 0.299 * r + 0.587 * g + 0.114 * b
                        text_color = (0, 0, 0) if luminance > 128 else (255, 255, 255)

                        raw = f"{val:{value_format}}"
                        if raw.startswith("0."):
                            raw = raw[1:]       # "0.123" -> ".123"
                        elif raw.startswith("-0."):
                            raw = "-" + raw[2:] # "-0.123" -> "-.123"
                        text = pg.TextItem(
                            text=raw,
                            color=text_color,
                            anchor=(0.5, 0.5),
                        )
                        text.setFont(cell_font)
                        text.setPos(j + 0.5, i + 0.5)
                        self.plot_item.addItem(text)
                        self._text_items.append(text)

        self._image_item.setImage(img)
        self._image_item.setRect(0, 0, n, n)

        # Configure axes with ticker labels
        bottom_ax = self.plot_item.getAxis("bottom")
        left_ax = self.plot_item.getAxis("left")

        bottom_ticks = [(j + 0.5, labels[j]) for j in range(n)]
        left_ticks = [(i + 0.5, labels[i]) for i in range(n)]
        bottom_ax.setTicks([bottom_ticks])
        left_ax.setTicks([left_ticks])

        bottom_ax.setStyle(tickLength=0, stopAxisAtTick=(True, True))
        left_ax.setStyle(tickLength=0, stopAxisAtTick=(True, True))

        # Style axis labels
        text_color = self._get_label_text_color()
        axis_pen = pg.mkPen(color=text_color, width=1)
        label_style = {"color": f"rgb{text_color}", "font-size": "11px"}
        for ax in (bottom_ax, left_ax):
            ax.setPen(axis_pen)
            ax.setTextPen(pg.mkPen(color=text_color))
            ax.setStyle(tickFont=label_font)

        # Invert Y so row 0 is at the top
        self.view_box.invertY(True)
        self.plot_item.setXRange(0, n, padding=0)
        self.plot_item.setYRange(0, n, padding=0)

        # Render summary overlay in upper-right triangle
        self._render_overlay(matrix, value_format, metadata)

        self.end_update()

    def show_placeholder(self, message: str = "Run analysis to see results"):
        """Show a placeholder message in the center of the chart."""
        import numpy as np

        self.begin_update()
        self._clear_items()
        self._image_item.setImage(np.zeros((1, 1, 4), dtype=np.uint8))
        self._placeholder = pg.TextItem(
            text=message,
            color=self._get_label_text_color(),
            anchor=(0.5, 0.5),
        )
        font = QFont()
        font.setPointSize(14)
        self._placeholder.setFont(font)
        self._placeholder.setPos(0, 0)
        self.plot_item.addItem(self._placeholder)
        self.plot_item.setXRange(-5, 5, padding=0)
        self.plot_item.setYRange(-5, 5, padding=0)
        self.end_update()

    def _clear_items(self):
        """Remove all text overlays and reset image."""
        for item in self._text_items:
            self.plot_item.removeItem(item)
        self._text_items.clear()
        self._clear_overlay()

        if self._placeholder is not None:
            self.plot_item.removeItem(self._placeholder)
            self._placeholder = None

    def _clear_overlay(self):
        """Remove summary overlay label."""
        if self._overlay_label is not None:
            self._overlay_label.deleteLater()
            self._overlay_label = None
        self._overlay_data = None

    def _render_overlay(self, matrix: "pd.DataFrame", value_format: str, metadata: Optional[Dict] = None):
        """Render a pixel-based summary overlay anchored to the top-right corner."""
        import numpy as np

        if metadata is None:
            return

        n = len(matrix)
        labels = list(matrix.index)
        vals = matrix.values

        # Extract lower-triangle off-diagonal values
        tri_rows, tri_cols = np.tril_indices(n, k=-1)
        off_diag = vals[tri_rows, tri_cols]

        if len(off_diag) == 0:
            return

        mean_val = float(np.mean(off_diag))
        median_val = float(np.median(off_diag))
        min_idx = int(np.argmin(off_diag))
        max_idx = int(np.argmax(off_diag))
        min_val = float(off_diag[min_idx])
        max_val = float(off_diag[max_idx])
        min_pair = f"{labels[tri_rows[min_idx]]}-{labels[tri_cols[min_idx]]}"
        max_pair = f"{labels[tri_rows[max_idx]]}-{labels[tri_cols[max_idx]]}"

        def _fmt(v):
            raw = f"{v:{value_format}}"
            if raw.startswith("0."):
                raw = raw[1:]
            elif raw.startswith("-0."):
                raw = "-" + raw[2:]
            return raw

        self._overlay_data = {
            "num_obs": metadata.get("num_observations", "?"),
            "periodicity": metadata.get("periodicity", "daily").capitalize(),
            "date_start": metadata.get("date_start", ""),
            "date_end": metadata.get("date_end", ""),
            "mean": _fmt(mean_val),
            "median": _fmt(median_val),
            "min_val": _fmt(min_val),
            "max_val": _fmt(max_val),
            "min_pair": min_pair,
            "max_pair": max_pair,
        }

        self._overlay_label = QLabel(self)
        self._apply_overlay_style()
        self._overlay_label.adjustSize()
        self._position_overlay()
        self._overlay_label.show()

    def _apply_overlay_style(self):
        """Set overlay HTML content and stylesheet from current theme."""
        if self._overlay_label is None or self._overlay_data is None:
            return

        d = self._overlay_data
        text_color = self._get_label_text_color()
        accent = self._get_theme_accent_color()
        bg_rgb = self._get_background_rgb()

        text_hex = f"#{text_color[0]:02x}{text_color[1]:02x}{text_color[2]:02x}"
        accent_hex = f"#{accent[0]:02x}{accent[1]:02x}{accent[2]:02x}"
        bg_rgba = f"rgba({bg_rgb[0]},{bg_rgb[1]},{bg_rgb[2]},200)"
        border_rgba = f"rgba({accent[0]},{accent[1]},{accent[2]},120)"

        self._overlay_label.setStyleSheet(
            f"QLabel {{ background-color: {bg_rgba}; border: 1px solid {border_rgba};"
            f" border-radius: 4px; padding: 8px; color: {text_hex}; }}"
        )

        # Build aligned text lines
        val_w = max(len(d["min_val"]), len(d["max_val"]))
        min_line = f"Min  {d['min_val']:>{val_w}}  {d['min_pair']}"
        max_line = f"Max  {d['max_val']:>{val_w}}  {d['max_pair']}"

        html = (
            f'<div style="font-family:monospace; font-size:11px; white-space:pre; line-height:1.4;">'
            f'<b style="color:{accent_hex};">Observations</b><br/>'
            f"{d['num_obs']} {d['periodicity']} periods<br/>"
            f"{d['date_start']} \u2192 {d['date_end']}<br/>"
            f"<br/>"
            f'<b style="color:{accent_hex};">Distribution</b><br/>'
            f"{'Mean':<8}{d['mean']}<br/>"
            f"{'Median':<8}{d['median']}<br/>"
            f"{min_line}<br/>"
            f"{max_line}"
            f"</div>"
        )
        self._overlay_label.setText(html)
        self._overlay_label.setTextFormat(Qt.RichText)

    def _position_overlay(self):
        """Position overlay label in the top-right corner."""
        if self._overlay_label is None:
            return
        self._overlay_label.move(
            self.width() - self._overlay_label.width() - 10, 10
        )

    def _update_overlay_theme(self):
        """Update overlay colors when theme changes."""
        if self._overlay_label is None:
            return
        self._apply_overlay_style()
        self._overlay_label.adjustSize()
        self._position_overlay()

    def resizeEvent(self, event):
        """Reposition overlay on resize to stay anchored to top-right."""
        super().resizeEvent(event)
        if hasattr(self, "_overlay_label"):
            self._position_overlay()
