from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QFormLayout,
    QMessageBox,
    QDoubleSpinBox,
    QSpinBox,
    QColorDialog,
    QGroupBox,
    QCheckBox,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from app.core.theme_manager import ThemeManager


class ChartSettingsDialog(QDialog):
    """
    Dialog for customizing chart appearance settings.
    """

    # Line style options
    LINE_STYLES = {
        "Solid": Qt.SolidLine,
        "Dashed": Qt.DashLine,
        "Dotted": Qt.DotLine,
        "Dash-Dot": Qt.DashDotLine,
    }

    def __init__(self, theme_manager: ThemeManager, current_settings: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Chart Settings")
        self.setModal(True)
        self.setMinimumWidth(500)
        
        self.theme_manager = theme_manager
        self.current_settings = current_settings
        
        # Color selections
        self.candle_up_color = current_settings.get("candle_up_color", (76, 153, 0))
        self.candle_down_color = current_settings.get("candle_down_color", (200, 50, 50))
        self.line_color = current_settings.get("line_color", None)
        self.chart_background = current_settings.get("chart_background", None)
        
        self._setup_ui()
        self._apply_theme()
        self._load_current_settings()

    def _setup_ui(self):
        """Create the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Header
        self.header = QLabel("Chart Appearance Settings")
        self.header.setObjectName("dialogHeader")
        layout.addWidget(self.header)

        # Candlestick settings
        candle_group = self._create_candle_group()
        layout.addWidget(candle_group)

        # Line chart settings
        line_group = self._create_line_group()
        layout.addWidget(line_group)

        # Chart background settings
        background_group = self._create_background_group()
        layout.addWidget(background_group)

        # General settings
        general_group = self._create_general_group()
        layout.addWidget(general_group)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.reset_btn = QPushButton("Reset to Defaults")
        self.reset_btn.clicked.connect(self._reset_to_defaults)
        button_layout.addWidget(self.reset_btn)
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)
        
        self.save_btn = QPushButton("Save Settings")
        self.save_btn.setDefault(True)
        self.save_btn.setObjectName("defaultButton")
        self.save_btn.clicked.connect(self._save_settings)
        button_layout.addWidget(self.save_btn)
        
        layout.addLayout(button_layout)

    def _create_candle_group(self) -> QGroupBox:
        """Create candlestick settings group."""
        group = QGroupBox("Candlestick Settings")
        group.setObjectName("settingsGroup")
        layout = QFormLayout()
        layout.setSpacing(10)

        # Up candle color
        up_color_layout = QHBoxLayout()
        self.up_color_btn = QPushButton("Choose Color")
        self.up_color_btn.clicked.connect(lambda: self._choose_color("up"))
        up_color_layout.addWidget(self.up_color_btn)
        
        self.up_color_preview = QLabel("●")
        self.up_color_preview.setStyleSheet(
            f"font-size: 24px; color: rgb({self.candle_up_color[0]}, "
            f"{self.candle_up_color[1]}, {self.candle_up_color[2]});"
        )
        up_color_layout.addWidget(self.up_color_preview)
        up_color_layout.addStretch()
        
        layout.addRow("Up Candle Color:", up_color_layout)

        # Down candle color
        down_color_layout = QHBoxLayout()
        self.down_color_btn = QPushButton("Choose Color")
        self.down_color_btn.clicked.connect(lambda: self._choose_color("down"))
        down_color_layout.addWidget(self.down_color_btn)
        
        self.down_color_preview = QLabel("●")
        self.down_color_preview.setStyleSheet(
            f"font-size: 24px; color: rgb({self.candle_down_color[0]}, "
            f"{self.candle_down_color[1]}, {self.candle_down_color[2]});"
        )
        down_color_layout.addWidget(self.down_color_preview)
        down_color_layout.addStretch()
        
        layout.addRow("Down Candle Color:", down_color_layout)

        # Candle width
        self.candle_width_spin = QDoubleSpinBox()
        self.candle_width_spin.setMinimum(0.1)
        self.candle_width_spin.setMaximum(1.0)
        self.candle_width_spin.setSingleStep(0.1)
        self.candle_width_spin.setValue(0.6)
        self.candle_width_spin.setDecimals(1)
        layout.addRow("Candle Width:", self.candle_width_spin)

        group.setLayout(layout)
        return group

    def _create_line_group(self) -> QGroupBox:
        """Create line chart settings group."""
        group = QGroupBox("Line Chart Settings")
        group.setObjectName("settingsGroup")
        layout = QFormLayout()
        layout.setSpacing(10)

        # Line color with "Use Theme Default" checkbox
        line_color_layout = QVBoxLayout()
        
        self.line_use_theme_check = QCheckBox("Use Theme Default")
        self.line_use_theme_check.setChecked(self.line_color is None)
        self.line_use_theme_check.toggled.connect(self._on_line_theme_toggled)
        line_color_layout.addWidget(self.line_use_theme_check)
        
        line_color_picker_layout = QHBoxLayout()
        self.line_color_btn = QPushButton("Choose Color")
        self.line_color_btn.clicked.connect(lambda: self._choose_color("line"))
        self.line_color_btn.setEnabled(self.line_color is not None)
        line_color_picker_layout.addWidget(self.line_color_btn)
        
        self.line_color_preview = QLabel("●")
        if self.line_color:
            self.line_color_preview.setStyleSheet(
                f"font-size: 24px; color: rgb({self.line_color[0]}, "
                f"{self.line_color[1]}, {self.line_color[2]});"
            )
        else:
            # Show theme default
            theme_color = self.theme_manager.get_chart_line_color()
            self.line_color_preview.setStyleSheet(
                f"font-size: 24px; color: rgb({theme_color[0]}, "
                f"{theme_color[1]}, {theme_color[2]});"
            )
        line_color_picker_layout.addWidget(self.line_color_preview)
        line_color_picker_layout.addStretch()
        
        line_color_layout.addLayout(line_color_picker_layout)
        layout.addRow("Line Color:", line_color_layout)

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

        group.setLayout(layout)
        return group

    def _create_background_group(self) -> QGroupBox:
        """Create background settings group."""
        group = QGroupBox("Chart Background")
        group.setObjectName("settingsGroup")
        layout = QFormLayout()
        layout.setSpacing(10)

        # Background color with "Use Theme Default" checkbox
        bg_layout = QVBoxLayout()
        
        self.bg_use_theme_check = QCheckBox("Use Theme Default")
        self.bg_use_theme_check.setChecked(self.chart_background is None)
        self.bg_use_theme_check.toggled.connect(self._on_bg_theme_toggled)
        bg_layout.addWidget(self.bg_use_theme_check)
        
        bg_color_picker_layout = QHBoxLayout()
        self.bg_color_btn = QPushButton("Choose Color")
        self.bg_color_btn.clicked.connect(lambda: self._choose_color("background"))
        self.bg_color_btn.setEnabled(self.chart_background is not None)
        bg_color_picker_layout.addWidget(self.bg_color_btn)
        
        self.bg_color_preview = QLabel("■")
        if self.chart_background:
            self.bg_color_preview.setStyleSheet(
                f"font-size: 24px; color: rgb({self.chart_background[0]}, "
                f"{self.chart_background[1]}, {self.chart_background[2]});"
            )
        else:
            # Show theme default (simplified, just show a placeholder)
            self.bg_color_preview.setStyleSheet("font-size: 24px; color: #888888;")
        bg_color_picker_layout.addWidget(self.bg_color_preview)
        bg_color_picker_layout.addStretch()
        
        bg_layout.addLayout(bg_color_picker_layout)
        layout.addRow("Background Color:", bg_layout)

        group.setLayout(layout)
        return group

    def _create_general_group(self) -> QGroupBox:
        """Create general settings group."""
        group = QGroupBox("General")
        group.setObjectName("settingsGroup")
        layout = QVBoxLayout()
        layout.setSpacing(10)

        info_label = QLabel(
            "Custom settings will override theme defaults.\n"
            "Changing themes will not affect your custom colors."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #888888; font-style: italic; font-size: 11px;")
        layout.addWidget(info_label)

        group.setLayout(layout)
        return group

    def _on_line_theme_toggled(self, checked: bool):
        """Handle line theme default checkbox toggle."""
        self.line_color_btn.setEnabled(not checked)
        if checked:
            # Show theme default color
            self.line_color = None
            theme_color = self.theme_manager.get_chart_line_color()
            self.line_color_preview.setStyleSheet(
                f"font-size: 24px; color: rgb({theme_color[0]}, "
                f"{theme_color[1]}, {theme_color[2]});"
            )

    def _on_bg_theme_toggled(self, checked: bool):
        """Handle background theme default checkbox toggle."""
        self.bg_color_btn.setEnabled(not checked)
        if checked:
            # Show theme default
            self.chart_background = None
            self.bg_color_preview.setStyleSheet("font-size: 24px; color: #888888;")

    def _choose_color(self, color_type: str):
        """Open color picker for a specific color type."""
        if color_type == "up":
            current_color = QColor(*self.candle_up_color)
            title = "Select Up Candle Color"
        elif color_type == "down":
            current_color = QColor(*self.candle_down_color)
            title = "Select Down Candle Color"
        elif color_type == "line":
            if self.line_color:
                current_color = QColor(*self.line_color)
            else:
                theme_color = self.theme_manager.get_chart_line_color()
                current_color = QColor(*theme_color)
            title = "Select Line Color"
        elif color_type == "background":
            if self.chart_background:
                current_color = QColor(*self.chart_background)
            else:
                current_color = QColor(30, 30, 30)  # Default dark
            title = "Select Background Color"
        else:
            return

        color = QColorDialog.getColor(current_color, self, title)
        
        if color.isValid():
            rgb = (color.red(), color.green(), color.blue())
            
            if color_type == "up":
                self.candle_up_color = rgb
                self.up_color_preview.setStyleSheet(
                    f"font-size: 24px; color: rgb({rgb[0]}, {rgb[1]}, {rgb[2]});"
                )
            elif color_type == "down":
                self.candle_down_color = rgb
                self.down_color_preview.setStyleSheet(
                    f"font-size: 24px; color: rgb({rgb[0]}, {rgb[1]}, {rgb[2]});"
                )
            elif color_type == "line":
                self.line_color = rgb
                self.line_color_preview.setStyleSheet(
                    f"font-size: 24px; color: rgb({rgb[0]}, {rgb[1]}, {rgb[2]});"
                )
            elif color_type == "background":
                self.chart_background = rgb
                self.bg_color_preview.setStyleSheet(
                    f"font-size: 24px; color: rgb({rgb[0]}, {rgb[1]}, {rgb[2]});"
                )

    def _load_current_settings(self):
        """Load current settings into the UI."""
        # Candle width
        self.candle_width_spin.setValue(
            self.current_settings.get("candle_width", 0.6)
        )
        
        # Line width
        self.line_width_spin.setValue(
            self.current_settings.get("line_width", 2)
        )
        
        # Line style
        line_style = self.current_settings.get("line_style", Qt.SolidLine)
        for style_name, style_value in self.LINE_STYLES.items():
            if style_value == line_style:
                index = self.line_style_combo.findText(style_name)
                if index >= 0:
                    self.line_style_combo.setCurrentIndex(index)
                break

    def _reset_to_defaults(self):
        """Reset all settings to defaults."""
        reply = QMessageBox.question(
            self,
            "Reset to Defaults",
            "Are you sure you want to reset all chart settings to defaults?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        
        if reply == QMessageBox.Yes:
            # Reset to defaults
            self.candle_up_color = (76, 153, 0)
            self.candle_down_color = (200, 50, 50)
            self.line_color = None
            self.chart_background = None
            
            # Update UI
            self.up_color_preview.setStyleSheet(
                f"font-size: 24px; color: rgb({self.candle_up_color[0]}, "
                f"{self.candle_up_color[1]}, {self.candle_up_color[2]});"
            )
            self.down_color_preview.setStyleSheet(
                f"font-size: 24px; color: rgb({self.candle_down_color[0]}, "
                f"{self.candle_down_color[1]}, {self.candle_down_color[2]});"
            )
            
            self.line_use_theme_check.setChecked(True)
            self.bg_use_theme_check.setChecked(True)
            
            self.candle_width_spin.setValue(0.6)
            self.line_width_spin.setValue(2)
            self.line_style_combo.setCurrentIndex(0)  # Solid

    def _save_settings(self):
        """Save the settings and close."""
        self.result = {
            "candle_up_color": self.candle_up_color,
            "candle_down_color": self.candle_down_color,
            "candle_width": self.candle_width_spin.value(),
            "line_color": self.line_color,
            "line_width": self.line_width_spin.value(),
            "line_style": self.LINE_STYLES[self.line_style_combo.currentText()],
            "chart_background": self.chart_background,
        }
        self.accept()

    def get_settings(self):
        """Get the configured settings."""
        return getattr(self, "result", None)

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
            #dialogHeader {
                color: #00d4ff;
                font-size: 18px;
                font-weight: bold;
                padding: 10px;
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
            QCheckBox {
                color: #cccccc;
                font-size: 13px;
                background-color: transparent;
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
            QComboBox QAbstractItemView {
                background-color: #2d2d2d;
                color: #ffffff;
                selection-background-color: #00d4ff;
                selection-color: #000000;
            }
            QSpinBox, QDoubleSpinBox {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 8px;
                font-size: 13px;
            }
            QSpinBox:hover, QDoubleSpinBox:hover {
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
            QCheckBox {
                color: #333333;
                font-size: 13px;
                background-color: transparent;
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
            QComboBox QAbstractItemView {
                background-color: #ffffff;
                color: #000000;
                selection-background-color: #0066cc;
                selection-color: #ffffff;
            }
            QSpinBox, QDoubleSpinBox {
                background-color: #f5f5f5;
                color: #000000;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 8px;
                font-size: 13px;
            }
            QSpinBox:hover, QDoubleSpinBox:hover {
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
            #dialogHeader {
                color: #FF8000;
                font-size: 18px;
                font-weight: bold;
                padding: 10px;
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
            QCheckBox {
                color: #b0b0b0;
                font-size: 13px;
                background-color: transparent;
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
            QComboBox QAbstractItemView {
                background-color: #0d1420;
                color: #e8e8e8;
                selection-background-color: #FF8000;
                selection-color: #000000;
            }
            QSpinBox, QDoubleSpinBox {
                background-color: transparent;
                color: #e8e8e8;
                border: 1px solid #1a2332;
                border-radius: 2px;
                padding: 8px;
                font-size: 13px;
            }
            QSpinBox:hover, QDoubleSpinBox:hover {
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