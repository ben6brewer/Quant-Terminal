from __future__ import annotations

from PySide6.QtWidgets import (
    QButtonGroup,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt, QTimer

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common import CustomMessageBox

# API keys managed in .env  (add new entries here as needed)
_API_KEY_DEFS = [
    {"env_var": "FRED_API_KEY", "label": "FRED", "hint": "fred.stlouisfed.org/docs/api/api_key.html"},
]


class SettingsModule(QWidget):
    """Settings module with theme switching and other preferences."""

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._is_changing_theme = False  # Flag to prevent redundant updates
        self._setup_ui()
        self._sync_theme_buttons()
        self._apply_theme()
        self.theme_manager.theme_changed.connect(self._on_external_theme_change)

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
        layout.setContentsMargins(40, 70, 40, 40)  # Extra top margin to avoid home button
        layout.setSpacing(30)

        # Header
        self.header = QLabel("Settings")
        self.header.setObjectName("headerLabel")
        layout.addWidget(self.header)

        # Appearance settings
        appearance_group = self._create_appearance_group()
        layout.addWidget(appearance_group)

        # API Keys settings
        api_keys_group = self._create_api_keys_group()
        layout.addWidget(api_keys_group)

        # Memory Manager settings
        memory_group = self._create_memory_group()
        layout.addWidget(memory_group)

        layout.addStretch(1)

        scroll.setWidget(content)
        main_layout.addWidget(scroll)

    def _create_appearance_group(self) -> QGroupBox:
        """Create appearance settings group."""
        group = QGroupBox("Appearance")

        layout = QVBoxLayout()
        layout.setSpacing(15)

        # Theme label
        theme_label = QLabel("Color Theme")
        theme_label.setObjectName("themeLabel")
        layout.addWidget(theme_label)

        # Radio buttons for theme selection
        self.theme_group = QButtonGroup(self)

        self.dark_radio = QRadioButton("Dark Mode")
        self.theme_group.addButton(self.dark_radio, 0)
        layout.addWidget(self.dark_radio)

        self.light_radio = QRadioButton("Light Mode")
        self.theme_group.addButton(self.light_radio, 1)
        layout.addWidget(self.light_radio)

        self.bloomberg_radio = QRadioButton("Bloomberg Mode")
        self.theme_group.addButton(self.bloomberg_radio, 2)
        layout.addWidget(self.bloomberg_radio)

        # Connect theme change
        self.theme_group.buttonClicked.connect(self._on_theme_changed)

        group.setLayout(layout)
        return group

    def _create_memory_group(self) -> QGroupBox:
        """Create memory manager settings group."""
        group = QGroupBox("Memory Manager")

        layout = QVBoxLayout()
        layout.setSpacing(15)

        # Description label
        desc_label = QLabel(
            "Clear cached data stored on your local system. "
            "Data will be re-fetched from APIs on next use."
        )
        desc_label.setObjectName("descLabel")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        # Grid of cache buttons (2 columns)
        grid = QGridLayout()
        grid.setSpacing(10)

        # Define buttons: (label, handler)
        cache_buttons = [
            ("Clear Market Data", self._on_clear_market_data),
            ("Clear Ticker Metadata", self._on_clear_ticker_metadata),
            ("Clear Ticker Names", self._on_clear_ticker_names),
            ("Clear Portfolio Returns", self._on_clear_portfolio_returns),
            ("Clear Benchmark Returns", self._on_clear_benchmark_returns),
            ("Clear IWV Holdings", self._on_clear_iwv_holdings),
            ("Clear Ticker Lists", self._on_clear_ticker_lists),
            ("Clear Portfolios", self._on_clear_portfolios),
            ("Clear Module Settings", self._on_clear_module_settings),
        ]

        for i, (label, handler) in enumerate(cache_buttons):
            btn = QPushButton(label)
            btn.setObjectName("cacheButton")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(handler)
            row = i // 2
            col = i % 2
            grid.addWidget(btn, row, col)

        layout.addLayout(grid)

        # Clear All button (full width, more prominent)
        self.clear_all_btn = QPushButton("Clear All Cache")
        self.clear_all_btn.setObjectName("clearAllButton")
        self.clear_all_btn.setCursor(Qt.PointingHandCursor)
        self.clear_all_btn.clicked.connect(self._on_clear_all_cache)
        layout.addWidget(self.clear_all_btn)

        group.setLayout(layout)
        return group

    # -------------------------------------------------------------------------
    # API Keys
    # -------------------------------------------------------------------------

    def _create_api_keys_group(self) -> QGroupBox:
        """Create API keys management group."""
        group = QGroupBox("API Keys")

        layout = QVBoxLayout()
        layout.setSpacing(15)

        desc_label = QLabel(
            "Manage API keys for external data providers. "
            "Keys are stored in your local .env file."
        )
        desc_label.setObjectName("descLabel")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        self._api_key_rows: dict = {}

        # Read current values from .env
        env_values = self._read_env_values()

        for key_def in _API_KEY_DEFS:
            env_var = key_def["env_var"]
            current_value = env_values.get(env_var, "")

            row_layout = QHBoxLayout()
            row_layout.setSpacing(8)

            # Label
            label = QLabel(key_def["label"])
            label.setObjectName("apiKeyLabel")
            label.setFixedWidth(60)
            row_layout.addWidget(label)

            # Input field (masked by default)
            key_input = QLineEdit()
            key_input.setObjectName("apiKeyInput")
            key_input.setEchoMode(QLineEdit.Password)
            key_input.setReadOnly(True)
            key_input.setText(current_value)
            if not current_value:
                key_input.setPlaceholderText("Not configured")
            row_layout.addWidget(key_input)

            # Show/Hide toggle button
            toggle_btn = QPushButton("Show")
            toggle_btn.setObjectName("apiKeyToggle")
            toggle_btn.setCursor(Qt.PointingHandCursor)
            toggle_btn.setFixedWidth(60)
            toggle_btn.clicked.connect(lambda checked=False, ev=env_var: self._on_api_key_toggle(ev))
            row_layout.addWidget(toggle_btn)

            # Edit button
            edit_btn = QPushButton("Edit")
            edit_btn.setObjectName("apiKeyEdit")
            edit_btn.setCursor(Qt.PointingHandCursor)
            edit_btn.setFixedWidth(60)
            edit_btn.clicked.connect(lambda checked=False, ev=env_var: self._on_api_key_edit(ev))
            row_layout.addWidget(edit_btn)

            # Save button (hidden initially)
            save_btn = QPushButton("Save")
            save_btn.setObjectName("apiKeySave")
            save_btn.setCursor(Qt.PointingHandCursor)
            save_btn.setFixedWidth(60)
            save_btn.setVisible(False)
            save_btn.clicked.connect(lambda checked=False, ev=env_var: self._on_api_key_save(ev))
            row_layout.addWidget(save_btn)

            # Cancel button (hidden initially)
            cancel_btn = QPushButton("Cancel")
            cancel_btn.setObjectName("apiKeyCancel")
            cancel_btn.setCursor(Qt.PointingHandCursor)
            cancel_btn.setFixedWidth(60)
            cancel_btn.setVisible(False)
            cancel_btn.clicked.connect(lambda checked=False, ev=env_var: self._on_api_key_cancel(ev))
            row_layout.addWidget(cancel_btn)

            self._api_key_rows[env_var] = {
                "input": key_input,
                "toggle_btn": toggle_btn,
                "edit_btn": edit_btn,
                "save_btn": save_btn,
                "cancel_btn": cancel_btn,
                "original_value": current_value,
            }

            layout.addLayout(row_layout)

        group.setLayout(layout)
        return group

    def _read_env_values(self) -> dict:
        """Read all managed API key values from .env."""
        from dotenv import dotenv_values

        env_path = self._get_env_path()
        if not env_path.exists():
            return {}
        values = dotenv_values(env_path)
        return {d["env_var"]: values.get(d["env_var"], "") or "" for d in _API_KEY_DEFS}

    @staticmethod
    def _get_env_path():
        """Return path to project root .env file."""
        from pathlib import Path
        return Path(__file__).parents[4] / ".env"

    def _on_api_key_toggle(self, env_var: str) -> None:
        """Toggle show/hide of an API key."""
        row = self._api_key_rows[env_var]
        key_input: QLineEdit = row["input"]
        toggle_btn: QPushButton = row["toggle_btn"]

        if key_input.echoMode() == QLineEdit.Password:
            key_input.setEchoMode(QLineEdit.Normal)
            toggle_btn.setText("Hide")
        else:
            key_input.setEchoMode(QLineEdit.Password)
            toggle_btn.setText("Show")

    def _on_api_key_edit(self, env_var: str) -> None:
        """Enter edit mode for an API key row."""
        row = self._api_key_rows[env_var]
        row["original_value"] = row["input"].text()

        row["input"].setReadOnly(False)
        row["input"].setEchoMode(QLineEdit.Normal)
        row["input"].setFocus()
        row["toggle_btn"].setText("Show")
        row["toggle_btn"].setVisible(False)
        row["edit_btn"].setVisible(False)
        row["save_btn"].setVisible(True)
        row["cancel_btn"].setVisible(True)

    def _on_api_key_save(self, env_var: str) -> None:
        """Save edited API key to .env and return to display mode."""
        from dotenv import set_key

        row = self._api_key_rows[env_var]
        new_value = row["input"].text().strip()

        env_path = self._get_env_path()
        # Ensure .env exists
        if not env_path.exists():
            env_path.touch()

        set_key(str(env_path), env_var, new_value)

        # Update placeholder state
        if new_value:
            row["input"].setPlaceholderText("")
        else:
            row["input"].setPlaceholderText("Not configured")

        row["original_value"] = new_value

        # Invalidate service caches
        if env_var == "FRED_API_KEY":
            from app.ui.modules.yield_curve.services.fred_service import FredService
            FredService._api_key = None

        self._api_key_exit_edit(env_var)

    def _on_api_key_cancel(self, env_var: str) -> None:
        """Cancel editing and restore original value."""
        row = self._api_key_rows[env_var]
        row["input"].setText(row["original_value"])
        self._api_key_exit_edit(env_var)

    def _api_key_exit_edit(self, env_var: str) -> None:
        """Return an API key row to display mode."""
        row = self._api_key_rows[env_var]
        row["input"].setReadOnly(True)
        row["input"].setEchoMode(QLineEdit.Password)
        row["toggle_btn"].setText("Show")
        row["toggle_btn"].setVisible(True)
        row["edit_btn"].setVisible(True)
        row["save_btn"].setVisible(False)
        row["cancel_btn"].setVisible(False)

    # -------------------------------------------------------------------------
    # Cache clear handlers
    # -------------------------------------------------------------------------

    def _on_clear_market_data(self) -> None:
        """Clear market data cache (parquet files)."""
        result = CustomMessageBox.question(
            self.theme_manager,
            self,
            "Clear Market Data",
            "This will delete all cached price data (parquet files).\n\n"
            "Data will be re-fetched from Yahoo Finance on next use.\n\n"
            "Are you sure you want to continue?",
            CustomMessageBox.Ok | CustomMessageBox.Cancel,
        )
        if result == CustomMessageBox.Ok:
            from app.services.market_data import clear_cache
            try:
                clear_cache()
            except Exception as e:
                self._show_error("Failed to clear market data cache", e)

    def _on_clear_ticker_metadata(self) -> None:
        """Clear ticker metadata cache."""
        result = CustomMessageBox.question(
            self.theme_manager,
            self,
            "Clear Ticker Metadata",
            "This will delete cached ticker information (sector, industry, beta, etc.).\n\n"
            "Metadata will be re-fetched from Yahoo Finance on next use.\n\n"
            "Are you sure you want to continue?",
            CustomMessageBox.Ok | CustomMessageBox.Cancel,
        )
        if result == CustomMessageBox.Ok:
            from app.services.ticker_metadata_service import TickerMetadataService
            try:
                TickerMetadataService.clear_cache()
            except Exception as e:
                self._show_error("Failed to clear ticker metadata cache", e)

    def _on_clear_ticker_names(self) -> None:
        """Clear ticker names cache."""
        result = CustomMessageBox.question(
            self.theme_manager,
            self,
            "Clear Ticker Names",
            "This will delete cached ticker display names (e.g., 'Apple Inc.').\n\n"
            "Names will be re-fetched from Yahoo Finance on next use.\n\n"
            "Are you sure you want to continue?",
            CustomMessageBox.Ok | CustomMessageBox.Cancel,
        )
        if result == CustomMessageBox.Ok:
            from app.services.ticker_name_cache import TickerNameCache
            try:
                TickerNameCache.clear_cache()
            except Exception as e:
                self._show_error("Failed to clear ticker names cache", e)

    def _on_clear_portfolio_returns(self) -> None:
        """Clear portfolio returns cache."""
        result = CustomMessageBox.question(
            self.theme_manager,
            self,
            "Clear Portfolio Returns",
            "This will delete all cached portfolio return calculations.\n\n"
            "Returns will be recalculated on next use.\n\n"
            "Are you sure you want to continue?",
            CustomMessageBox.Ok | CustomMessageBox.Cancel,
        )
        if result == CustomMessageBox.Ok:
            from app.services.returns_data_service import ReturnsDataService
            try:
                ReturnsDataService.clear_cache()
            except Exception as e:
                self._show_error("Failed to clear portfolio returns cache", e)

    def _on_clear_benchmark_returns(self) -> None:
        """Clear benchmark returns cache."""
        result = CustomMessageBox.question(
            self.theme_manager,
            self,
            "Clear Benchmark Returns",
            "This will delete all cached benchmark constituent returns.\n\n"
            "Returns will be re-fetched on next use.\n\n"
            "Are you sure you want to continue?",
            CustomMessageBox.Ok | CustomMessageBox.Cancel,
        )
        if result == CustomMessageBox.Ok:
            from app.services.benchmark_returns_service import BenchmarkReturnsService
            try:
                BenchmarkReturnsService.clear_cache()
            except Exception as e:
                self._show_error("Failed to clear benchmark returns cache", e)

    def _on_clear_iwv_holdings(self) -> None:
        """Clear IWV holdings cache."""
        result = CustomMessageBox.question(
            self.theme_manager,
            self,
            "Clear IWV Holdings",
            "This will delete cached iShares Russell 3000 ETF holdings.\n\n"
            "Holdings will be re-fetched from iShares on next use.\n\n"
            "Are you sure you want to continue?",
            CustomMessageBox.Ok | CustomMessageBox.Cancel,
        )
        if result == CustomMessageBox.Ok:
            from app.services.ishares_holdings_service import ISharesHoldingsService
            try:
                ISharesHoldingsService.clear_cache()
            except Exception as e:
                self._show_error("Failed to clear IWV holdings cache", e)

    def _on_clear_ticker_lists(self) -> None:
        """Clear saved ticker lists."""
        result = CustomMessageBox.question(
            self.theme_manager,
            self,
            "Clear Ticker Lists",
            "This will delete all saved ticker lists used by EF, Correlation, "
            "and Covariance modules.\n\n"
            "Are you sure you want to continue?",
            CustomMessageBox.Ok | CustomMessageBox.Cancel,
        )
        if result == CustomMessageBox.Ok:
            from app.ui.modules.analysis.services.ticker_list_persistence import TickerListPersistence
            try:
                TickerListPersistence.clear_all()
            except Exception as e:
                self._show_error("Failed to clear ticker lists", e)

    def _on_clear_portfolios(self) -> None:
        """Clear all portfolio files."""
        result = CustomMessageBox.question(
            self.theme_manager,
            self,
            "Clear Portfolios",
            "This will permanently delete ALL portfolio transaction logs.\n\n"
            "This action cannot be undone.\n\n"
            "Are you sure you want to continue?",
            CustomMessageBox.Ok | CustomMessageBox.Cancel,
        )
        if result == CustomMessageBox.Ok:
            from app.ui.modules.portfolio_construction.services.portfolio_persistence import PortfolioPersistence
            try:
                PortfolioPersistence.clear_all()
            except Exception as e:
                self._show_error("Failed to clear portfolios", e)

    def _on_clear_module_settings(self) -> None:
        """Clear all module settings files."""
        result = CustomMessageBox.question(
            self.theme_manager,
            self,
            "Clear Module Settings",
            "This will delete all module settings (chart preferences, "
            "default tickers, etc.).\n\n"
            "Settings will be reset to defaults on next use.\n\n"
            "Are you sure you want to continue?",
            CustomMessageBox.Ok | CustomMessageBox.Cancel,
        )
        if result == CustomMessageBox.Ok:
            from pathlib import Path
            try:
                settings_dir = Path.home() / ".quant_terminal"
                if settings_dir.exists():
                    for f in settings_dir.glob("*_settings.json"):
                        f.unlink()
            except Exception as e:
                self._show_error("Failed to clear module settings", e)

    def _on_clear_all_cache(self) -> None:
        """Clear all caches."""
        result = CustomMessageBox.question(
            self.theme_manager,
            self,
            "Clear All Cache",
            "This will delete ALL cached data:\n\n"
            "• Market data (price history)\n"
            "• Ticker metadata (sector, industry, beta)\n"
            "• Ticker names\n"
            "• Portfolio returns\n"
            "• Benchmark returns\n"
            "• IWV holdings\n"
            "• Ticker lists\n"
            "• Portfolios\n"
            "• Module settings\n\n"
            "All data will be re-fetched or reset on next use.\n\n"
            "Are you sure you want to continue?",
            CustomMessageBox.Ok | CustomMessageBox.Cancel,
        )
        if result == CustomMessageBox.Ok:
            errors = []

            # Clear all caches
            try:
                from app.services.market_data import clear_cache
                clear_cache()
            except Exception as e:
                errors.append(f"Market data: {e}")

            try:
                from app.services.ticker_metadata_service import TickerMetadataService
                TickerMetadataService.clear_cache()
            except Exception as e:
                errors.append(f"Ticker metadata: {e}")

            try:
                from app.services.ticker_name_cache import TickerNameCache
                TickerNameCache.clear_cache()
            except Exception as e:
                errors.append(f"Ticker names: {e}")

            try:
                from app.services.returns_data_service import ReturnsDataService
                ReturnsDataService.clear_cache()
            except Exception as e:
                errors.append(f"Portfolio returns: {e}")

            try:
                from app.services.benchmark_returns_service import BenchmarkReturnsService
                BenchmarkReturnsService.clear_cache()
            except Exception as e:
                errors.append(f"Benchmark returns: {e}")

            try:
                from app.services.ishares_holdings_service import ISharesHoldingsService
                ISharesHoldingsService.clear_cache()
            except Exception as e:
                errors.append(f"IWV holdings: {e}")

            try:
                from app.ui.modules.analysis.services.ticker_list_persistence import TickerListPersistence
                TickerListPersistence.clear_all()
            except Exception as e:
                errors.append(f"Ticker lists: {e}")

            try:
                from app.ui.modules.portfolio_construction.services.portfolio_persistence import PortfolioPersistence
                PortfolioPersistence.clear_all()
            except Exception as e:
                errors.append(f"Portfolios: {e}")

            try:
                from pathlib import Path
                settings_dir = Path.home() / ".quant_terminal"
                if settings_dir.exists():
                    for f in settings_dir.glob("*_settings.json"):
                        f.unlink()
            except Exception as e:
                errors.append(f"Module settings: {e}")

            if errors:
                CustomMessageBox.critical(
                    self.theme_manager,
                    self,
                    "Partial Error",
                    "Some caches failed to clear:\n\n" + "\n".join(errors),
                )

    def _show_error(self, message: str, error: Exception) -> None:
        """Show error dialog."""
        CustomMessageBox.critical(
            self.theme_manager,
            self,
            "Error",
            f"{message}:\n\n{str(error)}",
        )

    def _sync_theme_buttons(self) -> None:
        """Synchronize radio buttons with current theme."""
        current_theme = self.theme_manager.current_theme
        if current_theme == "dark":
            self.dark_radio.setChecked(True)
        elif current_theme == "bloomberg":
            self.bloomberg_radio.setChecked(True)
        else:
            self.light_radio.setChecked(True)

    def _on_theme_changed(self) -> None:
        """Handle theme change from radio buttons."""
        if self.dark_radio.isChecked():
            theme = "dark"
        elif self.bloomberg_radio.isChecked():
            theme = "bloomberg"
        else:
            theme = "light"

        # Set flag to skip redundant _apply_theme call from signal
        self._is_changing_theme = True
        self.theme_manager.set_theme(theme)
        # Defer _apply_theme to avoid blocking the UI thread
        QTimer.singleShot(0, self._apply_theme)
        # Defer flag reset so external handlers still skip correctly
        QTimer.singleShot(0, lambda: setattr(self, '_is_changing_theme', False))

    def _on_external_theme_change(self) -> None:
        """Handle theme changes from external sources (not our radio buttons)."""
        if self._is_changing_theme:
            return  # Skip if we triggered the change
        self._sync_theme_buttons()
        self._apply_theme()

    def _apply_theme(self) -> None:
        """Apply theme-specific styling."""
        theme = self.theme_manager.current_theme

        if theme == "light":
            stylesheet = self._get_light_stylesheet()
        elif theme == "bloomberg":
            stylesheet = self._get_bloomberg_stylesheet()
        else:
            stylesheet = self._get_dark_stylesheet()

        self.setStyleSheet(stylesheet)

    def _get_dark_stylesheet(self) -> str:
        """Dark theme stylesheet."""
        return """
            QWidget {
                background-color: #1e1e1e;
                color: #ffffff;
            }
            QScrollArea {
                background-color: #1e1e1e;
                border: none;
            }
            QLabel#headerLabel {
                font-size: 24px;
                font-weight: bold;
                color: #ffffff;
                margin-bottom: 10px;
            }
            QLabel#themeLabel {
                font-size: 14px;
                font-weight: normal;
                color: #cccccc;
                margin-left: 10px;
            }
            QGroupBox {
                font-size: 18px;
                font-weight: bold;
                color: #ffffff;
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
            QRadioButton {
                color: #ffffff;
                font-size: 13px;
                padding: 8px;
                margin-left: 20px;
                spacing: 8px;
            }
            QRadioButton::indicator {
                width: 16px;
                height: 16px;
                border-radius: 8px;
                border: 2px solid #3d3d3d;
                background-color: #2d2d2d;
            }
            QRadioButton::indicator:checked {
                border-color: #00d4ff;
                background-color: #00d4ff;
            }
            QRadioButton::indicator:hover {
                border-color: #00d4ff;
            }
            QLabel#descLabel {
                font-size: 13px;
                color: #999999;
                margin-left: 10px;
                margin-right: 10px;
            }
            QPushButton#cacheButton {
                background-color: #2d2d2d;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 6px;
                padding: 10px 16px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton#cacheButton:hover {
                border-color: #ff6b6b;
                background-color: #3d3d3d;
            }
            QPushButton#cacheButton:pressed {
                background-color: #ff6b6b;
                color: #ffffff;
            }
            QPushButton#clearAllButton {
                background-color: #3d2020;
                color: #ffffff;
                border: 1px solid #ff6b6b;
                border-radius: 6px;
                padding: 12px 24px;
                font-size: 13px;
                font-weight: bold;
                margin-top: 10px;
            }
            QPushButton#clearAllButton:hover {
                border-color: #ff8888;
                background-color: #4d2525;
            }
            QPushButton#clearAllButton:pressed {
                background-color: #ff6b6b;
                color: #ffffff;
            }
            QLabel#apiKeyLabel {
                font-size: 13px;
                font-weight: bold;
                color: #cccccc;
                margin-left: 10px;
            }
            QLineEdit#apiKeyInput {
                background-color: #2d2d2d;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 13px;
                font-family: "Menlo", "Consolas", "Courier New", monospace;
            }
            QLineEdit#apiKeyInput:focus {
                border-color: #00d4ff;
            }
            QLineEdit#apiKeyInput:read-only {
                background-color: #252525;
            }
            QPushButton#apiKeyToggle, QPushButton#apiKeyEdit,
            QPushButton#apiKeyCancel {
                background-color: #2d2d2d;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 6px 4px;
                font-size: 11px;
            }
            QPushButton#apiKeyToggle:hover, QPushButton#apiKeyEdit:hover,
            QPushButton#apiKeyCancel:hover {
                border-color: #00d4ff;
                background-color: #3d3d3d;
            }
            QPushButton#apiKeySave {
                background-color: #00d4ff;
                color: #000000;
                border: 1px solid #00d4ff;
                border-radius: 4px;
                padding: 6px 4px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton#apiKeySave:hover {
                background-color: #33ddff;
            }
        """

    def _get_light_stylesheet(self) -> str:
        """Light theme stylesheet."""
        return """
            QWidget {
                background-color: #ffffff;
                color: #000000;
            }
            QScrollArea {
                background-color: #ffffff;
                border: none;
            }
            QLabel#headerLabel {
                font-size: 24px;
                font-weight: bold;
                color: #000000;
                margin-bottom: 10px;
            }
            QLabel#themeLabel {
                font-size: 14px;
                font-weight: normal;
                color: #333333;
                margin-left: 10px;
            }
            QGroupBox {
                font-size: 18px;
                font-weight: bold;
                color: #000000;
                border: 2px solid #cccccc;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 20px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 5px;
            }
            QRadioButton {
                color: #000000;
                font-size: 13px;
                padding: 8px;
                margin-left: 20px;
                spacing: 8px;
            }
            QRadioButton::indicator {
                width: 16px;
                height: 16px;
                border-radius: 8px;
                border: 2px solid #cccccc;
                background-color: #f5f5f5;
            }
            QRadioButton::indicator:checked {
                border-color: #0066cc;
                background-color: #0066cc;
            }
            QRadioButton::indicator:hover {
                border-color: #0066cc;
            }
            QLabel#descLabel {
                font-size: 13px;
                color: #666666;
                margin-left: 10px;
                margin-right: 10px;
            }
            QPushButton#cacheButton {
                background-color: #f5f5f5;
                color: #000000;
                border: 1px solid #cccccc;
                border-radius: 6px;
                padding: 10px 16px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton#cacheButton:hover {
                border-color: #e53935;
                background-color: #e8e8e8;
            }
            QPushButton#cacheButton:pressed {
                background-color: #e53935;
                color: #ffffff;
            }
            QPushButton#clearAllButton {
                background-color: #ffebee;
                color: #c62828;
                border: 1px solid #e53935;
                border-radius: 6px;
                padding: 12px 24px;
                font-size: 13px;
                font-weight: bold;
                margin-top: 10px;
            }
            QPushButton#clearAllButton:hover {
                border-color: #c62828;
                background-color: #ffcdd2;
            }
            QPushButton#clearAllButton:pressed {
                background-color: #e53935;
                color: #ffffff;
            }
            QLabel#apiKeyLabel {
                font-size: 13px;
                font-weight: bold;
                color: #333333;
                margin-left: 10px;
            }
            QLineEdit#apiKeyInput {
                background-color: #f5f5f5;
                color: #000000;
                border: 1px solid #cccccc;
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 13px;
                font-family: "Menlo", "Consolas", "Courier New", monospace;
            }
            QLineEdit#apiKeyInput:focus {
                border-color: #0066cc;
            }
            QLineEdit#apiKeyInput:read-only {
                background-color: #eeeeee;
            }
            QPushButton#apiKeyToggle, QPushButton#apiKeyEdit,
            QPushButton#apiKeyCancel {
                background-color: #f5f5f5;
                color: #000000;
                border: 1px solid #cccccc;
                border-radius: 4px;
                padding: 6px 4px;
                font-size: 11px;
            }
            QPushButton#apiKeyToggle:hover, QPushButton#apiKeyEdit:hover,
            QPushButton#apiKeyCancel:hover {
                border-color: #0066cc;
                background-color: #e8e8e8;
            }
            QPushButton#apiKeySave {
                background-color: #0066cc;
                color: #ffffff;
                border: 1px solid #0066cc;
                border-radius: 4px;
                padding: 6px 4px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton#apiKeySave:hover {
                background-color: #0077ee;
            }
        """

    def _get_bloomberg_stylesheet(self) -> str:
        """Bloomberg theme stylesheet."""
        return """
            QWidget {
                background-color: #000814;
                color: #e8e8e8;
            }
            QScrollArea {
                background-color: #000814;
                border: none;
            }
            QLabel#headerLabel {
                font-size: 24px;
                font-weight: bold;
                color: #e8e8e8;
                margin-bottom: 10px;
            }
            QLabel#themeLabel {
                font-size: 14px;
                font-weight: normal;
                color: #a8a8a8;
                margin-left: 10px;
            }
            QGroupBox {
                font-size: 18px;
                font-weight: bold;
                color: #e8e8e8;
                border: 2px solid #1a2838;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 20px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 5px;
            }
            QRadioButton {
                color: #e8e8e8;
                font-size: 13px;
                padding: 8px;
                margin-left: 20px;
                spacing: 8px;
            }
            QRadioButton::indicator {
                width: 16px;
                height: 16px;
                border-radius: 8px;
                border: 2px solid #1a2838;
                background-color: #0d1420;
            }
            QRadioButton::indicator:checked {
                border-color: #FF8000;
                background-color: #FF8000;
            }
            QRadioButton::indicator:hover {
                border-color: #FF8000;
            }
            QLabel#descLabel {
                font-size: 13px;
                color: #808080;
                margin-left: 10px;
                margin-right: 10px;
            }
            QPushButton#cacheButton {
                background-color: #0d1420;
                color: #e8e8e8;
                border: 1px solid #1a2838;
                border-radius: 6px;
                padding: 10px 16px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton#cacheButton:hover {
                border-color: #ff6b6b;
                background-color: #1a2838;
            }
            QPushButton#cacheButton:pressed {
                background-color: #ff6b6b;
                color: #ffffff;
            }
            QPushButton#clearAllButton {
                background-color: #2a1515;
                color: #ff6b6b;
                border: 1px solid #ff6b6b;
                border-radius: 6px;
                padding: 12px 24px;
                font-size: 13px;
                font-weight: bold;
                margin-top: 10px;
            }
            QPushButton#clearAllButton:hover {
                border-color: #ff8888;
                background-color: #3a2020;
            }
            QPushButton#clearAllButton:pressed {
                background-color: #ff6b6b;
                color: #ffffff;
            }
            QLabel#apiKeyLabel {
                font-size: 13px;
                font-weight: bold;
                color: #a8a8a8;
                margin-left: 10px;
            }
            QLineEdit#apiKeyInput {
                background-color: #0d1420;
                color: #e8e8e8;
                border: 1px solid #1a2838;
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 13px;
                font-family: "Menlo", "Consolas", "Courier New", monospace;
            }
            QLineEdit#apiKeyInput:focus {
                border-color: #FF8000;
            }
            QLineEdit#apiKeyInput:read-only {
                background-color: #0a1018;
            }
            QPushButton#apiKeyToggle, QPushButton#apiKeyEdit,
            QPushButton#apiKeyCancel {
                background-color: #0d1420;
                color: #e8e8e8;
                border: 1px solid #1a2838;
                border-radius: 4px;
                padding: 6px 4px;
                font-size: 11px;
            }
            QPushButton#apiKeyToggle:hover, QPushButton#apiKeyEdit:hover,
            QPushButton#apiKeyCancel:hover {
                border-color: #FF8000;
                background-color: #1a2838;
            }
            QPushButton#apiKeySave {
                background-color: #FF8000;
                color: #000000;
                border: 1px solid #FF8000;
                border-radius: 4px;
                padding: 6px 4px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton#apiKeySave:hover {
                background-color: #FF9933;
            }
        """
