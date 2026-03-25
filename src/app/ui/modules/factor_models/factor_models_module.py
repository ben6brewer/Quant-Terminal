"""Factor Models Module — return decomposition across academic factor models."""

from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout

from app.core.theme_manager import ThemeManager
from app.ui.modules.base_module import BaseModule
from app.ui.widgets.common.portfolio_ticker_combo import parse_portfolio_value

from .widgets.factor_models_toolbar import FactorModelsToolbar
from .widgets.factor_attribution_chart import FactorAttributionChart
from .widgets.factor_stats_panel import FactorStatsPanel


class FactorModelsModule(BaseModule):
    """Factor return decomposition — decomposes asset/portfolio returns across
    CAPM, FF3/5, Carhart, Q-factor, and AQR models."""

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(theme_manager, parent)
        self._last_result = None

        self._setup_ui()
        self._connect_signals()
        self._apply_theme()
        self._load_settings()

    # ── UI Setup ────────────────────────────────────────────────────────────

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar (now contains input combo)
        self.controls = FactorModelsToolbar(self.theme_manager)
        layout.addWidget(self.controls)

        # Populate portfolio list in toolbar
        self._refresh_portfolios()

        # Content area: chart (stretch) + stats panel
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self.chart = FactorAttributionChart()
        content_layout.addWidget(self.chart, stretch=1)

        self.stats_panel = FactorStatsPanel(self.theme_manager)
        content_layout.addWidget(self.stats_panel)

        layout.addLayout(content_layout, stretch=1)

    def _connect_signals(self):
        self.controls.home_clicked.connect(self.home_clicked.emit)
        self.controls.run_clicked.connect(self._run)
        self.controls.export_clicked.connect(self._on_export)
        self.controls.settings_clicked.connect(self._on_settings_clicked)
        self.controls.view_mode_changed.connect(self._on_view_mode_changed)
        self.controls.model_changed.connect(self._on_model_changed)
        self.controls.input_changed.connect(self._on_input_changed)
        self.theme_manager.theme_changed.connect(self._on_theme_changed_lazy)

    def _refresh_portfolios(self):
        """Populate the toolbar input combo with saved portfolios."""
        try:
            from app.services.portfolio_data_service import PortfolioDataService

            svc = PortfolioDataService()
            names = svc.list_portfolios_by_recent()
            self.controls.set_portfolios(names)
        except Exception:
            pass

    # ── Settings ────────────────────────────────────────────────────────────

    def _load_settings(self):
        s = self.settings_manager.get_all_settings()

        # Restore input
        mode = s.get("input_mode", "ticker")
        if mode == "portfolio":
            portfolio = s.get("portfolio", "")
            if portfolio:
                self.controls.set_input_value(f"[Port] {portfolio}")
        else:
            ticker = s.get("ticker", "")
            if ticker:
                self.controls.set_input_value(ticker)

        model_key = s.get("model_key", "ff5mom")
        self.controls.set_model(model_key)

        freq = s.get("frequency", "monthly")
        self.controls.set_frequency(freq)

        lookback = s.get("lookback_days", 1825)
        self.controls.set_lookback(lookback)

        view_mode = s.get("view_mode", "cumulative")
        self.controls.set_view_mode(view_mode)

        settings = self.settings_manager.get_all_settings()
        self.chart.apply_settings(settings)
        self.stats_panel.setVisible(settings.get("show_stats_panel", True))

    def create_settings_manager(self):
        from .services.factor_settings_manager import FactorSettingsManager
        return FactorSettingsManager()

    def get_settings_options(self):
        return [
            ("show_gridlines", "Show Gridlines"),
            ("show_stats_panel", "Show Stats Panel"),
        ]

    def _on_settings_changed(self, new_settings):
        settings = self.settings_manager.get_all_settings()
        self.chart.apply_settings(settings)
        self.stats_panel.setVisible(settings.get("show_stats_panel", True))
        if self._last_result is not None:
            view_mode = self.controls.get_view_mode()
            self.chart.update_data(self._last_result, view_mode)
            self.chart.set_theme(self.theme_manager.current_theme)

    # ── Run ─────────────────────────────────────────────────────────────────

    def _on_input_changed(self, _value: str):
        """Input changed via combo — refresh portfolios and auto-run."""
        self._refresh_portfolios()

    def _on_export(self):
        """Export regression results to Excel."""
        if self._last_result is None:
            from app.ui.widgets.common import CustomMessageBox

            CustomMessageBox.warning(
                self.theme_manager,
                self,
                "No Results",
                "Run a factor regression first before exporting.",
            )
            return

        result = self._last_result
        model_spec = self.controls.get_model_spec()
        if model_spec is None:
            return

        # Re-fetch factor data (cached, instant) and align to regression dates
        from .services.factor_data_service import FactorDataService

        factor_df, rf = FactorDataService.get_factors(model_spec, result.frequency)

        from .services.factor_export_service import FactorExportService

        # Get the identifier (ticker or portfolio name) for labeling
        raw_value = self.controls.get_input_value()
        identifier, _is_portfolio = parse_portfolio_value(raw_value)

        FactorExportService.export_to_excel(
            self, self.theme_manager, result, factor_df, rf, model_spec, identifier,
        )

    def _run(self):
        # Parse input from toolbar combo
        raw_value = self.controls.get_input_value()
        identifier, is_portfolio = parse_portfolio_value(raw_value)

        if not identifier:
            self.chart.show_placeholder(
                "Enter a ticker or select a portfolio to run factor analysis"
            )
            return

        # Persist state
        model_key = self.controls.get_model_key()
        frequency = self.controls.get_frequency()
        lookback = self.controls.get_lookback_days()

        save_dict = {
            "input_mode": "portfolio" if is_portfolio else "ticker",
            "ticker": "" if is_portfolio else identifier,
            "portfolio": identifier if is_portfolio else "",
            "model_key": model_key,
            "frequency": frequency,
            "lookback_days": lookback,
            "view_mode": self.controls.get_view_mode(),
        }

        # Custom date range
        custom_range = self.controls.custom_date_range if lookback == -1 else None
        if custom_range:
            save_dict["custom_start_date"] = custom_range[0]
            save_dict["custom_end_date"] = custom_range[1]

        self.settings_manager.update_settings(save_dict)

        self._run_worker(
            self._compute,
            not is_portfolio,
            identifier,
            model_key,
            frequency,
            lookback,
            custom_range,
            loading_message="Running factor regression...",
            on_complete=self._on_complete,
            on_error=self._on_error,
        )

    @staticmethod
    def _compute(is_ticker, identifier, model_key, frequency, lookback_days, custom_range):
        """Background computation — fetch data + run regression."""
        import pandas as pd
        from datetime import datetime, timedelta

        from .services.model_definitions import MODELS
        from .services.custom_model_store import CustomModelStore
        from .services.factor_data_service import FactorDataService
        from .services.factor_regression_service import FactorRegressionService

        # Resolve model spec (built-in or custom)
        model_spec = MODELS.get(model_key)
        if model_spec is None:
            model_spec = CustomModelStore.get_model(model_key)
        if model_spec is None:
            raise ValueError(f"Unknown model: {model_key}")

        # Determine date range
        if custom_range:
            start_str, end_str = custom_range
        elif lookback_days is not None and lookback_days > 0:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=lookback_days)
            start_str = start_date.strftime("%Y-%m-%d")
            end_str = end_date.strftime("%Y-%m-%d")
        else:
            start_str = "1963-01-01"
            end_str = None

        # Fetch asset returns
        if is_ticker:
            from app.services.market_data import fetch_price_history

            prices = fetch_price_history(identifier)
            if prices is None or prices.empty:
                raise ValueError(f"No price data available for {identifier}")

            # Compute daily returns
            if "Close" in prices.columns:
                close = prices["Close"]
            elif "Adj Close" in prices.columns:
                close = prices["Adj Close"]
            else:
                close = prices.iloc[:, 0]

            daily_returns = close.pct_change().dropna()
            daily_returns.index = pd.to_datetime(daily_returns.index).tz_localize(None)
            daily_returns = daily_returns.loc[start_str:end_str]
        else:
            from app.services.returns_data_service import ReturnsDataService

            svc = ReturnsDataService()
            daily_returns = svc.get_time_varying_portfolio_returns(
                identifier,
                start_date=start_str,
                end_date=end_str,
                interval="daily",
            )
            if daily_returns is None or daily_returns.empty:
                raise ValueError(f"No return data for portfolio '{identifier}'")

        # Resample asset returns to target frequency
        if frequency == "monthly":
            asset_returns = (1 + daily_returns).resample("ME").prod() - 1
        elif frequency == "weekly":
            asset_returns = (1 + daily_returns).resample("W-FRI").prod() - 1
        else:
            asset_returns = daily_returns

        asset_returns = asset_returns.dropna()

        # Fetch factor data
        factor_df, rf = FactorDataService.get_factors(model_spec, frequency)

        # Run regression
        result = FactorRegressionService.run_regression(
            asset_returns, factor_df, rf, model_spec, frequency,
        )
        return result

    def _on_complete(self, result):
        self._last_result = result
        view_mode = self.controls.get_view_mode()
        settings = self.settings_manager.get_all_settings()
        self.chart.apply_settings(settings)
        self.chart.update_data(result, view_mode)
        self.chart.set_theme(self.theme_manager.current_theme)
        self.stats_panel.update_stats(result)
        self.stats_panel.setVisible(settings.get("show_stats_panel", True))

    def _on_error(self, error_msg: str):
        self.chart.show_placeholder(f"Error: {error_msg}")
        self.stats_panel.show_placeholder(error_msg)

    # ── View/Model change without re-run ────────────────────────────────────

    def _on_view_mode_changed(self, view_mode: str):
        """Re-render chart without re-running regression."""
        if self._last_result is not None:
            self.chart.set_view_mode(view_mode)

    def _on_model_changed(self, _model_key: str):
        """Model changed — clear cached result so next Run uses new model."""
        self._last_result = None

    # ── Theme ───────────────────────────────────────────────────────────────

    def _apply_theme(self):
        self.setStyleSheet(f"background-color: {self._get_theme_bg()};")
        self.chart.set_theme(self.theme_manager.current_theme)
