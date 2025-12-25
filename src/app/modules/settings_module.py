from __future__ import annotations

from PySide6.QtWidgets import (
    QButtonGroup,
    QGroupBox,
    QLabel,
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt


class SettingsModule(QWidget):
    """Settings module with theme switching and other preferences."""

    def __init__(self, hub_window=None, parent=None):
        super().__init__(parent)
        self.hub_window = hub_window
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Create the settings UI."""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Scrollable area for settings
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(30)

        # Header
        header = QLabel("Settings")
        header.setStyleSheet("""
            QLabel {
                font-size: 32px;
                font-weight: bold;
                margin-bottom: 10px;
            }
        """)
        layout.addWidget(header)

        # Appearance settings
        appearance_group = self._create_appearance_group()
        layout.addWidget(appearance_group)

        # Future settings groups can go here
        # layout.addWidget(self._create_data_group())
        # layout.addWidget(self._create_api_group())

        layout.addStretch(1)

        scroll.setWidget(content)
        main_layout.addWidget(scroll)

    def _create_appearance_group(self) -> QGroupBox:
        """Create appearance settings group."""
        group = QGroupBox("Appearance")
        group.setStyleSheet("""
            QGroupBox {
                font-size: 18px;
                font-weight: bold;
                border: 2px solid #3d3d3d;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 20px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 5px;
            }
        """)

        layout = QVBoxLayout()
        layout.setSpacing(15)

        # Theme label
        theme_label = QLabel("Color Theme")
        theme_label.setStyleSheet("font-size: 14px; font-weight: normal; margin-left: 10px;")
        layout.addWidget(theme_label)

        # Radio buttons for theme selection
        self.theme_group = QButtonGroup(self)
        
        self.dark_radio = QRadioButton("Dark Mode")
        self.dark_radio.setChecked(True)  # Default to dark
        self.dark_radio.setStyleSheet("""
            QRadioButton {
                font-size: 13px;
                padding: 8px;
                margin-left: 20px;
            }
            QRadioButton::indicator {
                width: 18px;
                height: 18px;
            }
        """)
        self.theme_group.addButton(self.dark_radio, 0)
        layout.addWidget(self.dark_radio)

        self.light_radio = QRadioButton("Light Mode")
        self.light_radio.setStyleSheet("""
            QRadioButton {
                font-size: 13px;
                padding: 8px;
                margin-left: 20px;
            }
            QRadioButton::indicator {
                width: 18px;
                height: 18px;
            }
        """)
        self.theme_group.addButton(self.light_radio, 1)
        layout.addWidget(self.light_radio)

        # Connect theme change
        self.theme_group.buttonClicked.connect(self._on_theme_changed)

        group.setLayout(layout)
        return group

    def _on_theme_changed(self) -> None:
        """Handle theme change."""
        if self.hub_window is None:
            return

        theme = "dark" if self.dark_radio.isChecked() else "light"
        self.hub_window.set_theme(theme)