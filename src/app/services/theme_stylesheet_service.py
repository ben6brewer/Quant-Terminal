"""Theme Stylesheet Service - Centralized widget stylesheets by theme."""

from typing import Dict, Tuple


class ThemeStylesheetService:
    """
    Provides theme-aware stylesheets for common widget types.

    Centralizes theme colors and stylesheet generation to avoid duplication
    across modules. All colors are defined in COLORS dict for easy maintenance.
    """

    # Theme color constants
    COLORS: Dict[str, Dict[str, str]] = {
        "dark": {
            "accent": "#00d4ff",
            "accent_hover": "#00e5ff",
            "accent_selection": "#40e0ff",
            "bg": "#1e1e1e",
            "bg_alt": "#232323",
            "bg_header": "#2d2d2d",
            "border": "#3d3d3d",
            "text": "#ffffff",
            "text_muted": "#cccccc",
            "text_on_accent": "#000000",
        },
        "light": {
            "accent": "#0066cc",
            "accent_hover": "#0077dd",
            "accent_selection": "#0088ee",
            "bg": "#ffffff",
            "bg_alt": "#f5f5f5",
            "bg_header": "#f5f5f5",
            "border": "#cccccc",
            "text": "#000000",
            "text_muted": "#333333",
            "text_on_accent": "#ffffff",
        },
        "bloomberg": {
            "accent": "#FF8000",
            "accent_hover": "#FF9020",
            "accent_selection": "#FFa040",
            "bg": "#000814",
            "bg_alt": "#0a0f1c",
            "bg_header": "#0d1420",
            "border": "#1a2838",
            "text": "#e8e8e8",
            "text_muted": "#a8a8a8",
            "text_on_accent": "#000000",
        }
    }

    @classmethod
    def get_colors(cls, theme: str) -> Dict[str, str]:
        """Get color palette for a theme."""
        return cls.COLORS.get(theme, cls.COLORS["dark"])

    @classmethod
    def get_table_stylesheet(cls, theme: str) -> str:
        """Get QTableWidget stylesheet for a theme."""
        c = cls.get_colors(theme)
        return f"""
            QTableWidget {{
                background-color: {c['bg']};
                alternate-background-color: {c['bg_alt']};
                color: {c['text']};
                gridline-color: {c['border']};
                border: 1px solid {c['border']};
                font-size: 14px;
            }}
            QTableWidget::item {{
                padding: 4px 8px;
            }}
            QTableWidget::item:selected {{
                background-color: {c['accent']};
                color: {c['text_on_accent']};
            }}
            QHeaderView::section {{
                background-color: {c['bg_header']};
                color: {c['text_muted']};
                padding: 8px;
                border: 1px solid {c['border']};
                font-weight: bold;
                font-size: 14px;
            }}
            QTableCornerButton::section {{
                background-color: {c['bg_header']};
                color: {c['text_muted']};
                border: 1px solid {c['border']};
                font-weight: bold;
                font-size: 13px;
                padding: 8px;
            }}
        """

    @classmethod
    def get_line_edit_stylesheet(cls, theme: str, highlighted: bool = True) -> str:
        """Get QLineEdit stylesheet for editable cells.

        Args:
            theme: Theme name ('dark', 'light', 'bloomberg')
            highlighted: If True, use accent color background. If False, transparent.
        """
        c = cls.get_colors(theme)

        if not highlighted:
            return f"""
                QLineEdit {{
                    background-color: transparent;
                    color: {c['text']};
                    border: none;
                    margin: 0px;
                    padding: 0px 8px;
                    font-size: 14px;
                }}
            """

        return f"""
            QLineEdit {{
                background-color: transparent;
                color: {c['text_on_accent']};
                border: none;
                margin: 0px;
                padding: 0px 4px;
                font-size: 14px;
            }}
            QLineEdit:focus {{
                background-color: transparent;
            }}
        """

    @classmethod
    def get_combobox_stylesheet(cls, theme: str, highlighted: bool = True) -> str:
        """Get QComboBox stylesheet for editable cells.

        Args:
            theme: Theme name ('dark', 'light', 'bloomberg')
            highlighted: If True, use accent color background. If False, transparent.
        """
        c = cls.get_colors(theme)

        if not highlighted:
            return f"""
                QComboBox {{
                    background-color: transparent;
                    color: {c['text']};
                    border: none;
                    padding: 4px 8px;
                    font-size: 14px;
                }}
                QComboBox::drop-down {{ border: none; width: 0px; }}
                QComboBox QAbstractItemView {{
                    background-color: {c['bg_header']};
                    color: {c['text']};
                    selection-background-color: {c['accent']};
                }}
            """

        return f"""
            QComboBox {{
                background-color: transparent;
                color: {c['text_on_accent']};
                border: none;
                padding: 4px 4px;
                font-size: 14px;
            }}
            QComboBox::drop-down {{ border: none; width: 0px; }}
            QComboBox:focus {{ background-color: transparent; }}
            QComboBox QAbstractItemView {{
                background-color: {c['accent']};
                color: {c['text_on_accent']};
                selection-background-color: {c['accent_selection']};
            }}
        """

    @classmethod
    def get_dialog_stylesheet(cls, theme: str) -> str:
        """Get QDialog stylesheet for themed dialogs.

        Includes styling for:
        - Dialog background and title bar
        - Labels (regular and description)
        - Line edits
        - Buttons (regular and title bar close)
        - List widgets
        - Combo boxes
        - Radio buttons and checkboxes
        """
        c = cls.get_colors(theme)

        # Additional colors for dialogs
        bg_pressed = "#1a1a1a" if theme == "dark" else "#d0d0d0" if theme == "light" else "#060a10"
        bg_hover = "#3d3d3d" if theme == "dark" else "#e8e8e8" if theme == "light" else "#1a2838"
        text_desc = "#888888" if theme == "dark" else "#666666" if theme == "light" else "#666666"
        text_disabled = "#666666" if theme == "dark" else "#999999" if theme == "light" else "#555555"

        return f"""
            QDialog {{
                background-color: {c['bg']};
                color: {c['text']};
            }}
            QWidget#titleBar {{
                background-color: {c['bg_header']};
            }}
            QLabel#titleLabel {{
                color: {c['text']};
                font-size: 14px;
                font-weight: bold;
                background-color: transparent;
            }}
            QPushButton#titleBarCloseButton {{
                background-color: transparent;
                color: {c['text']};
                border: none;
                font-size: 16px;
            }}
            QPushButton#titleBarCloseButton:hover {{
                background-color: #d32f2f;
                color: #ffffff;
            }}
            QLabel {{
                color: {c['text_muted']};
                font-size: 13px;
                background-color: transparent;
            }}
            QLabel#descriptionLabel {{
                color: {text_desc};
                font-size: 12px;
                background-color: transparent;
            }}
            QLineEdit {{
                background-color: {c['bg_header']};
                color: {c['text']};
                border: 1px solid {c['border']};
                border-radius: 3px;
                padding: 5px;
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border-color: {c['accent']};
            }}
            QListWidget {{
                background-color: {c['bg_header']};
                color: {c['text']};
                border: 1px solid {c['border']};
                border-radius: 3px;
                font-size: 13px;
            }}
            QListWidget::item:selected {{
                background-color: {c['accent']};
                color: {c['text_on_accent']};
            }}
            QListWidget::item:hover {{
                background-color: {bg_hover};
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
                padding: 4px;
            }}
            QRadioButton {{
                color: {c['text']};
                font-size: 13px;
                spacing: 8px;
                background-color: transparent;
            }}
            QRadioButton::indicator {{
                width: 16px;
                height: 16px;
                border-radius: 8px;
                border: 2px solid {c['border']};
                background-color: {c['bg_header']};
            }}
            QRadioButton::indicator:checked {{
                border-color: {c['accent']};
                background-color: {c['accent']};
            }}
            QRadioButton::indicator:hover {{
                border-color: {c['accent']};
            }}
            QCheckBox {{
                color: {c['text']};
                font-size: 13px;
                spacing: 8px;
                background-color: transparent;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border-radius: 3px;
                border: 2px solid {c['border']};
                background-color: {c['bg_header']};
            }}
            QCheckBox::indicator:checked {{
                border-color: {c['accent']};
                background-color: {c['accent']};
            }}
            QCheckBox::indicator:hover {{
                border-color: {c['accent']};
            }}
            QCheckBox:disabled {{
                color: {text_disabled};
            }}
            QCheckBox::indicator:disabled {{
                border-color: {c['bg_header']};
                background-color: {bg_pressed};
            }}
            QPushButton {{
                background-color: {c['bg_header']};
                color: {c['text']};
                border: 1px solid {c['border']};
                border-radius: 3px;
                padding: 6px 12px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {bg_hover};
                border-color: {c['accent']};
            }}
            QPushButton:pressed {{
                background-color: {bg_pressed};
            }}
            QPushButton#defaultButton {{
                background-color: {c['accent']};
                color: {c['text_on_accent']};
                border: 1px solid {c['accent']};
                font-weight: 600;
            }}
            QPushButton#defaultButton:hover {{
                background-color: {c['accent_hover']};
                border-color: {c['accent_hover']};
            }}
            QPushButton#defaultButton:pressed {{
                background-color: {c['accent']};
            }}
            QLabel#noteLabel {{
                color: {text_desc};
                font-style: italic;
                font-size: 11px;
                background-color: transparent;
            }}
            QGroupBox {{
                color: {c['text']};
                background-color: {c['bg']};
                border: 2px solid {c['border']};
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 20px;
                font-size: 14px;
                font-weight: bold;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 5px;
                background-color: {c['bg']};
            }}
            QSpinBox {{
                background-color: {c['bg_header']};
                color: {c['text']};
                border: 1px solid {c['border']};
                border-radius: 3px;
                padding: 5px 8px;
                font-size: 13px;
            }}
            QSpinBox:hover {{
                border-color: {c['accent']};
            }}
            QSpinBox:focus {{
                border-color: {c['accent']};
            }}
            QScrollArea {{
                border: none;
                background-color: {c['bg']};
            }}
            QScrollBar:vertical {{
                background-color: {c['bg']};
                width: 12px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {bg_hover};
                border-radius: 6px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: {c['border']};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar:horizontal {{
                background-color: {c['bg']};
                height: 12px;
                margin: 0px;
            }}
            QScrollBar::handle:horizontal {{
                background-color: {bg_hover};
                border-radius: 6px;
                min-width: 20px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background-color: {c['border']};
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0px;
            }}
        """

    # ------------------------------------------------------------------
    # Layout stylesheet color palettes (preserves exact ThemeManager values)
    # ------------------------------------------------------------------

    _SIDEBAR = {
        "dark": {
            "bg": "#2d2d2d", "text": "#ffffff", "header_bg": "#1a1a1a",
            "accent": "#00d4ff", "footer": "#666666", "nav_text": "#cccccc",
            "hover_bg": "#3d3d3d", "hover_text": "#ffffff",
            "text_on_accent": "#000000",
        },
        "light": {
            "bg": "#f5f5f5", "text": "#000000", "header_bg": "#e0e0e0",
            "accent": "#0066cc", "footer": "#999999", "nav_text": "#333333",
            "hover_bg": "#e8e8e8", "hover_text": "#000000",
            "text_on_accent": "#ffffff",
        },
        "bloomberg": {
            "bg": "#0d1420", "text": "#e8e8e8", "header_bg": "#000814",
            "accent": "#FF8000", "footer": "#666666", "nav_text": "#b0b0b0",
            "hover_bg": "#162030", "hover_text": "#e8e8e8",
            "text_on_accent": "#000000",
        },
    }

    _CONTENT = {
        "dark": {
            "bg": "#1e1e1e", "text": "#ffffff", "text_muted": "#cccccc",
            "groupbox_bg": "#2d2d2d", "groupbox_extra": "",
        },
        "light": {
            "bg": "#ffffff", "text": "#000000", "text_muted": "#333333",
            "groupbox_bg": "#f5f5f5", "groupbox_extra": "border: 2px solid #d0d0d0;",
        },
        "bloomberg": {
            "bg": "#000814", "text": "#e8e8e8", "text_muted": "#b0b0b0",
            "groupbox_bg": "#0a1018",
            "groupbox_extra": 'border: 1px solid #1a2332; font-family: "Segoe UI", "Arial", sans-serif;',
        },
    }

    _CONTROLS = {
        "dark": {
            "bg": "#2d2d2d", "accent": "#00d4ff", "label_color": "#b0b0b0",
            "label_size": "12px", "input_bg": "#1e1e1e", "input_text": "#ffffff",
            "input_border": "#3d3d3d", "input_padding": "7px 10px", "input_font": "",
            "selection_color": "#000000", "hover_bg": "#252525", "focus_bg": "#252525",
            "arrow_color": "#cccccc", "dropdown_bg": "#2d2d2d", "dropdown_text": "#ffffff",
        },
        "light": {
            "bg": "#f5f5f5", "accent": "#0066cc", "label_color": "#555555",
            "label_size": "12px", "input_bg": "#ffffff", "input_text": "#000000",
            "input_border": "#cccccc", "input_padding": "7px 10px", "input_font": "",
            "selection_color": "#ffffff", "hover_bg": "#f9f9f9", "focus_bg": "#ffffff",
            "arrow_color": "#555555", "dropdown_bg": "#ffffff", "dropdown_text": "#000000",
        },
        "bloomberg": {
            "bg": "#0d1420", "accent": "#FF8000", "label_color": "#b0b0b0",
            "label_size": "11px", "input_bg": "#0a1018", "input_text": "#e8e8e8",
            "input_border": "#1a2332", "input_padding": "6px 10px",
            "input_font": 'font-family: "Menlo", "Consolas", "Courier New", monospace;',
            "selection_color": "#000000", "hover_bg": "#0d1420", "focus_bg": "#0d1420",
            "arrow_color": "#b0b0b0", "dropdown_bg": "#0d1420", "dropdown_text": "#e8e8e8",
        },
    }

    _BUTTON = {
        "dark": {
            "text": "#ffffff", "accent": "#00d4ff",
            "accent_rgba": "rgba(0, 212, 255, 0.15)",
            "text_on_accent": "#000000",
        },
        "light": {
            "text": "#000000", "accent": "#0066cc",
            "accent_rgba": "rgba(0, 102, 204, 0.15)",
            "text_on_accent": "#ffffff",
        },
        "bloomberg": {
            "text": "#e8e8e8", "accent": "#FF8000",
            "accent_rgba": "rgba(255, 128, 0, 0.15)",
            "text_on_accent": "#000000",
        },
    }

    # ------------------------------------------------------------------
    # Layout stylesheets
    # ------------------------------------------------------------------

    @classmethod
    def get_sidebar_stylesheet(cls, theme: str) -> str:
        """Get sidebar stylesheet for a theme."""
        s = cls._SIDEBAR.get(theme, cls._SIDEBAR["dark"])
        mono = 'font-family: "Menlo", "Consolas", "Courier New", monospace;' if theme == "bloomberg" else ""
        hover_border = f"border-left: 3px solid {s['accent']};" if theme == "bloomberg" else ""
        return f"""
            #sidebar {{ background-color: {s['bg']}; color: {s['text']}; }}
            #sidebarHeader {{
                background-color: {s['header_bg']}; color: {s['accent']};
                font-size: 14px; font-weight: bold; {mono}
                padding: 20px 10px; border-bottom: 2px solid {s['accent']};
            }}
            #sidebarFooter {{ color: {s['footer']}; font-size: 10px; {mono} padding: 10px; }}
            #navButton {{
                text-align: left; padding: 15px 20px; border: none;
                background-color: transparent; color: {s['nav_text']};
                font-size: 13px; font-weight: 500;
            }}
            #navButton:hover {{
                background-color: {s['hover_bg']}; color: {s['hover_text']}; {hover_border}
            }}
            #navButton:checked {{
                background-color: {s['accent']}; color: {s['text_on_accent']};
                font-weight: bold;
            }}
        """

    @classmethod
    def get_content_stylesheet(cls, theme: str) -> str:
        """Get content area stylesheet for a theme."""
        s = cls._CONTENT.get(theme, cls._CONTENT["dark"])
        return f"""
            QStackedWidget {{ background-color: {s['bg']}; }}
            QScrollArea {{ background-color: {s['bg']}; border: none; }}
            QGroupBox {{ color: {s['text']}; background-color: {s['groupbox_bg']}; {s['groupbox_extra']} }}
            QLabel {{ color: {s['text_muted']}; }}
            QRadioButton {{ color: {s['text_muted']}; }}
            QWidget {{ background-color: {s['bg']}; color: {s['text']}; }}
        """

    @classmethod
    def get_controls_stylesheet(cls, theme: str) -> str:
        """Get chart controls bar stylesheet for a theme."""
        s = cls._CONTROLS.get(theme, cls._CONTROLS["dark"])
        return f"""
            QWidget {{
                background-color: {s['bg']};
                border-bottom: 2px solid {s['accent']};
            }}
            QLabel {{
                color: {s['label_color']};
                font-size: {s['label_size']};
                font-weight: bold;
                font-family: "Segoe UI", "Arial", sans-serif;
                letter-spacing: 0.5px;
                padding: 0px 5px;
            }}
            QLineEdit {{
                background-color: {s['input_bg']};
                color: {s['input_text']};
                border: 1px solid {s['input_border']};
                border-radius: 2px;
                padding: {s['input_padding']};
                font-size: 13px;
                font-weight: 600;
                {s['input_font']}
                selection-background-color: {s['accent']};
                selection-color: {s['selection_color']};
            }}
            QLineEdit:hover {{
                border: 1px solid {s['accent']};
                background-color: {s['hover_bg']};
            }}
            QLineEdit:focus {{
                border: 1px solid {s['accent']};
                background-color: {s['focus_bg']};
            }}
            QComboBox {{
                background-color: {s['input_bg']};
                color: {s['input_text']};
                border: 1px solid {s['input_border']};
                border-radius: 2px;
                padding: {s['input_padding']};
                font-size: 13px;
                font-weight: 500;
            }}
            QComboBox:hover {{
                border: 1px solid {s['accent']};
                background-color: {s['hover_bg']};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid {s['arrow_color']};
                margin-right: 5px;
            }}
            QComboBox::down-arrow:hover {{
                border-top-color: {s['accent']};
            }}
            QComboBox QAbstractItemView {{
                background-color: {s['dropdown_bg']};
                color: {s['dropdown_text']};
                selection-background-color: {s['accent']};
                selection-color: {s['selection_color']};
                border: 1px solid {s['accent']};
            }}
        """

    @classmethod
    def get_home_button_stylesheet(cls, theme: str) -> str:
        """Get home/settings button stylesheet for a theme."""
        s = cls._BUTTON.get(theme, cls._BUTTON["dark"])
        font = 'font-family: "Segoe UI", "Arial", sans-serif;' if theme == "bloomberg" else ""
        return f"""
            #homeButton, #chartSettingsButton, #settingsButton {{
                background-color: transparent;
                color: {s['text']};
                border: 1px solid transparent;
                border-radius: 2px;
                font-size: 13px;
                font-weight: bold;
                {font}
            }}
            #settingsButton {{
                margin: 5px 10px;
            }}
            #homeButton:hover, #chartSettingsButton:hover, #settingsButton:hover {{
                background-color: {s['accent_rgba']};
                border: 1px solid {s['accent']};
            }}
            #homeButton:pressed, #chartSettingsButton:pressed, #settingsButton:pressed {{
                background-color: {s['accent']};
                color: {s['text_on_accent']};
                border: 1px solid {s['accent']};
            }}
        """

    @classmethod
    def get_button_stylesheet(cls, theme: str) -> str:
        """Get universal QPushButton stylesheet for a theme."""
        s = cls._BUTTON.get(theme, cls._BUTTON["dark"])
        return f"""
            QPushButton {{
                background-color: transparent;
                color: {s['text']};
                border: 1px solid transparent;
                border-radius: 2px;
                padding: 8px 14px;
                font-weight: 600;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {s['accent_rgba']};
                border: 1px solid {s['accent']};
            }}
            QPushButton:pressed {{
                background-color: {s['accent']};
                color: {s['text_on_accent']};
                border: 1px solid {s['accent']};
            }}
            QPushButton:checked {{
                background-color: {s['accent']};
                color: {s['text_on_accent']};
                border: 1px solid {s['accent']};
            }}
            QPushButton:disabled {{
                opacity: 0.4;
            }}
        """

    @classmethod
    def get_chart_background_color(cls, theme: str) -> str:
        """Get chart background color for a theme."""
        return {"light": "w", "bloomberg": "#000814"}.get(theme, "#1e1e1e")

    @classmethod
    def get_chart_line_color(cls, theme: str) -> Tuple[int, int, int]:
        """Get chart line color RGB tuple for a theme."""
        return {
            "light": (0, 0, 0),
            "bloomberg": (0, 212, 255),
        }.get(theme, (76, 175, 80))
