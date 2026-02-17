"""Reusable crosshair axis overlay — shows value on Y-axis and date on X-axis."""

from typing import Callable, List, Optional

from PySide6.QtCore import Qt, QPoint
from PySide6.QtWidgets import QLabel


class CrosshairOverlay:
    """Manages QLabel overlays on the Y-axis and X-axis of a BaseChart.

    The value label sits on the Y-axis (left or right) following mouse Y.
    The date label sits on the bottom X-axis following mouse X.

    Args:
        chart: The BaseChart instance (used as QLabel parent and for theme helpers).
        plot_item: The PlotItem whose axes provide geometry.
        view_box: The ViewBox for coordinate mapping.
        value_formatter: Callable(float) -> str to format the Y value.
        y_axis_side: "left" or "right" — which Y-axis to overlay on.
    """

    def __init__(self, chart, plot_item, view_box,
                 value_formatter: Callable[[float], str] = None,
                 y_axis_side: str = "right"):
        self._chart = chart
        self._plot_item = plot_item
        self._view_box = view_box
        self._value_formatter = value_formatter or (lambda v: f"{v:.4f}")
        self._y_axis_side = y_axis_side

        self._date_labels: List[str] = []
        self._data_len: int = 0

        self._show_value_label = True
        self._show_date_label = True

        # Create QLabel overlays
        self._value_label = QLabel(chart)
        self._value_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._value_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._value_label.hide()

        self._date_label = QLabel(chart)
        self._date_label.setAlignment(Qt.AlignCenter)
        self._date_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._date_label.hide()

        self._apply_style()

    # ── Public API ────────────────────────────────────────────────────

    def set_data(self, date_labels: List[str], data_len: int):
        """Set the date label lookup list and data length."""
        self._date_labels = date_labels
        self._data_len = data_len

    def set_visible(self, show_value_label: bool, show_date_label: bool):
        """Configure which labels are active."""
        self._show_value_label = show_value_label
        self._show_date_label = show_date_label
        if not show_value_label:
            self._value_label.hide()
        if not show_date_label:
            self._date_label.hide()

    def update(self, mouse_pos: QPoint):
        """Update overlay positions from a mouseMoveEvent pos()."""
        if self._show_value_label:
            self._update_value_label(mouse_pos)
        if self._show_date_label:
            self._update_date_label(mouse_pos)

    def hide(self):
        """Hide both overlay labels (call from leaveEvent)."""
        self._value_label.hide()
        self._date_label.hide()

    def update_theme(self):
        """Re-apply label styles for the current theme."""
        self._apply_style()

    # ── Value Label (Y-axis) ─────────────────────────────────────────

    def _update_value_label(self, mouse_pos: QPoint):
        mouse_y = mouse_pos.y()

        # Bounds check: only show when mouse is within the ViewBox vertically
        vb_scene_rect = self._view_box.sceneBoundingRect()
        vb_widget_tl = self._chart.mapFromScene(vb_scene_rect.topLeft())
        vb_widget_bottom = vb_widget_tl.y() + vb_scene_rect.height()

        if mouse_y < vb_widget_tl.y() or mouse_y > vb_widget_bottom:
            self._value_label.hide()
            return

        y_axis = self._plot_item.getAxis(self._y_axis_side)
        axis_rect = y_axis.geometry()

        # Hide if mouse is over the axis background area
        tick_offset = 11
        if self._y_axis_side == "right":
            axis_bg_start = axis_rect.left() + tick_offset
            if mouse_pos.x() > axis_bg_start:
                self._value_label.hide()
                return
        else:
            if mouse_pos.x() < axis_rect.right():
                self._value_label.hide()
                return

        # Map mouse Y to view coordinates
        view_pos = self._view_box.mapSceneToView(
            self._chart.mapToScene(0, mouse_y)
        )
        value = float(view_pos.y())

        # Format and set text
        self._value_label.setText(self._value_formatter(value))
        self._value_label.adjustSize()

        # Position on the Y-axis (axis_rect X is already in widget coords)
        label_height = self._value_label.sizeHint().height()

        if self._y_axis_side == "right":
            axis_width = axis_rect.width() - tick_offset
            self._value_label.setFixedWidth(max(axis_width, 1))
            x_pos = int(axis_rect.left() + tick_offset)
        else:
            axis_width = axis_rect.width() - tick_offset
            self._value_label.setFixedWidth(max(axis_width, 1))
            x_pos = int(axis_rect.left())

        y_pos = int(mouse_y - label_height / 2)

        self._value_label.move(x_pos, y_pos)
        self._value_label.show()

    # ── Date Label (X-axis) ──────────────────────────────────────────

    def _update_date_label(self, mouse_pos: QPoint):
        if self._data_len == 0:
            self._date_label.hide()
            return

        mouse_x = mouse_pos.x()
        mouse_y = mouse_pos.y()

        # Bounds: hide if mouse is over the Y-axis area
        y_axis = self._plot_item.getAxis(self._y_axis_side)
        y_rect = y_axis.geometry()
        plot_scene_rect = self._plot_item.sceneBoundingRect()
        plot_widget_tl = self._chart.mapFromScene(plot_scene_rect.topLeft())

        if self._y_axis_side == "right":
            if mouse_x >= plot_widget_tl.x() + y_rect.left():
                self._date_label.hide()
                return
        else:
            if mouse_x < plot_widget_tl.x() + y_rect.right():
                self._date_label.hide()
                return

        # Map mouse X to view coordinates
        view_pos = self._view_box.mapSceneToView(
            self._chart.mapToScene(mouse_x, 0)
        )
        x_index = int(round(view_pos.x()))

        if x_index < 0 or x_index >= self._data_len:
            self._date_label.hide()
            return

        # Date text
        if x_index < len(self._date_labels):
            label_text = self._date_labels[x_index]
        else:
            self._date_label.hide()
            return

        self._date_label.setText(label_text)
        self._date_label.adjustSize()

        # Position on the bottom axis
        bottom_axis = self._plot_item.getAxis('bottom')
        axis_rect = bottom_axis.geometry()

        # Bottom axis top in widget coords
        axis_top_y = plot_widget_tl.y() + axis_rect.top()

        # Hide if mouse is below the axis line
        if mouse_y > axis_top_y:
            self._date_label.hide()
            return

        label_width = self._date_label.width()
        label_height = self._date_label.height()

        x_pos = int(mouse_x - label_width / 2)
        axis_center_y = axis_rect.top() + (axis_rect.height() - label_height) / 2
        y_pos = int(plot_widget_tl.y() + axis_center_y) + 2

        self._date_label.move(x_pos, y_pos)
        self._date_label.show()

    # ── Theming ──────────────────────────────────────────────────────

    def _apply_style(self):
        bg_rgb = self._chart._get_background_rgb()
        accent = self._chart._get_theme_accent_color()
        text_rgb = self._chart._get_label_text_color()

        bg_color = f"rgb({bg_rgb[0]}, {bg_rgb[1]}, {bg_rgb[2]})"
        border_color = f"rgb({accent[0]}, {accent[1]}, {accent[2]})"
        text_color = f"rgb({text_rgb[0]}, {text_rgb[1]}, {text_rgb[2]})"

        base = f"""
            background-color: {bg_color};
            color: {text_color};
            border: 1px solid {border_color};
            font-size: 11px;
            font-weight: bold;
        """
        self._value_label.setStyleSheet(f"QLabel {{ {base} padding: 2px 0px; }}")
        self._date_label.setStyleSheet(f"QLabel {{ {base} padding: 2px 4px; }}")
