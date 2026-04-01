"""Monthly Returns Module - Year×month heatmap of returns."""

from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QWidget

from app.core.config import DEFAULT_TICKER
from app.core.theme_manager import ThemeManager
from app.services.portfolio_data_service import PortfolioDataService
from app.ui.widgets.common import parse_portfolio_value, CustomMessageBox
from app.ui.modules.base_module import BaseModule

from .services.monthly_returns_service import MonthlyReturnsService
from .widgets.monthly_returns_toolbar import MonthlyReturnsToolbar
from .widgets.monthly_returns_table import MonthlyReturnsTable
from .widgets.monthly_returns_settings_dialog import MonthlyReturnsSettingsDialog


class MonthlyReturnsModule(BaseModule):
    """Displays a year×month heatmap of returns for any ticker or portfolio."""

    SETTINGS_FILENAME = "monthly_returns_settings.json"
    DEFAULT_SETTINGS = {
        "show_ytd": True,
        "use_gradient": True,
        "decimals": 2,
        "colorscale": "Red-Green",
    }

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(theme_manager, parent)

        self._current_portfolio: str = ""
        self._is_ticker_mode: bool = False
        self._portfolio_list: list = []

        self._setup_ui()
        self._connect_signals()
        self._apply_theme()
        self._refresh_portfolio_list()

        # Pre-populate with default ticker
        self._current_portfolio = DEFAULT_TICKER
        self._is_ticker_mode = True
        self.controls.set_ticker_text(DEFAULT_TICKER)
        self._update_heatmap()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Controls bar
        self.controls = MonthlyReturnsToolbar(self.theme_manager)
        layout.addWidget(self.controls)

        # Container with padding around the table
        self.table_container = QWidget()
        table_layout = QHBoxLayout(self.table_container)
        table_layout.setContentsMargins(20, 10, 20, 10)

        self.table = MonthlyReturnsTable(self.theme_manager)
        table_layout.addWidget(self.table)

        layout.addWidget(self.table_container, stretch=1)

    def _connect_signals(self):
        self.controls.home_clicked.connect(self.home_clicked.emit)
        self.controls.portfolio_changed.connect(self._on_portfolio_changed)
        self.controls.settings_clicked.connect(self._on_settings_clicked)
        self.controls.info_clicked.connect(self._on_info_clicked)
        self.theme_manager.theme_changed.connect(self._on_theme_changed_lazy)

    def _refresh_portfolio_list(self):
        self._portfolio_list = PortfolioDataService.list_portfolios_by_recent()
        self.controls.update_portfolio_list(self._portfolio_list, self._current_portfolio)

    def _on_portfolio_changed(self, name: str):
        name, _ = parse_portfolio_value(name)
        if name == self._current_portfolio:
            return
        self._current_portfolio = name
        self._is_ticker_mode = name not in self._portfolio_list
        self._update_heatmap()

    def create_settings_dialog(self, current_settings):
        return MonthlyReturnsSettingsDialog(self.theme_manager, current_settings, self)

    def _on_settings_changed(self, new_settings):
        self._update_heatmap()

    def _update_heatmap(self):
        if not self._current_portfolio:
            return

        self.table_container.hide()

        self._run_worker(
            MonthlyReturnsService.compute_monthly_grid,
            self._current_portfolio,
            self._is_ticker_mode,
            loading_message="Computing monthly returns...",
            on_complete=self._on_heatmap_complete,
            on_error=self._on_heatmap_error,
        )

    def _on_heatmap_complete(self, grid):
        """Handle completed heatmap computation."""
        if grid.empty:
            CustomMessageBox.information(
                self.theme_manager, self, "No Data",
                "No data available for the selected ticker or portfolio."
            )
        else:
            s = self.settings_manager.get_all_settings()
            self.table.update_grid(
                grid,
                colorscale=s["colorscale"],
                use_gradient=s["use_gradient"],
                decimals=s["decimals"],
                show_ytd=s["show_ytd"],
            )
        self.table_container.show()

    def _on_heatmap_error(self, error_msg: str):
        """Handle heatmap computation error."""
        self.table_container.show()
        CustomMessageBox.critical(
            self.theme_manager, self, "Load Error", error_msg
        )

    def _apply_theme(self):
        bg = self._get_theme_bg()
        self.setStyleSheet(f"""
            MonthlyReturnsModule {{ background-color: {bg}; }}
            QWidget {{ background-color: {bg}; }}
        """)

    def refresh(self):
        self._refresh_portfolio_list()
        if self._current_portfolio:
            self._update_heatmap()
