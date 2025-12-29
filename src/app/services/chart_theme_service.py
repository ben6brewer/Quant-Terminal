"""Chart Theme Service - Centralized chart-related theme stylesheets."""


class ChartThemeService:
    """Service providing chart-related theme stylesheets."""

    @staticmethod
    def get_indicator_panel_stylesheet(theme: str) -> str:
        """Get stylesheet for indicator panel based on theme.

        Args:
            theme: Theme name ('dark', 'light', or 'bloomberg')

        Returns:
            CSS stylesheet string for the indicator panel
        """
        if theme == "dark":
            return ChartThemeService._get_dark_indicator_panel_stylesheet()
        elif theme == "light":
            return ChartThemeService._get_light_indicator_panel_stylesheet()
        elif theme == "bloomberg":
            return ChartThemeService._get_bloomberg_indicator_panel_stylesheet()
        else:
            return ChartThemeService._get_dark_indicator_panel_stylesheet()

    @staticmethod
    def _get_dark_indicator_panel_stylesheet() -> str:
        """Get dark theme stylesheet for indicator panel."""
        return """
            #indicatorPanel {
                background-color: #2d2d2d;
                border-left: 2px solid #3d3d3d;
            }
            QLabel {
                color: #cccccc;
                background-color: transparent;
            }
            QListWidget {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 2px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 5px;
            }
            QListWidget::item:selected {
                background-color: #00d4ff;
                color: #000000;
            }
            QPushButton {
                background-color: transparent;
                color: #ffffff;
                border: 1px solid transparent;
                border-radius: 2px;
                padding: 8px 14px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: rgba(0, 212, 255, 0.15);
                border: 1px solid #00d4ff;
            }
            QPushButton:pressed {
                background-color: #00d4ff;
                color: #000000;
                border: 1px solid #00d4ff;
            }
            QPushButton:checked {
                background-color: #00d4ff;
                color: #000000;
                border: 1px solid #00d4ff;
            }
            QPushButton:disabled {
                opacity: 0.4;
            }
            QPushButton#createButton {
                background-color: #00d4ff;
                color: #000000;
                border: none;
                border-radius: 2px;
                padding: 10px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton#createButton:hover {
                background-color: #00c4ef;
            }
            QPushButton#createButton:pressed {
                background-color: #00b4df;
            }
        """

    @staticmethod
    def _get_light_indicator_panel_stylesheet() -> str:
        """Get light theme stylesheet for indicator panel."""
        return """
            #indicatorPanel {
                background-color: #f5f5f5;
                border-left: 2px solid #d0d0d0;
            }
            QLabel {
                color: #333333;
                background-color: transparent;
            }
            QListWidget {
                background-color: #ffffff;
                color: #000000;
                border: 1px solid #d0d0d0;
                border-radius: 2px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 5px;
            }
            QListWidget::item:selected {
                background-color: #0066cc;
                color: #ffffff;
            }
            QPushButton {
                background-color: transparent;
                color: #000000;
                border: 1px solid transparent;
                border-radius: 2px;
                padding: 8px 14px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: rgba(0, 102, 204, 0.15);
                border: 1px solid #0066cc;
            }
            QPushButton:pressed {
                background-color: #0066cc;
                color: #ffffff;
                border: 1px solid #0066cc;
            }
            QPushButton:checked {
                background-color: #0066cc;
                color: #ffffff;
                border: 1px solid #0066cc;
            }
            QPushButton:disabled {
                opacity: 0.4;
            }
            QPushButton#createButton {
                background-color: #0066cc;
                color: #ffffff;
                border: none;
                border-radius: 2px;
                padding: 10px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton#createButton:hover {
                background-color: #0052a3;
            }
            QPushButton#createButton:pressed {
                background-color: #003d7a;
            }
        """

    @staticmethod
    def _get_bloomberg_indicator_panel_stylesheet() -> str:
        """Get Bloomberg theme stylesheet for indicator panel."""
        return """
            #indicatorPanel {
                background-color: #0d1420;
                border-left: 2px solid #1a2332;
            }
            QLabel {
                color: #b0b0b0;
                background-color: transparent;
            }
            QListWidget {
                background-color: #0a1018;
                color: #e8e8e8;
                border: 1px solid #1a2332;
                border-radius: 2px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 5px;
            }
            QListWidget::item:selected {
                background-color: #FF8000;
                color: #000000;
            }
            QPushButton {
                background-color: transparent;
                color: #e8e8e8;
                border: 1px solid transparent;
                border-radius: 2px;
                padding: 8px 14px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: rgba(255, 128, 0, 0.15);
                border: 1px solid #FF8000;
            }
            QPushButton:pressed {
                background-color: #FF8000;
                color: #000000;
                border: 1px solid #FF8000;
            }
            QPushButton:checked {
                background-color: #FF8000;
                color: #000000;
                border: 1px solid #FF8000;
            }
            QPushButton:disabled {
                opacity: 0.4;
            }
            QPushButton#createButton {
                background-color: #FF8000;
                color: #000000;
                border: none;
                border-radius: 2px;
                padding: 10px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton#createButton:hover {
                background-color: #FF9520;
            }
            QPushButton#createButton:pressed {
                background-color: #E67300;
            }
        """
