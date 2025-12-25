from __future__ import annotations

import sys
from PySide6.QtWidgets import QApplication

from app.ui_hub_window import HubWindow
from app.modules.chart_module import ChartModule
from app.modules.settings_module import SettingsModule
from app.modules.placeholder_modules import (
    AnalysisModule,
    NewsModule,
    PortfolioModule,
    ScreenerModule,
    WatchlistModule,
)


def main() -> int:
    app = QApplication(sys.argv)

    # Create main hub window
    hub = HubWindow()

    # Add modules
    hub.add_module("charts", ChartModule())
    hub.add_module("portfolio", PortfolioModule())
    hub.add_module("watchlist", WatchlistModule())
    hub.add_module("news", NewsModule())
    hub.add_module("screener", ScreenerModule())
    hub.add_module("analysis", AnalysisModule())
    hub.add_module("settings", SettingsModule(hub_window=hub))

    # Show charts module by default
    hub.show_initial_module("charts")

    hub.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())