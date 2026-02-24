"""Asset Class Returns Tab Bar - Switches between Asset Class and Custom heatmaps."""

from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QButtonGroup
from PySide6.QtCore import Signal, Qt

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common.lazy_theme_mixin import LazyThemeMixin


class AssetClassReturnsTabBar(LazyThemeMixin, QWidget):
    """Horizontal tab bar: Asset Class Heatmap | Custom Heatmap."""

    view_changed = Signal(int)  # 0 = Asset Class, 1 = Custom

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._theme_dirty = False
        self._setup_ui()
        self._apply_theme()
        self.theme_manager.theme_changed.connect(self._on_theme_changed_lazy)

    def showEvent(self, event):
        super().showEvent(event)
        self._check_theme_dirty()

    def _setup_ui(self):
        self.setFixedHeight(52)
        self.setObjectName("viewTabBar")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(5)

        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)

        self.asset_class_tab = QPushButton("Asset Class Heatmap")
        self.asset_class_tab.setObjectName("viewTab")
        self.asset_class_tab.setCheckable(True)
        self.asset_class_tab.setCursor(Qt.PointingHandCursor)
        self.asset_class_tab.setMinimumWidth(190)
        self.asset_class_tab.setFixedHeight(40)
        self.asset_class_tab.setChecked(True)
        self.asset_class_tab.clicked.connect(lambda: self.view_changed.emit(0))
        layout.addWidget(self.asset_class_tab)
        self.button_group.addButton(self.asset_class_tab)

        self.custom_tab = QPushButton("Custom Heatmap")
        self.custom_tab.setObjectName("viewTab")
        self.custom_tab.setCheckable(True)
        self.custom_tab.setCursor(Qt.PointingHandCursor)
        self.custom_tab.setMinimumWidth(170)
        self.custom_tab.setFixedHeight(40)
        self.custom_tab.clicked.connect(lambda: self.view_changed.emit(1))
        layout.addWidget(self.custom_tab)
        self.button_group.addButton(self.custom_tab)

        layout.addStretch()

    def set_active_view(self, index: int):
        if index == 0:
            self.asset_class_tab.setChecked(True)
        else:
            self.custom_tab.setChecked(True)

    def _apply_theme(self):
        theme = self.theme_manager.current_theme
        if theme == "light":
            self.setStyleSheet(self._get_light_stylesheet())
        elif theme == "bloomberg":
            self.setStyleSheet(self._get_bloomberg_stylesheet())
        else:
            self.setStyleSheet(self._get_dark_stylesheet())

    def _get_dark_stylesheet(self) -> str:
        return """
            #viewTabBar {
                background-color: #1e1e1e;
                border-bottom: 1px solid #3d3d3d;
            }
            #viewTab {
                background-color: transparent;
                color: #cccccc;
                border: none;
                border-radius: 2px;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: 500;
            }
            #viewTab:hover {
                background-color: #2d2d2d;
                color: #ffffff;
            }
            #viewTab:checked {
                background-color: #00d4ff;
                color: #000000;
                font-weight: bold;
            }
        """

    def _get_light_stylesheet(self) -> str:
        return """
            #viewTabBar {
                background-color: #ffffff;
                border-bottom: 1px solid #cccccc;
            }
            #viewTab {
                background-color: transparent;
                color: #333333;
                border: none;
                border-radius: 2px;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: 500;
            }
            #viewTab:hover {
                background-color: #f0f0f0;
                color: #000000;
            }
            #viewTab:checked {
                background-color: #0066cc;
                color: #ffffff;
                font-weight: bold;
            }
        """

    def _get_bloomberg_stylesheet(self) -> str:
        return """
            #viewTabBar {
                background-color: #000814;
                border-bottom: 1px solid #1a2838;
            }
            #viewTab {
                background-color: transparent;
                color: #a8a8a8;
                border: none;
                border-radius: 2px;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: 500;
            }
            #viewTab:hover {
                background-color: #0d1420;
                color: #e8e8e8;
            }
            #viewTab:checked {
                background-color: #FF8000;
                color: #000000;
                font-weight: bold;
            }
        """
