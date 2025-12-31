"""Theme Stylesheet Service - Centralized widget stylesheets by theme."""

from typing import Dict


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
                padding: 0px;
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
                background-color: {c['accent']};
                color: {c['text_on_accent']};
                border: none;
                margin: 0px;
                padding: 0px 8px;
                font-size: 14px;
            }}
            QLineEdit:focus {{
                background-color: {c['accent_hover']};
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
                background-color: {c['accent']};
                color: {c['text_on_accent']};
                border: none;
                padding: 4px 8px;
                font-size: 14px;
            }}
            QComboBox::drop-down {{ border: none; width: 0px; }}
            QComboBox:focus {{ background-color: {c['accent_hover']}; }}
            QComboBox QAbstractItemView {{
                background-color: {c['accent']};
                color: {c['text_on_accent']};
                selection-background-color: {c['accent_selection']};
            }}
        """
