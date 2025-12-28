from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QLineEdit,
    QPushButton,
    QFormLayout,
    QSpinBox,
    QColorDialog,
    QGroupBox,
    QWidget,
)
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QColor, QMouseEvent

from app.core.theme_manager import ThemeManager
from app.ui.widgets.custom_message_box import CustomMessageBox


class CreateIndicatorDialog(QDialog):
    """
    Dialog for creating/editing custom indicators with user-specified parameters
    and appearance settings.
    """

    # Define indicator types and their parameters
    INDICATOR_TYPES = {
        "SMA": {
            "name": "Simple Moving Average",
            "params": [
                {"name": "length", "label": "Period", "default": "20", "type": "int"},
            ],
            "uses_markers": False,  # Only uses lines
        },
        "EMA": {
            "name": "Exponential Moving Average",
            "params": [
                {"name": "length", "label": "Period", "default": "12", "type": "int"},
            ],
            "uses_markers": False,
        },
        "Bollinger Bands": {
            "name": "Bollinger Bands",
            "params": [
                {"name": "length", "label": "Period", "default": "20", "type": "int"},
                {"name": "std", "label": "Std Dev", "default": "2", "type": "float"},
            ],
            "uses_markers": False,
        },
        "RSI": {
            "name": "Relative Strength Index",
            "params": [
                {"name": "length", "label": "Period", "default": "14", "type": "int"},
            ],
            "uses_markers": False,
        },
        "MACD": {
            "name": "MACD",
            "params": [
                {"name": "fast", "label": "Fast Period", "default": "12", "type": "int"},
                {"name": "slow", "label": "Slow Period", "default": "26", "type": "int"},
                {"name": "signal", "label": "Signal Period", "default": "9", "type": "int"},
            ],
            "uses_markers": False,
        },
        "ATR": {
            "name": "Average True Range",
            "params": [
                {"name": "length", "label": "Period", "default": "14", "type": "int"},
            ],
            "uses_markers": False,
        },
        "Stochastic": {
            "name": "Stochastic Oscillator",
            "params": [
                {"name": "k", "label": "K Period", "default": "14", "type": "int"},
                {"name": "d", "label": "D Period", "default": "3", "type": "int"},
                {"name": "smooth_k", "label": "Smooth K", "default": "3", "type": "int"},
            ],
            "uses_markers": False,
        },
        "OBV": {
            "name": "On-Balance Volume",
            "params": [],
            "uses_markers": False,
        },
        "VWAP": {
            "name": "Volume Weighted Average Price",
            "params": [],
            "uses_markers": False,
        },
    }

    # Line style options
    LINE_STYLES = {
        "Solid": Qt.SolidLine,
        "Dashed": Qt.DashLine,
        "Dotted": Qt.DotLine,
        "Dash-Dot": Qt.DashDotLine,
    }

    # Marker/shape options
    MARKER_SHAPES = {
        "Circle": "o",
        "Square": "s",
        "Triangle": "t",
        "Diamond": "d",
        "Plus": "+",
        "Cross": "x",
        "Star": "star",
    }

    # Preset colors
    PRESET_COLORS = [
        ("Blue", (0, 150, 255)),
        ("Orange", (255, 150, 0)),
        ("Purple", (150, 0, 255)),
        ("Yellow", (255, 200, 0)),
        ("Cyan", (0, 255, 150)),
        ("Magenta", (255, 0, 150)),
        ("Green", (76, 175, 80)),
        ("Red", (244, 67, 54)),
        ("White", (255, 255, 255)),
        ("Custom...", None),
    ]

    def __init__(self, theme_manager: ThemeManager, parent=None, edit_mode=False, indicator_config=None):
        super().__init__(parent)
        self.setModal(True)
        self.setMinimumWidth(500)

        # Remove native title bar
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)

        self.theme_manager = theme_manager
        self.edit_mode = edit_mode
        self.indicator_config = indicator_config or {}
        self.param_inputs = {}
        self.selected_color = (0, 150, 255)  # Default blue

        # For window dragging
        self._drag_pos = QPoint()

        self._setup_ui()
        self._apply_theme()

        # If in edit mode, populate fields
        if self.edit_mode and self.indicator_config:
            self._populate_from_config()

    def _setup_ui(self):
        """Create the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Custom title bar
        title_text = "Edit Indicator" if self.edit_mode else "Create Custom Indicator"
        self.title_bar = self._create_title_bar(title_text)
        layout.addWidget(self.title_bar)

        # Content container
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(15, 15, 15, 15)
        content_layout.setSpacing(15)

        # Indicator type selector
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Indicator Type:"))

        self.type_combo = QComboBox()
        self.type_combo.addItems(list(self.INDICATOR_TYPES.keys()))
        self.type_combo.currentTextChanged.connect(self._on_type_changed)

        # Disable type combo in edit mode
        if self.edit_mode:
            self.type_combo.setEnabled(False)

        type_layout.addWidget(self.type_combo, stretch=1)

        content_layout.addLayout(type_layout)

        # Custom name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Custom Name (optional):"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Leave empty for auto-generated name")
        name_layout.addWidget(self.name_input, stretch=1)
        content_layout.addLayout(name_layout)

        # Parameter form
        param_group = QGroupBox("Indicator Parameters")
        param_group.setObjectName("paramGroup")
        param_layout = QVBoxLayout(param_group)

        self.param_form = QFormLayout()
        self.param_form.setSpacing(10)
        param_layout.addLayout(self.param_form)

        content_layout.addWidget(param_group)

        # Appearance settings
        self.appearance_group = self._create_appearance_group()
        content_layout.addWidget(self.appearance_group)

        # Initialize with first indicator type
        self._on_type_changed(self.type_combo.currentText())

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)

        button_text = "Update Indicator" if self.edit_mode else "Create Indicator"
        self.create_btn = QPushButton(button_text)
        self.create_btn.setDefault(True)
        self.create_btn.setObjectName("defaultButton")
        self.create_btn.clicked.connect(self._create_indicator)
        button_layout.addWidget(self.create_btn)

        content_layout.addLayout(button_layout)

        # Add content to main layout
        layout.addWidget(content_widget)

    def _create_title_bar(self, title: str) -> QWidget:
        """Create custom title bar with window controls."""
        title_bar = QWidget()
        title_bar.setObjectName("titleBar")
        title_bar.setFixedHeight(32)

        bar_layout = QHBoxLayout(title_bar)
        bar_layout.setContentsMargins(10, 0, 5, 0)
        bar_layout.setSpacing(5)

        # Dialog title
        self.title_label = QLabel(title)
        self.title_label.setObjectName("titleLabel")
        bar_layout.addWidget(self.title_label)

        bar_layout.addStretch()

        # Close button
        close_btn = QPushButton("✕")
        close_btn.setObjectName("titleBarCloseButton")
        close_btn.setFixedSize(40, 32)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.reject)
        bar_layout.addWidget(close_btn)

        # Enable dragging from title bar
        title_bar.mousePressEvent = self._title_bar_mouse_press
        title_bar.mouseMoveEvent = self._title_bar_mouse_move

        return title_bar

    def _title_bar_mouse_press(self, event: QMouseEvent) -> None:
        """Handle mouse press on title bar for dragging."""
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def _title_bar_mouse_move(self, event: QMouseEvent) -> None:
        """Handle mouse move on title bar for dragging."""
        if event.buttons() == Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def _populate_from_config(self):
        """Populate dialog fields from existing indicator config."""
        config = self.indicator_config
        
        # Set indicator type
        indicator_type = config.get("type")
        if indicator_type:
            index = self.type_combo.findText(indicator_type)
            if index >= 0:
                self.type_combo.setCurrentIndex(index)
        
        # Set custom name
        custom_name = config.get("custom_name", "")
        if custom_name:
            self.name_input.setText(custom_name)
        
        # Set parameters
        params = config.get("params", {})
        for param_name, value in params.items():
            if param_name in self.param_inputs:
                self.param_inputs[param_name]["widget"].setText(str(value))
        
        # Set appearance
        appearance = config.get("appearance", {})
        
        # Color
        color = appearance.get("color", (0, 150, 255))
        self.selected_color = color
        self.color_preview.setStyleSheet(
            f"font-size: 24px; color: rgb({color[0]}, {color[1]}, {color[2]});"
        )
        
        # Find matching preset color or set to Custom
        color_index = len(self.PRESET_COLORS) - 1  # Default to Custom
        for i, (name, preset_color) in enumerate(self.PRESET_COLORS[:-1]):
            if preset_color == color:
                color_index = i
                break
        self.color_combo.setCurrentIndex(color_index)
        
        # Line width
        line_width = appearance.get("line_width", 2)
        self.line_width_spin.setValue(line_width)
        
        # Line style
        line_style = appearance.get("line_style", Qt.SolidLine)
        for style_name, style_value in self.LINE_STYLES.items():
            if style_value == line_style:
                index = self.line_style_combo.findText(style_name)
                if index >= 0:
                    self.line_style_combo.setCurrentIndex(index)
                break
        
        # Marker shape
        marker_shape = appearance.get("marker_shape", "o")
        for shape_name, shape_value in self.MARKER_SHAPES.items():
            if shape_value == marker_shape:
                index = self.marker_shape_combo.findText(shape_name)
                if index >= 0:
                    self.marker_shape_combo.setCurrentIndex(index)
                break
        
        # Marker size
        marker_size = appearance.get("marker_size", 10)
        self.marker_size_spin.setValue(marker_size)

    def _create_appearance_group(self) -> QGroupBox:
        """Create appearance settings group."""
        group = QGroupBox("Appearance Settings")
        group.setObjectName("appearanceGroup")
        layout = QFormLayout()
        layout.setSpacing(10)

        # Color selection
        color_layout = QHBoxLayout()
        self.color_combo = QComboBox()
        for color_name, _ in self.PRESET_COLORS:
            self.color_combo.addItem(color_name)
        self.color_combo.currentTextChanged.connect(self._on_color_changed)
        color_layout.addWidget(self.color_combo, stretch=1)
        
        self.color_preview = QLabel("●")
        self.color_preview.setStyleSheet("font-size: 24px; color: rgb(0, 150, 255);")
        color_layout.addWidget(self.color_preview)
        
        layout.addRow("Color:", color_layout)

        # Line width
        self.line_width_spin = QSpinBox()
        self.line_width_spin.setMinimum(1)
        self.line_width_spin.setMaximum(10)
        self.line_width_spin.setValue(2)
        self.line_width_spin.setSuffix(" px")
        self.line_width_row = layout.rowCount()
        layout.addRow("Line Width:", self.line_width_spin)

        # Line style
        self.line_style_combo = QComboBox()
        self.line_style_combo.addItems(list(self.LINE_STYLES.keys()))
        self.line_style_row = layout.rowCount()
        layout.addRow("Line Style:", self.line_style_combo)

        # Marker shape (for scatter plots)
        self.marker_shape_combo = QComboBox()
        self.marker_shape_combo.addItems(list(self.MARKER_SHAPES.keys()))
        self.marker_shape_row = layout.rowCount()
        layout.addRow("Marker Shape:", self.marker_shape_combo)

        # Marker size
        self.marker_size_spin = QSpinBox()
        self.marker_size_spin.setMinimum(4)
        self.marker_size_spin.setMaximum(20)
        self.marker_size_spin.setValue(10)
        self.marker_size_spin.setSuffix(" px")
        self.marker_size_row = layout.rowCount()
        layout.addRow("Marker Size:", self.marker_size_spin)

        group.setLayout(layout)
        return group

    def _update_appearance_visibility(self, indicator_type: str):
        """Show/hide appearance options based on indicator type."""
        indicator_info = self.INDICATOR_TYPES.get(indicator_type, {})
        uses_markers = indicator_info.get("uses_markers", False)
        
        # Get the form layout
        form_layout = self.appearance_group.layout()
        
        # Show/hide marker-related fields
        # Line options are always visible
        # Marker options only visible if indicator uses markers
        
        if hasattr(self, 'marker_shape_row'):
            # Hide marker shape
            label_item = form_layout.itemAt(self.marker_shape_row, QFormLayout.LabelRole)
            field_item = form_layout.itemAt(self.marker_shape_row, QFormLayout.FieldRole)
            
            if label_item and label_item.widget():
                label_item.widget().setVisible(uses_markers)
            if field_item and field_item.widget():
                field_item.widget().setVisible(uses_markers)
        
        if hasattr(self, 'marker_size_row'):
            # Hide marker size
            label_item = form_layout.itemAt(self.marker_size_row, QFormLayout.LabelRole)
            field_item = form_layout.itemAt(self.marker_size_row, QFormLayout.FieldRole)
            
            if label_item and label_item.widget():
                label_item.widget().setVisible(uses_markers)
            if field_item and field_item.widget():
                field_item.widget().setVisible(uses_markers)

    def _on_color_changed(self, color_name: str):
        """Handle color selection change."""
        if color_name == "Custom...":
            # Open color picker
            current_color = QColor(*self.selected_color)
            color = QColorDialog.getColor(current_color, self, "Select Indicator Color")
            
            if color.isValid():
                self.selected_color = (color.red(), color.green(), color.blue())
                self.color_preview.setStyleSheet(
                    f"font-size: 24px; color: rgb({color.red()}, {color.green()}, {color.blue()});"
                )
            else:
                # User canceled, revert to previous selection
                # Find the previous color in the preset list
                for i, (name, rgb) in enumerate(self.PRESET_COLORS[:-1]):
                    if rgb == self.selected_color:
                        self.color_combo.setCurrentIndex(i)
                        break
        else:
            # Use preset color
            for name, rgb in self.PRESET_COLORS:
                if name == color_name and rgb is not None:
                    self.selected_color = rgb
                    self.color_preview.setStyleSheet(
                        f"font-size: 24px; color: rgb({rgb[0]}, {rgb[1]}, {rgb[2]});"
                    )
                    break

    def _apply_theme(self):
        """Apply the current theme to the dialog."""
        theme = self.theme_manager.current_theme

        if theme == "light":
            stylesheet = self._get_light_stylesheet()
        elif theme == "bloomberg":
            stylesheet = self._get_bloomberg_stylesheet()
        else:
            stylesheet = self._get_dark_stylesheet()

        self.setStyleSheet(stylesheet)

    def _get_dark_stylesheet(self) -> str:
        """Get dark theme stylesheet."""
        return """
            QDialog {
                background-color: #2d2d2d;
                color: #ffffff;
            }
            #titleBar {
                background-color: #2d2d2d;
                border-bottom: 1px solid #3d3d3d;
            }
            #titleLabel {
                background-color: transparent;
                color: #ffffff;
                font-size: 13px;
                font-weight: 500;
            }
            #titleBarCloseButton {
                background-color: transparent;
                color: #ffffff;
                border: none;
                font-size: 14px;
                font-weight: bold;
            }
            #titleBarCloseButton:hover {
                background-color: #d32f2f;
            }
            QLabel {
                color: #cccccc;
                font-size: 13px;
                background-color: transparent;
            }
            QGroupBox {
                color: #ffffff;
                background-color: #2d2d2d;
                border: 2px solid #3d3d3d;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 20px;
                font-size: 14px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 5px;
            }
            QComboBox {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 8px;
                font-size: 13px;
            }
            QComboBox:hover {
                border: 1px solid #00d4ff;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: #2d2d2d;
                color: #ffffff;
                selection-background-color: #00d4ff;
                selection-color: #000000;
            }
            QLineEdit {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 8px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #00d4ff;
            }
            QSpinBox {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 8px;
                font-size: 13px;
            }
            QSpinBox:hover {
                border: 1px solid #00d4ff;
            }
            QPushButton {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 10px 20px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                border: 1px solid #00d4ff;
                background-color: #2d2d2d;
            }
            QPushButton:pressed {
                background-color: #00d4ff;
                color: #000000;
            }
            QPushButton#defaultButton {
                background-color: #00d4ff;
                color: #000000;
                border: 1px solid #00d4ff;
            }
            QPushButton#defaultButton:hover {
                background-color: #00c4ef;
            }
        """

    def _get_light_stylesheet(self) -> str:
        """Get light theme stylesheet."""
        return """
            QDialog {
                background-color: #ffffff;
                color: #000000;
            }
            #titleBar {
                background-color: #f5f5f5;
                border-bottom: 1px solid #cccccc;
            }
            #titleLabel {
                background-color: transparent;
                color: #000000;
                font-size: 13px;
                font-weight: 500;
            }
            #titleBarCloseButton {
                background-color: transparent;
                color: #000000;
                border: none;
                font-size: 14px;
                font-weight: bold;
            }
            #titleBarCloseButton:hover {
                background-color: #d32f2f;
                color: #ffffff;
            }
            QLabel {
                color: #333333;
                font-size: 13px;
                background-color: transparent;
            }
            QGroupBox {
                color: #000000;
                background-color: #f5f5f5;
                border: 2px solid #d0d0d0;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 20px;
                font-size: 14px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 5px;
            }
            QComboBox {
                background-color: #f5f5f5;
                color: #000000;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 8px;
                font-size: 13px;
            }
            QComboBox:hover {
                border: 1px solid #0066cc;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: #ffffff;
                color: #000000;
                selection-background-color: #0066cc;
                selection-color: #ffffff;
            }
            QLineEdit {
                background-color: #f5f5f5;
                color: #000000;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 8px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #0066cc;
            }
            QSpinBox {
                background-color: #f5f5f5;
                color: #000000;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 8px;
                font-size: 13px;
            }
            QSpinBox:hover {
                border: 1px solid #0066cc;
            }
            QPushButton {
                background-color: #f5f5f5;
                color: #000000;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 10px 20px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                border: 1px solid #0066cc;
                background-color: #e8e8e8;
            }
            QPushButton:pressed {
                background-color: #0066cc;
                color: #ffffff;
            }
            QPushButton#defaultButton {
                background-color: #0066cc;
                color: #ffffff;
                border: 1px solid #0066cc;
            }
            QPushButton#defaultButton:hover {
                background-color: #0052a3;
            }
        """

    def _get_bloomberg_stylesheet(self) -> str:
        """Get Bloomberg theme stylesheet."""
        return """
            QDialog {
                background-color: #0d1420;
                color: #e8e8e8;
            }
            #titleBar {
                background-color: #0d1420;
                border-bottom: 1px solid #1a2332;
            }
            #titleLabel {
                background-color: transparent;
                color: #e8e8e8;
                font-size: 13px;
                font-weight: 500;
            }
            #titleBarCloseButton {
                background-color: transparent;
                color: #e8e8e8;
                border: none;
                font-size: 14px;
                font-weight: bold;
            }
            #titleBarCloseButton:hover {
                background-color: #d32f2f;
                color: #ffffff;
            }
            QLabel {
                color: #b0b0b0;
                font-size: 13px;
                background-color: transparent;
            }
            QGroupBox {
                color: #e8e8e8;
                background-color: #0d1420;
                border: 2px solid #1a2332;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 20px;
                font-size: 14px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 5px;
            }
            QComboBox {
                background-color: transparent;
                color: #e8e8e8;
                border: 1px solid #1a2332;
                border-radius: 2px;
                padding: 8px;
                font-size: 13px;
            }
            QComboBox:hover {
                border: 1px solid #FF8000;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: #0d1420;
                color: #e8e8e8;
                selection-background-color: #FF8000;
                selection-color: #000000;
            }
            QLineEdit {
                background-color: transparent;
                color: #e8e8e8;
                border: 1px solid #1a2332;
                border-radius: 2px;
                padding: 8px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #FF8000;
            }
            QSpinBox {
                background-color: transparent;
                color: #e8e8e8;
                border: 1px solid #1a2332;
                border-radius: 2px;
                padding: 8px;
                font-size: 13px;
            }
            QSpinBox:hover {
                border: 1px solid #FF8000;
            }
            QPushButton {
                background-color: transparent;
                color: #e8e8e8;
                border: 1px solid #1a2332;
                border-radius: 2px;
                padding: 10px 20px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                border: 1px solid #FF8000;
                background-color: rgba(255, 128, 0, 0.1);
            }
            QPushButton:pressed {
                background-color: #FF8000;
                color: #000000;
            }
            QPushButton#defaultButton {
                background-color: #FF8000;
                color: #000000;
                border: 1px solid #FF8000;
            }
            QPushButton#defaultButton:hover {
                background-color: #FF9520;
            }
        """

    def _on_type_changed(self, indicator_type: str):
        """Update parameter form when indicator type changes."""
        # Clear existing parameter inputs
        while self.param_form.rowCount() > 0:
            self.param_form.removeRow(0)
        self.param_inputs.clear()

        # Get parameter definitions for this indicator type
        indicator_info = self.INDICATOR_TYPES.get(indicator_type, {})
        params = indicator_info.get("params", [])

        # Add parameter inputs
        for param in params:
            label = QLabel(f"{param['label']}:")
            input_field = QLineEdit()
            input_field.setText(param["default"])
            input_field.setPlaceholderText(f"Enter {param['label'].lower()}")
            
            self.param_form.addRow(label, input_field)
            self.param_inputs[param["name"]] = {
                "widget": input_field,
                "type": param["type"],
            }

        # If no parameters, show a message
        if not params:
            no_params_label = QLabel("This indicator has no configurable parameters.")
            no_params_label.setStyleSheet("font-style: italic; color: #888888;")
            self.param_form.addRow(no_params_label)
        
        # Update appearance field visibility
        self._update_appearance_visibility(indicator_type)

    def _create_indicator(self):
        """Validate inputs and create/update the indicator."""
        indicator_type = self.type_combo.currentText()
        
        # Collect and validate parameters
        params = {}
        for param_name, param_info in self.param_inputs.items():
            value_str = param_info["widget"].text().strip()
            param_type = param_info["type"]
            
            try:
                if param_type == "int":
                    value = int(value_str)
                    if value <= 0:
                        raise ValueError("Must be positive")
                elif param_type == "float":
                    value = float(value_str)
                    if value <= 0:
                        raise ValueError("Must be positive")
                else:
                    value = value_str
                
                params[param_name] = value
                
            except ValueError as e:
                CustomMessageBox.warning(
                    self.theme_manager,
                    self,
                    "Invalid Input",
                    f"Invalid value for {param_name}: {value_str}\n{str(e)}",
                )
                return

        # Get custom name if provided
        custom_name = self.name_input.text().strip()

        # Collect appearance settings
        appearance = {
            "color": self.selected_color,
            "line_width": self.line_width_spin.value(),
            "line_style": self.LINE_STYLES[self.line_style_combo.currentText()],
            "marker_shape": self.MARKER_SHAPES[self.marker_shape_combo.currentText()],
            "marker_size": self.marker_size_spin.value(),
        }

        # Store the result
        self.result = {
            "type": indicator_type,
            "params": params,
            "custom_name": custom_name or None,
            "appearance": appearance,
        }
        
        self.accept()

    def get_indicator_config(self):
        """Get the created/edited indicator configuration."""
        return getattr(self, "result", None)