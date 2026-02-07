"""Analysis Controls Widget - Shared top control bar for analysis modules."""

from typing import List

from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
)
from PySide6.QtCore import Signal

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common import (
    LazyThemeMixin,
    NoScrollComboBox,
    PortfolioTickerComboBox,
)
from app.services.theme_stylesheet_service import ThemeStylesheetService


# Lookback options: label -> calendar days (None = max, -1 = custom)
LOOKBACK_OPTIONS = [
    ("1 Year", 365),
    ("2 Years", 730),
    ("5 Years", 1825),
    ("Max", None),
    ("Custom", -1),
]

# Simulation count options
SIMULATION_OPTIONS = [1000, 5000, 10000, 25000, 50000]


class AnalysisControls(LazyThemeMixin, QWidget):
    """Shared control bar for Efficient Frontier, Correlation, and Covariance modules.

    Signals:
        home_clicked: Home button pressed
        portfolio_loaded(list): Portfolio selected, emits list of tickers
        lookback_changed(int): Lookback period changed (calendar days, 0=max)
        simulations_changed(int): Simulation count changed (EF only)
        run_clicked: Run button pressed
    """

    home_clicked = Signal()
    portfolio_loaded = Signal(list)
    lookback_changed = Signal(int)
    simulations_changed = Signal(int)
    run_clicked = Signal()
    settings_clicked = Signal()

    def __init__(
        self,
        theme_manager: ThemeManager,
        show_simulations: bool = False,
        run_label: str = "Run",
        parent=None,
    ):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._theme_dirty = False
        self._show_simulations = show_simulations
        self._custom_date_range = None
        self._previous_lookback_index = 2  # Default: 5 Years

        self._setup_ui(run_label)
        self._apply_theme()
        self.theme_manager.theme_changed.connect(self._on_theme_changed_lazy)

    def showEvent(self, event):
        super().showEvent(event)
        self._check_theme_dirty()

    def _setup_ui(self, run_label: str):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Home button
        self.home_btn = QPushButton("Home")
        self.home_btn.setMinimumWidth(70)
        self.home_btn.setMaximumWidth(100)
        self.home_btn.setFixedHeight(40)
        self.home_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.home_btn.setObjectName("home_btn")
        self.home_btn.clicked.connect(self.home_clicked.emit)
        layout.addWidget(self.home_btn)

        layout.addStretch(1)

        # Portfolio combo (load tickers from portfolio)
        self.portfolio_label = QLabel("Load Portfolio:")
        self.portfolio_label.setObjectName("control_label")
        layout.addWidget(self.portfolio_label)
        self.portfolio_combo = PortfolioTickerComboBox()
        self.portfolio_combo.setMinimumWidth(140)
        self.portfolio_combo.setMaximumWidth(250)
        self.portfolio_combo.setFixedHeight(40)
        self.portfolio_combo.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.portfolio_combo.value_changed.connect(self._on_portfolio_selected)
        layout.addWidget(self.portfolio_combo)

        layout.addSpacing(10)

        # Lookback selector
        self.lookback_label = QLabel("Lookback:")
        self.lookback_label.setObjectName("control_label")
        layout.addWidget(self.lookback_label)
        self.lookback_combo = NoScrollComboBox()
        self.lookback_combo.setMinimumWidth(85)
        self.lookback_combo.setMaximumWidth(120)
        self.lookback_combo.setFixedHeight(40)
        self.lookback_combo.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        for label, days in LOOKBACK_OPTIONS:
            self.lookback_combo.addItem(label, days)
        self.lookback_combo.setCurrentIndex(2)  # Default: 5 Years
        self.lookback_combo.currentIndexChanged.connect(self._on_lookback_changed)
        layout.addWidget(self.lookback_combo)

        # Simulations selector (EF only)
        if self._show_simulations:
            layout.addSpacing(8)

            self.sims_label = QLabel("Simulations:")
            self.sims_label.setObjectName("control_label")
            layout.addWidget(self.sims_label)
            self.sims_combo = NoScrollComboBox()
            self.sims_combo.setMinimumWidth(80)
            self.sims_combo.setMaximumWidth(110)
            self.sims_combo.setFixedHeight(40)
            self.sims_combo.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            for count in SIMULATION_OPTIONS:
                self.sims_combo.addItem(f"{count:,}", count)
            self.sims_combo.setCurrentIndex(2)  # Default: 10,000
            self.sims_combo.currentIndexChanged.connect(self._on_sims_changed)
            layout.addWidget(self.sims_combo)

        layout.addSpacing(8)

        # Run button
        self.run_btn = QPushButton(run_label)
        self.run_btn.setMinimumWidth(80)
        self.run_btn.setMaximumWidth(140)
        self.run_btn.setFixedHeight(40)
        self.run_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.run_btn.setObjectName("run_btn")
        self.run_btn.clicked.connect(self.run_clicked.emit)
        layout.addWidget(self.run_btn)

        layout.addStretch(1)

        # Settings button (right-aligned, mirrors Home on the left)
        self.settings_btn = QPushButton("Settings")
        self.settings_btn.setMinimumWidth(70)
        self.settings_btn.setMaximumWidth(100)
        self.settings_btn.setFixedHeight(40)
        self.settings_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.settings_btn.clicked.connect(self.settings_clicked.emit)
        layout.addWidget(self.settings_btn)

    def _on_portfolio_selected(self, value: str):
        """Handle portfolio selection - load tickers from portfolio."""
        if not value:
            return
        if value.startswith("[Port] "):
            portfolio_name = value[7:]
            try:
                from app.services.portfolio_data_service import PortfolioDataService
                data = PortfolioDataService.get_portfolio(portfolio_name)
                if data and data.tickers:
                    self.portfolio_loaded.emit(data.tickers)
            except Exception:
                pass

    def _on_lookback_changed(self, index: int):
        data = self.lookback_combo.currentData()

        if data == -1:
            # Custom: open date range dialog
            from .custom_date_dialog import CustomDateDialog

            dialog = CustomDateDialog(self.theme_manager, parent=self.window())
            if dialog.exec():
                self._custom_date_range = dialog.get_date_range()
                self._previous_lookback_index = index
                self.lookback_changed.emit(-1)
            else:
                # Cancelled: revert to previous selection
                self.lookback_combo.blockSignals(True)
                self.lookback_combo.setCurrentIndex(self._previous_lookback_index)
                self.lookback_combo.blockSignals(False)
            return

        # Preset selected: clear custom range
        self._custom_date_range = None
        self._previous_lookback_index = index
        # Emit 0 for Max (None)
        self.lookback_changed.emit(data if data is not None else 0)

    def _on_sims_changed(self, index: int):
        count = self.sims_combo.currentData()
        if count:
            self.simulations_changed.emit(count)

    def set_portfolio_list(self, portfolios: List[str]):
        """Set available portfolios in the dropdown."""
        self.portfolio_combo.set_portfolios(portfolios)

    def set_lookback(self, days: int):
        """Set the lookback combo to match the given days value."""
        for i in range(self.lookback_combo.count()):
            data = self.lookback_combo.itemData(i)
            if data == days or (days == 0 and data is None):
                self.lookback_combo.setCurrentIndex(i)
                return

    def set_simulations(self, count: int):
        """Set the simulations combo to match the given count."""
        if not self._show_simulations:
            return
        for i in range(self.sims_combo.count()):
            if self.sims_combo.itemData(i) == count:
                self.sims_combo.setCurrentIndex(i)
                return

    @property
    def custom_date_range(self):
        """Return (start_iso, end_iso) tuple or None."""
        return self._custom_date_range

    def _apply_theme(self):
        c = ThemeStylesheetService.get_colors(self.theme_manager.current_theme)

        if self.theme_manager.current_theme == "dark":
            bg_hover = "#3d3d3d"
            run_hover = "#00bfe6"
            run_pressed = "#00a6c7"
        elif self.theme_manager.current_theme == "light":
            bg_hover = "#e8e8e8"
            run_hover = "#0055aa"
            run_pressed = "#004488"
        else:  # bloomberg
            bg_hover = "#1a2838"
            run_hover = "#e67300"
            run_pressed = "#cc6600"

        self.setStyleSheet(f"""
            QWidget {{
                background-color: {c['bg']};
                color: {c['text']};
            }}
            QLabel#control_label {{
                color: {c['text']};
                font-size: 14px;
                font-weight: 500;
                background: transparent;
            }}
            QComboBox {{
                background-color: {c['bg_header']};
                color: {c['text']};
                border: 1px solid {c['border']};
                border-radius: 3px;
                padding: 8px 12px;
                font-size: 14px;
            }}
            QComboBox:hover {{
                border-color: {c['accent']};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 24px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 6px solid transparent;
                border-right: 6px solid transparent;
                border-top: 7px solid {c['text']};
                margin-right: 10px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {c['bg_header']};
                color: {c['text']};
                selection-background-color: {c['accent']};
                selection-color: {c['text_on_accent']};
                font-size: 14px;
                padding: 4px;
                outline: none;
            }}
            QComboBox QAbstractItemView::item {{
                padding: 8px 12px;
                min-height: 24px;
            }}
            QComboBox QAbstractItemView::item:selected {{
                background-color: {c['accent']};
                color: {c['text_on_accent']};
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
                background-color: {c['bg']};
            }}
            QPushButton#run_btn {{
                background-color: {c['accent']};
                color: {c['text_on_accent']};
                font-weight: bold;
                border: 1px solid {c['accent']};
            }}
            QPushButton#run_btn:hover {{
                background-color: {run_hover};
                border-color: {run_hover};
            }}
            QPushButton#run_btn:pressed {{
                background-color: {run_pressed};
            }}
        """)
