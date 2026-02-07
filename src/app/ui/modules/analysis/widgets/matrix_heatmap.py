"""Matrix Heatmap Widget - Lower-triangle heatmap for correlation/covariance matrices."""

from __future__ import annotations

from typing import TYPE_CHECKING, List

import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

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
        self.end_update()

    def set_data(self, matrix: "pd.DataFrame", value_format: str = ".3f", colorscale: str = "Green-Yellow-Red"):
        """Render the matrix as a lower-triangle heatmap.

        Args:
            matrix: Square DataFrame (correlation or covariance matrix)
            value_format: Format string for cell values (e.g., ".3f", ".4f")
            colorscale: Name of colorscale from COLORSCALES dict
        """
        import numpy as np

        self.begin_update()
        self._clear_items()

        labels = list(matrix.index)
        n = len(labels)
        vals = matrix.values

        # Collect lower triangle values (exclude diagonal) for normalization
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
                    norm = max(0.0, min(1.0, (val - v_min) / v_range))
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

        if self._placeholder is not None:
            self.plot_item.removeItem(self._placeholder)
            self._placeholder = None
