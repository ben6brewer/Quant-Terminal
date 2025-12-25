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
    QMessageBox,
    QSpinBox,
    QColorDialog,
    QGroupBox,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from app.core.theme_manager import ThemeManager


class CreateIndicatorDialog(QDialog):
    """
    Dialog for creating custom indicators with user-specified parameters
    and appearance settings.
    """

    # Define indicator types and their parameters
    INDICATOR_TYPES = {
        "SMA": {
            "name": "Simple Moving Average",
            "params": [
                {"name": "length", "label": "Period", "default": "20", "type": "int"},
            ],
        },
        "EMA": {
            "name": "Exponential Moving Average",
            "params": [
                {"name": "length", "label": "Period", "default": "12", "type": "int"},
            ],
        },
        "Bollinger Bands": {
            "name": "Bollinger Bands",
            "params": [
                {"name": "length", "label": "Period", "default": "20", "type": "int"},
                {"name": "std", "label": "Std Dev", "default": "2", "type": "float"},
            ],
        },
        "RSI": {
            "name": "Relative Strength Index",
            "params": [
                {"name": "length", "label": "Period", "default": "14", "type": "int"},
            ],
        },
        "MACD": {
            "name": "MACD",
            "params": [
                {"name": "fast", "label": "Fast Period", "default": "12", "type": "int"},
                {"name": "slow", "label": "Slow Period", "default": "26", "type": "int"},
                {"name": "signal", "label": "Signal Period", "default": "9", "type": "int"},
            ],
        },
        "ATR": {
            "name": "Average True Range",
            "params": [
                {"name": "length", "label": "Period", "default": "14", "type": "int"},
            ],
        },
        "Stochastic": {
            "name": "Stochastic Oscillator",
            "params": [
                {"name": "k", "label": "K Period", "default": "14", "type": "int"},
                {"name": "d", "label": "D Period", "default": "3", "type": "int"},
                {"name": "smooth_k", "label": "Smooth K", "default": "3", "type": "int"},
            ],
        },
        "OBV": {
            "name": "On-Balance Volume",
            "params": [],  # No parameters
        },
        "VWAP": {
            "name": "Volume Weighted Average Price",
            "params": [],  # No parameters
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

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create Custom Indicator")
        self.setModal(True)
        self.setMinimumWidth(500)
        
        self.theme_manager = theme_manager
        self.param_inputs = {}
        self.selected_color = (0, 150, 255)  # Default blue
        
        self._setup_ui()
        self._apply_theme()

    def _setup_ui(self):
        """Create the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Header
        self.header = QLabel("Create Custom Indicator")
        self.header.setObjectName("dialogHeader")
        layout.addWidget(self.header)

        # Indicator type selector
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Indicator Type:"))
        
        self.type_combo = QComboBox()
        self.type_combo.addItems(list(self.INDICATOR_TYPES.keys()))
        self.type_combo.currentTextChanged.connect(self._on_type_changed)
        type_layout.addWidget(self.type_combo, stretch=1)
        
        layout.addLayout(type_layout)

        # Custom name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Custom Name (optional):"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Leave empty for auto-generated name")
        name_layout.addWidget(self.name_input, stretch=1)
        layout.addLayout(name_layout)

        # Parameter form
        param_group = QGroupBox("Indicator Parameters")
        param_group.setObjectName("paramGroup")
        param_layout = QVBoxLayout(param_group)
        
        self.param_form = QFormLayout()
        self.param_form.setSpacing(10)
        param_layout.addLayout(self.param_form)
        
        layout.addWidget(param_group)

        # Appearance settings
        appearance_group = self._create_appearance_group()
        layout.addWidget(appearance_group)

        # Initialize with first indicator type
        self._on_type_changed(self.type_combo.currentText())

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)
        
        self.create_btn = QPushButton("Create Indicator")
        self.create_btn.setDefault(True)
        self.create_btn.setObjectName("defaultButton")
        self.create_btn.clicked.connect(self._create_indicator)
        button_layout.addWidget(self.create_btn)
        
        layout.addLayout(button_layout)

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
        layout.addRow("Line Width:", self.line_width_spin)

        # Line style
        self.line_style_combo = QComboBox()
        self.line_style_combo.addItems(list(self.LINE_STYLES.keys()))
        layout.addRow("Line Style:", self.line_style_combo)

        # Marker shape (for scatter plots)
        self.marker_shape_combo = QComboBox()
        self.marker_shape_combo.addItems(list(self.MARKER_SHAPES.keys()))
        layout.addRow("Marker Shape:", self.marker_shape_combo)

        # Marker size
        self.marker_size_spin = QSpinBox()
        self.marker_size_spin.setMinimum(4)
        self.marker_size_spin.setMaximum(20)
        self.marker_size_spin.setValue(10)
        self.marker_size_spin.setSuffix(" px")
        layout.addRow("Marker Size:", self.marker_size_spin)

        group.setLayout(layout)
        return group

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
            #dialogHeader {
                color: #00d4ff;
                font-size: 18px;
                font-weight: bold;
                padding: 10px;
            }
            QLabel {
                color: #cccccc;
                font-size: 13px;
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
            #dialogHeader {
                color: #0066cc;
                font-size: 18px;
                font-weight: bold;
                padding: 10px;
            }
            QLabel {
                color: #333333;
                font-size: 13px;
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

    def _create_indicator(self):
        """Validate inputs and create the indicator."""
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
                QMessageBox.warning(
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
        """Get the created indicator configuration."""
        return getattr(self, "result", None)