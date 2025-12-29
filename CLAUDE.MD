# Quant Terminal - AI Assistant Guide

**Optimized for AI assistants working on this codebase**

## 1. Project Overview

**Quant Terminal** is a Bloomberg Terminal-inspired desktop application for investing, charting, and technical analysis. Built with Python and PySide6 (Qt), it provides professional-grade charting, custom indicators, and equation-based price analysis within a modular, tile-based navigation system designed to scale to 25+ specialized finance modules.

### Current State

- **Version**: 0.1.0 (early stage, actively developing)
- **Status**: Tile-based navigation complete, chart module fully refactored and modularized, ready to scale
- **Production Modules**: 1 (Charts)
- **Placeholder Modules**: 8 (Crypto Dashboard, DeFi, NFT Tracker, Portfolio, Watchlist, News, Screener, Analysis)
- **Planned Modules**: 15+ (Portfolio Performance, Risk Analytics, Monte Carlo, DCF Valuation, Backtesting, etc.)

### Tech Stack

- **Python**: 3.10+ with type hints
- **UI Framework**: PySide6 (Qt6)
- **Charting**: PyQtGraph (real-time plotting)
- **Data**: pandas, numpy
- **Market Data**: yfinance (Yahoo Finance API)

### Key Capabilities

1. **Ticker Equations**: Mathematical expressions combining tickers (e.g., `=BTC-USD/SPX`)
2. **Technical Indicators**: 9 built-in types + custom indicator creation with plugin system
3. **Multi-Timeframe Charting**: Daily, weekly, monthly, yearly with candlestick/line charts
4. **Tile-Based Navigation**: 3-column grid with section tabs, search, and favorites
5. **Dual Plot System**: Main price chart + oscillator subplot with draggable resize
6. **Order Book Integration**: Real-time Binance depth charts and ladder view
7. **Full Theme System**: Dark, Light, Bloomberg with signal-based propagation

---

## 2. Architecture & Design Patterns

### Core Architectural Principles

#### 1. Module-Scoped Services Pattern

**Purpose**: Prevent services directory clutter as codebase scales to 25+ modules

**Implementation**:
- **Global `services/`**: Only truly shared services (market_data, favorites, preferences)
- **Module `services/`**: Module-specific business logic in `modules/{module_name}/services/`

**Example**:
```
services/                         # ONLY shared services
├── market_data.py               # Used by all modules
├── favorites_service.py         # Used by navigation
└── preferences_service.py       # Used by settings

modules/chart/services/          # Chart-specific services
├── indicator_service.py         # Only chart module needs
├── ticker_equation_parser.py    # Only chart module needs
├── chart_settings_manager.py    # Only chart module needs
├── chart_theme_service.py       # Only chart module needs
└── binance_data.py              # Only chart module needs
```

**Rationale**: With 25+ modules planned, a flat `services/` directory would become unmaintainable. Module-scoped services keep related code together and enable independent module development.

#### 2. Separation of Concerns

**Data Flow**:
```
MarketDataService (global) → Module Services → Widgets → UI
                ↓
        ThemeManager (signal propagation to all components)
```

**Layer Responsibilities**:
- **Services**: Business logic, calculations, data fetching (stateless/singleton-like)
- **Widgets**: Presentation, user interaction (reusable UI components)
- **Modules**: Integration, orchestration (compose services + widgets)
- **Navigation**: Module discovery, launching (HomeScreen, tiles, tabs)

**Critical Rule**: Services never import widgets. Widgets can import services. Modules orchestrate both.

#### 3. Widget Organization Strategy

**Purpose**: Organize widgets by reusability scope, not by feature

**Structure**:
```
ui/widgets/
├── charting/              # Reusable chart infrastructure for ALL chart modules
│   ├── base_chart.py      # Foundation for Portfolio, Risk, Monte Carlo charts
│   ├── axes/              # Draggable price, date, custom axes
│   ├── renderers/         # Candlestick, line renderers
│   └── overlays/          # Resize handles, labels
│
├── navigation/            # Navigation components used by HubWindow
│   ├── home_screen.py
│   ├── module_tile.py
│   ├── module_tile_grid.py
│   └── section_tab_bar.py
│
└── common/                # Truly shared widgets (used by 3+ modules)
    └── custom_message_box.py

ui/modules/{module_name}/widgets/  # Module-specific widgets
    └── price_chart.py              # Only used by chart module
```

**Decision Tree**:
- **Will 3+ modules use this?** → `ui/widgets/common/`
- **Is it chart infrastructure?** → `ui/widgets/charting/`
- **Is it navigation?** → `ui/widgets/navigation/`
- **Otherwise** → `ui/modules/{module_name}/widgets/`

#### 4. Composition Over Inheritance

**Anti-Pattern**: Deep inheritance chains
```python
class ChartWidget(BaseChart):
    class AdvancedChartWidget(ChartWidget):
        class SuperAdvancedChartWidget(AdvancedChartWidget):  # ❌ Hard to maintain
```

**Preferred Pattern**: Composition
```python
class PortfolioChart(BaseChart):  # Only inherit core infrastructure
    def __init__(self, theme_manager):
        super().__init__(theme_manager)

        # Compose reusable components
        self.price_axis = PriceAxisItem(orientation='right')
        self.date_axis = DateIndexAxisItem(orientation='bottom')
        self.resize_handle = ResizeHandle(orientation='horizontal')

        # Focus on portfolio-specific logic
        self.plot_cumulative_returns(...)
```

**Benefits**:
- Clear component boundaries
- Easy to test components independently
- Reusable components for future modules

#### 5. Signal-Based Architecture

**Purpose**: Loose coupling between components

**Pattern**:
```python
# ThemeManager (publisher)
class ThemeManager(QObject):
    theme_changed = Signal(str)  # Emits theme name

    def set_theme(self, theme: str):
        self.current_theme = theme
        self.theme_changed.emit(theme)

# Widget (subscriber)
class MyWidget(QWidget):
    def __init__(self, theme_manager):
        super().__init__()
        self.theme_manager = theme_manager

        # Subscribe to theme changes
        self.theme_manager.theme_changed.connect(self._on_theme_changed)

    def _on_theme_changed(self, theme: str):
        self._apply_theme()  # React to theme change
```

**Used For**:
- Theme propagation (ThemeManager → all UI components)
- Control signals (ChartControls → ChartModule)
- Indicator signals (IndicatorPanel → ChartModule)
- Navigation signals (ModuleTile → HubWindow)

### Reusable Infrastructure Investment

**Chart Module Refactoring** (8 phases, completed):
- **Before**: 3,075 lines in 2 large files (price_chart.py 2,076 lines, chart_module.py 999 lines)
- **After**: 16 files, no file exceeds 600 lines
- **Extracted**: 1,325 lines of reusable components (BaseChart, axes, renderers, overlays)

**Return on Investment**:
- **Portfolio Chart**: ~50 lines (reuses 600+ lines of BaseChart)
- **Risk Analytics Chart**: ~40 lines (reuses BaseChart + axes)
- **Monte Carlo Chart**: ~40 lines (reuses BaseChart)
- **Efficiency Gain**: 12x reduction (50 lines vs 600+)

---

## 3. Directory Structure

Complete tree with inline explanations:

```
C:\Users\benja\Desktop\Quant-Terminal\
├── src/app/
│   │
│   ├── core/                              # Cross-cutting concerns
│   │   ├── config.py                      # Centralized app settings
│   │   │   - MODULE_SECTIONS: Registry of all modules by section
│   │   │   - Window defaults: 1400×900px, launches maximized
│   │   │   - Chart defaults: BTC-USD, daily, candles, log scale
│   │   │   - Tile layout: 3 cols, 453×285px, 20px spacing
│   │   │
│   │   └── theme_manager.py               # Theme switching (Dark, Light, Bloomberg)
│   │       - Signal-based theme propagation to all components
│   │       - Centralized stylesheet generation
│   │       - Provides: get_title_bar_stylesheet(), get_home_button_stylesheet(), etc.
│   │       - Default theme: Bloomberg (#0d1420 bg, #FF8000 accent)
│   │
│   ├── services/                          # GENERAL SERVICES ONLY (truly shared)
│   │   ├── market_data.py                 # Yahoo Finance data fetching
│   │   │   - fetch_price_history(ticker, interval, period) → DataFrame
│   │   │   - Interval conversion: daily→1d, weekly→1wk, monthly→1mo, yearly→1mo+resample
│   │   │   - Normalizes yfinance MultiIndex columns
│   │   │   - Handles missing data gracefully
│   │   │
│   │   ├── market_data_cache.py           # In-memory caching strategy
│   │   │   - 5-minute TTL
│   │   │   - clear_cache() for manual invalidation
│   │   │
│   │   ├── favorites_service.py           # Favorites persistence (singleton pattern)
│   │   │   - Saves to ~/.quant_terminal/favorites.json
│   │   │   - toggle_favorite(module_id)
│   │   │   - is_favorite(module_id) → bool
│   │   │   - get_all_favorites() → List[str]
│   │   │   - Class-level storage and methods
│   │   │
│   │   └── preferences_service.py         # User preferences (future)
│   │       - Window size, position, etc.
│   │
│   ├── ui/
│   │   ├── hub_window.py                  # Main application window
│   │   │   - Frameless window (Qt.FramelessWindowHint)
│   │   │   - Custom title bar (32px) with minimize, maximize, close
│   │   │   - Title bar dragging implementation
│   │   │   - Manages QStackedWidget for HomeScreen ↔ Modules
│   │   │   - Module container system: wraps modules with home button overlay
│   │   │   - Theme-aware title bar styling
│   │   │   - Launches maximized by default
│   │   │
│   │   ├── widgets/
│   │   │   │
│   │   │   ├── charting/                  # REUSABLE CHART INFRASTRUCTURE
│   │   │   │   │                          # (For ALL future chart modules)
│   │   │   │   │
│   │   │   │   ├── base_chart.py          # Foundation for all chart modules (~600 lines)
│   │   │   │   │   - Inherits from pg.GraphicsLayoutWidget
│   │   │   │   │   - Provides: PlotItem setup, ViewBox management
│   │   │   │   │   - Theme application (background, gridlines, crosshair)
│   │   │   │   │   - Event handlers: mouseMoveEvent, leaveEvent, resizeEvent
│   │   │   │   │   - View helpers: _get_visible_date_window(), _safe_set_yrange()
│   │   │   │   │   - Interface:
│   │   │   │   │       - set_theme(theme: str)
│   │   │   │   │       - set_x_axis(axis_item), set_y_axis(axis_item)
│   │   │   │   │       - plot_line(x, y, **kwargs)
│   │   │   │   │       - clear()
│   │   │   │   │   - Used by: PriceChart (current), PortfolioChart (future),
│   │   │   │   │                RiskChart (future), MonteCarloChart (future)
│   │   │   │   │
│   │   │   │   ├── axes/
│   │   │   │   │   ├── draggable_axis.py      # Base draggable axis (~90 lines)
│   │   │   │   │   │   - Click and drag to zoom/pan
│   │   │   │   │   │   - Inherits from pg.AxisItem
│   │   │   │   │   │
│   │   │   │   │   ├── price_axis.py          # Price formatting (~40 lines)
│   │   │   │   │   │   - Formats ticks as $1,234.56
│   │   │   │   │   │   - Inherits from DraggableAxisItem
│   │   │   │   │   │
│   │   │   │   │   └── date_index_axis.py     # Date formatting (~67 lines)
│   │   │   │   │       - Formats ticks as dates (Jan 2024, Q1 2024, 2024)
│   │   │   │   │       - Handles DatetimeIndex → numeric mapping
│   │   │   │   │       - Inherits from DraggableAxisItem
│   │   │   │   │
│   │   │   │   ├── renderers/
│   │   │   │   │   └── candlestick.py         # OHLC candlestick renderer (~88 lines)
│   │   │   │   │       - Inherits from pg.GraphicsObject
│   │   │   │   │       - Custom paint() for candlestick bars
│   │   │   │   │       - Configurable colors and width
│   │   │   │   │
│   │   │   │   └── overlays/
│   │   │   │       └── resize_handle.py       # Draggable resize handle (~100 lines)
│   │   │   │           - For oscillator subplot resizing
│   │   │   │           - Emits resize_requested(delta) signal
│   │   │   │           - Theme-aware styling
│   │   │   │
│   │   │   ├── navigation/                # MODULE NAVIGATION COMPONENTS
│   │   │   │   │
│   │   │   │   ├── home_screen.py             # Central navigation hub
│   │   │   │   │   - Combines section tabs + search bar + tile grid
│   │   │   │   │   - Settings button (top-right corner)
│   │   │   │   │   - Emits module_selected(module_id) signal
│   │   │   │   │   - Special behavior: Charting tab auto-opens Charts module
│   │   │   │   │
│   │   │   │   ├── module_tile.py             # Individual tile widget (453×285px)
│   │   │   │   │   - Screenshot preview (453×255px, 16:9)
│   │   │   │   │   - Star button (top-right, toggles favorite)
│   │   │   │   │   - Hover effect (border → theme accent color)
│   │   │   │   │   - Click emits tile_clicked(module_id) signal
│   │   │   │   │
│   │   │   │   ├── module_tile_grid.py        # 3-column grid layout
│   │   │   │   │   - Fixed 3 columns (TILE_COLS=3), 20px spacing
│   │   │   │   │   - Section filtering (shows modules from selected section)
│   │   │   │   │   - Search filtering (case-insensitive label match)
│   │   │   │   │   - Favorites-first sorting: (not is_favorite, label.lower())
│   │   │   │   │   - Horizontally centered grid
│   │   │   │   │
│   │   │   │   └── section_tab_bar.py         # Horizontal section tabs
│   │   │   │       - Tabs: Home, Charting, Crypto, Portfolio, Market Data, Analysis
│   │   │   │       - Home tab: default, shows all modules (unfiltered)
│   │   │   │       - Exclusive selection (one active at a time)
│   │   │   │       - Auto-return to Home: clicking active tab returns to Home
│   │   │   │       - Emits section_changed(section_name) signal
│   │   │   │
│   │   │   └── common/                    # SHARED WIDGETS (used by 3+ modules)
│   │   │       └── custom_message_box.py      # Theme-aware dialog boxes
│   │   │           - Frameless dialogs with custom title bar
│   │   │           - Question, Warning, Error, Info types
│   │   │           - Matches theme (Dark, Light, Bloomberg)
│   │   │
│   │   └── modules/
│   │       │
│   │       └── chart/                     # CHART MODULE (FULLY SELF-CONTAINED)
│   │           │                          # Example of module organization for future modules
│   │           │
│   │           ├── chart_module.py        # Main orchestrator (~400 lines)
│   │           │   - Connects: ChartControls → Services → PriceChart
│   │           │   - Manages: indicator application, ticker changes, theme updates
│   │           │   - Coordinates: main chart + oscillator subplot + depth panel
│   │           │   - Uses relative imports: from .services import ..., from .widgets import ...
│   │           │
│   │           ├── services/              # CHART-SPECIFIC SERVICES
│   │           │   │                      # (Not in global services/ - module-scoped pattern)
│   │           │   │
│   │           │   ├── indicator_service.py          # Technical indicators (~600 lines)
│   │           │   │   - 9 built-in: SMA, EMA, Bollinger, VWAP, RSI, MACD, ATR, Stochastic, OBV
│   │           │   │   - Custom indicator management (create, delete, load)
│   │           │   │   - Persistence: ~/.quant_terminal/custom_indicators.json
│   │           │   │   - calculate_indicator(name, data, params) → Series/DataFrame
│   │           │   │
│   │           │   ├── ticker_equation_parser.py     # Expression parser (~300 lines)
│   │           │   │   - Parses: =BTC-USD/SPX, =(BTC-USD+ETH-USD)/2, etc.
│   │           │   │   - Tokenizer → Shunting Yard → RPN evaluation
│   │           │   │   - Date alignment when combining multiple tickers
│   │           │   │   - Caching to avoid re-fetching same ticker
│   │           │   │
│   │           │   ├── chart_settings_manager.py     # Chart preferences persistence
│   │           │   │   - Saves: chart type, scale, indicator visibility
│   │           │   │   - Loads on module startup
│   │           │   │
│   │           │   ├── chart_theme_service.py        # Chart-specific stylesheets
│   │           │   │   - get_indicator_panel_stylesheet(theme) → str
│   │           │   │   - get_control_bar_stylesheet(theme) → str
│   │           │   │   - get_depth_panel_stylesheet(theme) → str
│   │           │   │
│   │           │   └── binance_data.py               # Order book depth data
│   │           │       - get_depth_summary(ticker, levels=500) → dict
│   │           │       - Supports Binance and Binance.US
│   │           │       - is_binance_ticker(ticker) → bool
│   │           │
│   │           ├── widgets/              # CHART-SPECIFIC WIDGETS
│   │           │   │                     # (Not in ui/widgets/ - module-scoped pattern)
│   │           │   │
│   │           │   ├── price_chart.py                # Financial price charts (~500 lines)
│   │           │   │   - Inherits from BaseChart (reuses 600 lines)
│   │           │   │   - OHLC/candlestick plotting
│   │           │   │   - Line chart plotting
│   │           │   │   - Log scale transforms
│   │           │   │   - Indicator overlay plotting
│   │           │   │   - set_prices(df, chart_type, scale)
│   │           │   │
│   │           │   ├── oscillator_pane.py            # Oscillator subplot
│   │           │   │   - Separate chart for RSI, MACD, Stochastic, etc.
│   │           │   │   - Uses ResizeHandle for draggable height adjustment
│   │           │   │   - Synchronized x-axis with main chart
│   │           │   │
│   │           │   ├── chart_controls.py             # Ticker/interval/type/scale controls
│   │           │   │   - Ticker input (supports equations)
│   │           │   │   - Interval selector (daily, weekly, monthly, yearly)
│   │           │   │   - Chart type toggle (candles, line)
│   │           │   │   - Scale toggle (regular, log)
│   │           │   │   - Settings button
│   │           │   │   - Emits: ticker_changed, interval_changed, chart_type_changed, etc.
│   │           │   │
│   │           │   ├── indicator_panel.py            # Indicator sidebar UI (~250 lines)
│   │           │   │   - Multi-select list of indicators
│   │           │   │   - Apply, Clear, Create, Edit, Delete buttons
│   │           │   │   - Emits: indicators_changed, create_clicked, etc.
│   │           │   │
│   │           │   ├── create_indicator_dialog.py    # Custom indicator creation dialog
│   │           │   │   - Input: name, type (overlay/oscillator), parameters
│   │           │   │   - Validation and persistence via IndicatorService
│   │           │   │   - Frameless dialog with custom title bar
│   │           │   │
│   │           │   ├── chart_settings_dialog.py      # Chart preferences dialog
│   │           │   │   - Configure: default ticker, interval, chart type, scale
│   │           │   │   - Persistence via ChartSettingsManager
│   │           │   │
│   │           │   ├── edit_plugin_appearance_dialog.py  # Indicator styling dialog
│   │           │   │   - Configure: color, line width, style
│   │           │   │   - Live preview
│   │           │   │
│   │           │   ├── depth_chart.py                # Order book depth chart
│   │           │   │   - Cumulative volume visualization
│   │           │   │   - Bid/ask areas with colors (green/red)
│   │           │   │   - Auto-ranging
│   │           │   │
│   │           │   └── order_book_ladder.py          # Order book ladder view
│   │           │       - Traditional ladder format (price levels)
│   │           │       - Real-time updates (500ms)
│   │           │       - Spread calculation
│   │           │
│   │           └── custom_indicators/    # PLUGIN SYSTEM (ABC pattern)
│   │               ├── base_indicator.py             # Abstract base class
│   │               │   - Defines interface: calculate(data) → Series/DataFrame
│   │               │   - Subclasses must implement calculate()
│   │               │
│   │               └── death_golden_cross.py         # Example plugin
│   │                   - Detects SMA(50) / SMA(200) crossovers
│   │                   - Shows buy/sell signals
│   │
│   └── utils/
│       ├── formatters.py                  # Number/date formatting helpers
│       │   - format_large_number(1234567) → "1.23M"
│       │   - format_price(1234.56) → "$1,234.56"
│       │
│       ├── validators.py                  # Input validation
│       │   - is_valid_ticker(ticker) → bool
│       │   - is_valid_equation(eq) → bool
│       │
│       └── screenshot_manager.py          # Module preview image generation
│           - Generates colored placeholders with emojis
│           - Storage: ~/.quant_terminal/screenshots/
│           - Section-based color coding
│           - 16:9 aspect ratio (453×255px)
│           - generate_screenshot(module_id, emoji, color)
│           - Lazy loading (only generates when tile displayed)
│
├── .venv/                                 # Python virtual environment
├── requirements.txt                       # Python dependencies
├── setup.py                               # Package setup
└── README.md                              # Project README
```

---

## 4. Module Development Guide

### Step-by-Step: Building a Portfolio Performance Module

This guide demonstrates the complete workflow for creating a new module using the established patterns.

#### Step 1: Plan Module Structure

Before writing code, design the module architecture:

```
modules/portfolio/
├── portfolio_module.py        # Main orchestrator
├── services/
│   ├── __init__.py
│   ├── portfolio_service.py   # Portfolio calculations (returns, Sharpe, drawdowns)
│   └── holdings_service.py    # Holdings management (CRUD operations)
└── widgets/
    ├── __init__.py
    ├── portfolio_chart.py     # Performance chart (inherits BaseChart)
    └── holdings_table.py      # Holdings table widget
```

**Decision**: Services handle business logic, widgets handle presentation, module orchestrates.

#### Step 2: Create Module Services

Create `modules/portfolio/services/portfolio_service.py`:

```python
"""Portfolio-specific business logic."""

from typing import List, Dict
import pandas as pd
import numpy as np

class PortfolioService:
    """Calculate portfolio metrics and returns."""

    @staticmethod
    def calculate_returns(holdings: List[Dict], prices: pd.DataFrame) -> pd.Series:
        """Calculate portfolio returns from holdings and price data.

        Args:
            holdings: List of {"ticker": str, "shares": float, "cost_basis": float}
            prices: DataFrame with tickers as columns, dates as index

        Returns:
            Series with daily portfolio returns
        """
        portfolio_value = pd.Series(index=prices.index, dtype=float)

        for date in prices.index:
            daily_value = 0
            for holding in holdings:
                ticker = holding["ticker"]
                shares = holding["shares"]
                if ticker in prices.columns:
                    daily_value += prices.loc[date, ticker] * shares
            portfolio_value.loc[date] = daily_value

        returns = portfolio_value.pct_change()
        return returns

    @staticmethod
    def calculate_sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.02) -> float:
        """Calculate Sharpe ratio.

        Args:
            returns: Daily returns series
            risk_free_rate: Annual risk-free rate (default 2%)

        Returns:
            Annualized Sharpe ratio
        """
        excess_returns = returns - (risk_free_rate / 252)  # Daily risk-free rate
        sharpe = np.sqrt(252) * excess_returns.mean() / excess_returns.std()
        return sharpe

    @staticmethod
    def calculate_max_drawdown(returns: pd.Series) -> float:
        """Calculate maximum drawdown.

        Args:
            returns: Daily returns series

        Returns:
            Maximum drawdown as decimal (e.g., 0.25 = 25% drawdown)
        """
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.cummax()
        drawdown = (cumulative - running_max) / running_max
        return drawdown.min()
```

Create `modules/portfolio/services/holdings_service.py`:

```python
"""Holdings management with persistence."""

from pathlib import Path
import json
from typing import List, Dict, Optional

class HoldingsService:
    """Manage portfolio holdings with JSON persistence."""

    _holdings_file = Path.home() / ".quant_terminal" / "holdings.json"

    @classmethod
    def initialize(cls):
        """Create holdings file if it doesn't exist."""
        cls._holdings_file.parent.mkdir(parents=True, exist_ok=True)
        if not cls._holdings_file.exists():
            cls._save_holdings([])

    @classmethod
    def load_holdings(cls) -> List[Dict]:
        """Load holdings from file."""
        if cls._holdings_file.exists():
            with open(cls._holdings_file, 'r') as f:
                return json.load(f)
        return []

    @classmethod
    def _save_holdings(cls, holdings: List[Dict]):
        """Save holdings to file."""
        with open(cls._holdings_file, 'w') as f:
            json.dump(holdings, f, indent=2)

    @classmethod
    def add_holding(cls, ticker: str, shares: float, cost_basis: float):
        """Add a new holding."""
        holdings = cls.load_holdings()
        holdings.append({
            "ticker": ticker,
            "shares": shares,
            "cost_basis": cost_basis
        })
        cls._save_holdings(holdings)

    @classmethod
    def remove_holding(cls, ticker: str):
        """Remove a holding by ticker."""
        holdings = cls.load_holdings()
        holdings = [h for h in holdings if h["ticker"] != ticker]
        cls._save_holdings(holdings)
```

Create `modules/portfolio/services/__init__.py`:

```python
"""Portfolio module services."""

from .portfolio_service import PortfolioService
from .holdings_service import HoldingsService

__all__ = ['PortfolioService', 'HoldingsService']
```

#### Step 3: Create Reusable Chart Widget

Create `modules/portfolio/widgets/portfolio_chart.py`:

```python
"""Portfolio performance chart inheriting from BaseChart."""

from PySide6.QtCore import Signal
import pandas as pd

from app.ui.widgets.charting.base_chart import BaseChart
from app.ui.widgets.charting.axes import DraggableAxisItem

class PortfolioChart(BaseChart):
    """Portfolio returns chart.

    Inherits 600 lines of BaseChart infrastructure:
    - PlotItem setup, ViewBox management
    - Background/gridline/crosshair handling
    - Theme application
    - Event handlers (mouseMoveEvent, leaveEvent, resizeEvent)
    - View helpers (_get_visible_date_window, _safe_set_yrange)
    """

    def __init__(self, theme_manager, parent=None):
        super().__init__(theme_manager, parent)

        # Custom percentage axis
        pct_axis = DraggableAxisItem(orientation='right')
        pct_axis.labelUnits = '%'
        pct_axis.setLabel('Cumulative Return', units='%')
        self.set_y_axis(pct_axis)

        # Store plot items for clearing
        self._portfolio_line = None
        self._benchmark_line = None

    def plot_returns(self, returns: pd.Series, benchmark_returns: pd.Series = None):
        """Plot cumulative returns.

        Args:
            returns: Daily returns series
            benchmark_returns: Optional benchmark (e.g., SPY) returns for comparison
        """
        # Clear previous plots
        self.clear()

        # Calculate cumulative returns
        cumulative = (1 + returns).cumprod() - 1

        # Plot portfolio line
        self._portfolio_line = self.plot_line(
            list(range(len(cumulative))),
            cumulative.values * 100,  # Convert to percentage
            pen='g',
            width=2,
            name='Portfolio'
        )

        # Plot benchmark if provided
        if benchmark_returns is not None:
            cumulative_benchmark = (1 + benchmark_returns).cumprod() - 1
            self._benchmark_line = self.plot_line(
                list(range(len(cumulative_benchmark))),
                cumulative_benchmark.values * 100,
                pen='b',
                width=2,
                name='Benchmark'
            )

        # Auto-range to fit data
        self.autoRange()
```

Create `modules/portfolio/widgets/holdings_table.py`:

```python
"""Holdings table widget."""

from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView
from PySide6.QtCore import Qt, Signal

class HoldingsTable(QTableWidget):
    """Table displaying portfolio holdings."""

    holding_selected = Signal(str)  # Emits ticker when row clicked

    def __init__(self, theme_manager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager

        # Table setup
        self.setColumnCount(4)
        self.setHorizontalHeaderLabels(['Ticker', 'Shares', 'Cost Basis', 'Current Value'])
        self.horizontalHeader().setStretchLastSection(True)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setSelectionMode(QTableWidget.SingleSelection)

        # Connect signals
        self.itemClicked.connect(self._on_item_clicked)
        self.theme_manager.theme_changed.connect(self._apply_theme)

        self._apply_theme()

    def _on_item_clicked(self, item):
        """Emit holding_selected signal with ticker."""
        row = item.row()
        ticker_item = self.item(row, 0)
        if ticker_item:
            self.holding_selected.emit(ticker_item.text())

    def set_holdings(self, holdings, prices):
        """Update table with holdings data.

        Args:
            holdings: List of {"ticker": str, "shares": float, "cost_basis": float}
            prices: Dict mapping ticker → current price
        """
        self.setRowCount(len(holdings))

        for i, holding in enumerate(holdings):
            ticker = holding["ticker"]
            shares = holding["shares"]
            cost_basis = holding["cost_basis"]
            current_price = prices.get(ticker, 0)
            current_value = shares * current_price

            self.setItem(i, 0, QTableWidgetItem(ticker))
            self.setItem(i, 1, QTableWidgetItem(f"{shares:.2f}"))
            self.setItem(i, 2, QTableWidgetItem(f"${cost_basis:.2f}"))
            self.setItem(i, 3, QTableWidgetItem(f"${current_value:.2f}"))

    def _apply_theme(self):
        """Apply current theme."""
        theme = self.theme_manager.current_theme

        if theme == "light":
            stylesheet = """
                QTableWidget {
                    background-color: #ffffff;
                    color: #000000;
                    gridline-color: #d0d0d0;
                }
                QHeaderView::section {
                    background-color: #f0f0f0;
                    color: #000000;
                    padding: 5px;
                    border: 1px solid #d0d0d0;
                }
            """
        elif theme == "bloomberg":
            stylesheet = """
                QTableWidget {
                    background-color: #0d1420;
                    color: #e8e8e8;
                    gridline-color: #1a2332;
                }
                QHeaderView::section {
                    background-color: #0a1018;
                    color: #FF8000;
                    padding: 5px;
                    border: 1px solid #1a2332;
                }
            """
        else:  # dark
            stylesheet = """
                QTableWidget {
                    background-color: #1e1e1e;
                    color: #ffffff;
                    gridline-color: #3a3a3a;
                }
                QHeaderView::section {
                    background-color: #2a2a2a;
                    color: #00d4ff;
                    padding: 5px;
                    border: 1px solid #3a3a3a;
                }
            """

        self.setStyleSheet(stylesheet)
```

Create `modules/portfolio/widgets/__init__.py`:

```python
"""Portfolio module widgets."""

from .portfolio_chart import PortfolioChart
from .holdings_table import HoldingsTable

__all__ = ['PortfolioChart', 'HoldingsTable']
```

#### Step 4: Create Main Module Widget

Create `modules/portfolio/portfolio_module.py`:

```python
"""Portfolio module - main orchestrator."""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
from PySide6.QtCore import Qt

from .widgets import PortfolioChart, HoldingsTable
from .services import PortfolioService, HoldingsService
from app.services.market_data import fetch_price_history

class PortfolioModule(QWidget):
    """Portfolio performance and holdings tracking."""

    def __init__(self, theme_manager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self.portfolio_service = PortfolioService()

        self._setup_ui()
        self._load_data()

        # Connect to theme changes
        self.theme_manager.theme_changed.connect(self._apply_theme)
        self._apply_theme()

    def _setup_ui(self):
        """Setup module UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Header with title and add button
        header = QHBoxLayout()
        title = QLabel("Portfolio Performance")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()

        add_btn = QPushButton("Add Holding")
        add_btn.clicked.connect(self._on_add_holding)
        header.addWidget(add_btn)

        layout.addLayout(header)

        # Performance chart (60% of space)
        self.chart = PortfolioChart(self.theme_manager)
        layout.addWidget(self.chart, stretch=3)

        # Holdings table (40% of space)
        self.holdings_table = HoldingsTable(self.theme_manager)
        self.holdings_table.holding_selected.connect(self._on_holding_selected)
        layout.addWidget(self.holdings_table, stretch=2)

    def _load_data(self):
        """Load portfolio data and update UI."""
        # Initialize holdings service
        HoldingsService.initialize()

        # Load holdings
        holdings = HoldingsService.load_holdings()

        if not holdings:
            # No holdings yet - show empty state
            return

        # Fetch prices for all tickers
        tickers = [h["ticker"] for h in holdings]
        prices_dict = {}
        all_prices_df = None

        for ticker in tickers:
            try:
                df = fetch_price_history(ticker, "daily", "1y")
                prices_dict[ticker] = df['Close'].iloc[-1]  # Latest price

                if all_prices_df is None:
                    all_prices_df = df[['Close']].rename(columns={'Close': ticker})
                else:
                    all_prices_df[ticker] = df['Close']
            except Exception as e:
                print(f"Error fetching {ticker}: {e}")
                prices_dict[ticker] = 0

        # Update holdings table
        self.holdings_table.set_holdings(holdings, prices_dict)

        # Calculate and plot returns
        if all_prices_df is not None:
            returns = self.portfolio_service.calculate_returns(holdings, all_prices_df)

            # Fetch benchmark (SPY)
            try:
                spy_df = fetch_price_history("SPY", "daily", "1y")
                benchmark_returns = spy_df['Close'].pct_change()
                self.chart.plot_returns(returns, benchmark_returns)
            except:
                self.chart.plot_returns(returns)

    def _on_add_holding(self):
        """Handle add holding button click."""
        # TODO: Open dialog to add holding
        # For now, just reload data
        self._load_data()

    def _on_holding_selected(self, ticker: str):
        """Handle holding selection in table."""
        print(f"Selected holding: {ticker}")
        # TODO: Show holding details or actions

    def _apply_theme(self):
        """Apply current theme."""
        theme = self.theme_manager.current_theme

        if theme == "light":
            bg_color = "#ffffff"
            text_color = "#000000"
        elif theme == "bloomberg":
            bg_color = "#0d1420"
            text_color = "#e8e8e8"
        else:  # dark
            bg_color = "#1e1e1e"
            text_color = "#ffffff"

        self.setStyleSheet(f"""
            QWidget {{
                background-color: {bg_color};
                color: {text_color};
            }}
        """)
```

#### Step 5: Register in Module Registry

Edit `core/config.py`:

```python
MODULE_SECTIONS = {
    "Charting": [
        {"id": "charts", "label": "Charts", "emoji": "📈"}
    ],
    "Crypto": [
        {"id": "crypto_dashboard", "label": "Crypto Dashboard", "emoji": "₿"},
        {"id": "defi", "label": "DeFi", "emoji": "🪙"},
        {"id": "nft_tracker", "label": "NFT Tracker", "emoji": "🖼️"}
    ],
    "Portfolio": [
        {"id": "portfolio", "label": "Portfolio", "emoji": "💼"},  # ← NOW IMPLEMENTED
        {"id": "watchlist", "label": "Watchlist", "emoji": "👁️"}
    ],
    # ... other sections
}
```

#### Step 6: Register in main.py

Edit `main.py`:

```python
# ... existing imports ...
from app.ui.modules.chart.chart_module import ChartModule
from app.ui.modules.portfolio.portfolio_module import PortfolioModule  # ← ADD THIS

def main():
    app = QApplication(sys.argv)

    # Initialize services
    FavoritesService.initialize()

    # Initialize ThemeManager
    theme_manager = ThemeManager()
    theme_manager.set_theme("bloomberg")

    # Create HubWindow
    hub = HubWindow(theme_manager, FavoritesService)

    # Add modules
    hub.add_module("charts", ChartModule(theme_manager))
    hub.add_module("portfolio", PortfolioModule(theme_manager))  # ← ADD THIS

    # ... add other modules ...

    hub.showMaximized()
    sys.exit(app.exec())
```

#### Step 7: Generate Screenshot

The ScreenshotManager will auto-generate a screenshot on first load. To manually generate:

```python
from app.utils.screenshot_manager import ScreenshotManager

ScreenshotManager.generate_screenshot(
    module_id="portfolio",
    emoji="💼",
    color="#4CAF50"  # Green for portfolio
)
```

#### Module Development Checklist

Use this checklist for every new module:

- [ ] **Plan structure** (services, widgets) - Decide responsibilities
- [ ] **Create module directory**: `modules/{module_name}/`
- [ ] **Create services** in `modules/{module_name}/services/`
  - [ ] Business logic (calculations, data processing)
  - [ ] Persistence (if needed)
  - [ ] Create `__init__.py` for clean imports
- [ ] **Create widgets** in `modules/{module_name}/widgets/`
  - [ ] Reusable components (inherit from BaseChart if chart module)
  - [ ] Module-specific UI widgets
  - [ ] Create `__init__.py` for clean imports
- [ ] **Create main module widget** (orchestrator)
  - [ ] Inherit from QWidget
  - [ ] Compose services + widgets
  - [ ] Connect to `theme_changed` signal
  - [ ] Implement `_apply_theme()` method
- [ ] **Register in `core/config.py`** MODULE_SECTIONS
- [ ] **Register in `main.py`** via `hub.add_module()`
- [ ] **Test theme switching** (Dark ↔ Light ↔ Bloomberg)
- [ ] **Generate screenshot** (auto or manual)
- [ ] **Test navigation**
  - [ ] Tile click opens module
  - [ ] Home button returns to home screen
  - [ ] Favorite toggle persists

### Code Reduction Example

**Without Reusable Infrastructure** (old approach):
```python
class PortfolioChart(QWidget):
    # 600+ lines: PlotItem setup, ViewBox, theme handling, events, helpers
    # + 50 lines: Portfolio-specific logic
    # = 650+ lines total
```

**With Reusable Infrastructure** (current approach):
```python
class PortfolioChart(BaseChart):
    # 50 lines: Portfolio-specific logic only
    # Inherits 600 lines from BaseChart
    # = 50 lines written, 650 lines functionality
```

**Result**: 12x reduction in code written (50 vs 600+)

---

## 5. Reusable Components Documentation

### BaseChart Infrastructure

**Purpose**: Provide core chart functionality for ALL chart modules (Portfolio, Risk Analytics, Monte Carlo, DCF Valuation, etc.)

**Location**: `ui/widgets/charting/base_chart.py`

**What BaseChart Provides** (~600 lines):

1. **PlotItem and ViewBox Setup**
   - `pg.GraphicsLayoutWidget` initialization
   - PlotItem creation and configuration
   - ViewBox mouse mode setup (RectMode for panning)

2. **Background and Styling**
   - Theme-aware background colors
   - Grid line configuration (alpha, style)
   - Crosshair setup and styling

3. **Theme Application**
   - `set_theme(theme: str)` method
   - Dynamic background color updates
   - Grid and crosshair color updates

4. **Event Handlers**
   - `mouseMoveEvent`: Crosshair tracking
   - `leaveEvent`: Hide crosshair when mouse leaves
   - `resizeEvent`: Maintain layout on window resize

5. **View Helpers**
   - `_get_visible_date_window()`: Get currently visible x-range
   - `_safe_set_yrange(min, max)`: Set y-range with error handling
   - `autoRange()`: Auto-fit data to view

6. **Interface Methods**
   - `set_x_axis(axis_item)`: Set custom x-axis
   - `set_y_axis(axis_item, position="right")`: Set custom y-axis
   - `plot_line(x, y, **kwargs)`: Plot a line with customization
   - `clear()`: Clear all plot items

**Usage Pattern**:

```python
from app.ui.widgets.charting.base_chart import BaseChart
from app.ui.widgets.charting.axes import PriceAxisItem, DateIndexAxisItem

class MyChart(BaseChart):
    def __init__(self, theme_manager, parent=None):
        super().__init__(theme_manager, parent)

        # Customize axes (optional)
        price_axis = PriceAxisItem(orientation='right')
        date_axis = DateIndexAxisItem(orientation='bottom', data_index=df.index)
        self.set_y_axis(price_axis)
        self.set_x_axis(date_axis)

        # Add custom event handlers (optional)
        # self.plot_item.scene().sigMouseMoved.connect(self._custom_mouse_handler)

    def plot_data(self, data):
        """Module-specific plotting logic."""
        self.plot_line(x, y, pen='b', name='My Data')
```

**Efficiency Gain**: Write ~50 lines instead of 600+ for each chart module

**Used By**:
- `PriceChart` (current) - Financial OHLC charts
- `PortfolioChart` (future) - Cumulative returns
- `RiskChart` (future) - VaR, CVaR, drawdowns
- `MonteCarloChart` (future) - Simulation paths
- `CorrelationChart` (future) - Correlation matrices

### Axis Components

#### DraggableAxisItem

**Location**: `ui/widgets/charting/axes/draggable_axis.py` (~90 lines)

**Purpose**: Base axis with click-and-drag zoom/pan functionality

**Features**:
- Inherits from `pg.AxisItem`
- Click and drag to zoom (vertical drag = zoom in/out)
- Base class for price, date, and custom axes

**Usage**:
```python
from app.ui.widgets.charting.axes import DraggableAxisItem

custom_axis = DraggableAxisItem(orientation='left')
custom_axis.setLabel('Custom Metric', units='units')
self.set_y_axis(custom_axis, position='left')
```

#### PriceAxisItem

**Location**: `ui/widgets/charting/axes/price_axis.py` (~40 lines)

**Purpose**: Price formatting with $ and thousands separators

**Features**:
- Formats ticks as `$1,234.56`
- Inherits draggable functionality from DraggableAxisItem

**Usage**:
```python
from app.ui.widgets.charting.axes import PriceAxisItem

price_axis = PriceAxisItem(orientation='right')
self.set_y_axis(price_axis)
```

**Output**: Axis labels appear as `$1,234.56`, `$2,345.67`, etc.

#### DateIndexAxisItem

**Location**: `ui/widgets/charting/axes/date_index_axis.py` (~67 lines)

**Purpose**: Date formatting with smart granularity (2024, Q1 2024, Jan 2024, Jan 15)

**Features**:
- Maps DatetimeIndex to numeric x-coordinates
- Smart date formatting based on zoom level
- Inherits draggable functionality

**Usage**:
```python
from app.ui.widgets.charting.axes import DateIndexAxisItem

date_axis = DateIndexAxisItem(orientation='bottom', data_index=df.index)
self.set_x_axis(date_axis)
```

**Output**: Axis labels appear as dates with appropriate granularity based on visible range

### Renderers

#### CandlestickItem

**Location**: `ui/widgets/charting/renderers/candlestick.py` (~88 lines)

**Purpose**: Render OHLC candlestick bars

**Features**:
- Inherits from `pg.GraphicsObject`
- Custom `paint()` method for candlestick drawing
- Configurable colors (bullish green, bearish red)
- Configurable bar width

**Usage**:
```python
from app.ui.widgets.charting.renderers.candlestick import CandlestickItem

# Prepare OHLC data
ohlc_data = [(x, open, high, low, close), ...]

candlestick = CandlestickItem(ohlc_data)
self.plot_item.addItem(candlestick)
```

**Rendering**: Draws OHLC bars with wicks (high/low) and bodies (open/close)

### Overlays

#### ResizeHandle

**Location**: `ui/widgets/charting/overlays/resize_handle.py` (~100 lines)

**Purpose**: Draggable resize handle for split panes

**Features**:
- Horizontal or vertical orientation
- Emits `resize_requested(delta)` signal when dragged
- Theme-aware styling (hover effects)
- Cursor changes on hover

**Usage**:
```python
from app.ui.widgets.charting.overlays.resize_handle import ResizeHandle

resize_handle = ResizeHandle(orientation='horizontal')
resize_handle.resize_requested.connect(self._on_resize)

def _on_resize(self, delta):
    # Adjust split pane sizes based on delta
    new_height = current_height + delta
    self.main_chart.setFixedHeight(new_height)
```

**Used In**: OscillatorPane (chart module) to resize oscillator subplot

### Navigation Components

#### HomeScreen

**Location**: `ui/widgets/navigation/home_screen.py`

**Purpose**: Central navigation hub combining section tabs, search bar, and tile grid

**Features**:
- Section tabs (Home, Charting, Crypto, Portfolio, Market Data, Analysis)
- Centered search bar (926px width = 2 tiles)
- Module tile grid with favorites-first sorting
- Settings button (top-right corner)
- Emits `module_selected(module_id)` signal

**Signals**:
- `module_selected(str)`: Emitted when tile clicked or section auto-opens module

**Special Behavior**: Clicking "Charting" tab auto-opens Charts module (single-module section)

#### ModuleTile

**Location**: `ui/widgets/navigation/module_tile.py`

**Purpose**: Individual tile widget for a module

**Size**: 453×285px (453×255 screenshot + 30px label)

**Features**:
- Screenshot preview from ScreenshotManager
- Star button (top-right corner)
- Hover effect (border → theme accent color)
- Click emits `tile_clicked(module_id)` signal
- Star click toggles favorite via FavoritesService

**Theme-Aware**: Border hover color matches theme accent (cyan/blue/orange)

#### ModuleTileGrid

**Location**: `ui/widgets/navigation/module_tile_grid.py`

**Purpose**: Grid layout for module tiles with filtering and sorting

**Layout**: 3 columns, 20px spacing, horizontally centered

**Features**:
- Section filtering: `set_section(section_name)` shows only modules from that section
- Search filtering: `set_search_filter(query)` matches against module labels (case-insensitive)
- Favorites-first sorting: `(not is_favorite, label.lower())`
- Auto-refresh on favorite toggle

**Usage**:
```python
from app.ui.widgets.navigation import ModuleTileGrid

grid = ModuleTileGrid(theme_manager)
grid.tile_clicked.connect(self._on_tile_clicked)

# Filter by section
grid.set_section("Portfolio")

# Filter by search
grid.set_search_filter("port")  # Shows "Portfolio" tile
```

#### SectionTabBar

**Location**: `ui/widgets/navigation/section_tab_bar.py`

**Purpose**: Horizontal tab bar for filtering modules by section

**Tabs**: Home, Charting, Crypto, Portfolio, Market Data, Analysis

**Features**:
- Home tab: default selected, shows all modules (unfiltered view)
- Exclusive selection: only one tab active at a time
- Auto-return to Home: clicking active tab again returns to Home view
- Centered layout with stretch on both sides
- Emits `section_changed(section_name)` signal

**Signal**: `section_changed(str)` - Emitted when tab clicked (section name or "Home" for all)

---

## 6. Code Conventions

### Import Patterns

#### Module-Scoped Relative Imports

**Within module widgets**:
```python
# modules/chart/widgets/indicator_panel.py
from ..services import IndicatorService, ChartThemeService
from .oscillator_pane import OscillatorPane
```

**Within module main file**:
```python
# modules/chart/chart_module.py
from .services import (
    TickerEquationParser,
    IndicatorService,
    ChartSettingsManager,
    ChartThemeService,
    BinanceOrderBook
)
from .widgets import PriceChart, ChartControls, IndicatorPanel
```

#### Cross-Module Imports

**Importing from global services**:
```python
from app.services.market_data import fetch_price_history, clear_cache
from app.services.favorites_service import FavoritesService
```

**Importing from another module** (rare - modules should be independent):
```python
# Only if absolutely necessary
from app.ui.modules.chart.services import IndicatorService
```

#### Reusable Components

**Charting infrastructure**:
```python
from app.ui.widgets.charting.base_chart import BaseChart
from app.ui.widgets.charting.axes import PriceAxisItem, DateIndexAxisItem, DraggableAxisItem
from app.ui.widgets.charting.renderers.candlestick import CandlestickItem
from app.ui.widgets.charting.overlays.resize_handle import ResizeHandle
```

**Navigation**:
```python
from app.ui.widgets.navigation import HomeScreen, ModuleTile, ModuleTileGrid, SectionTabBar
```

**Common**:
```python
from app.ui.widgets.common import CustomMessageBox
```

### Type Hints

**Use type hints for all public functions and methods**:

```python
from typing import List, Dict, Optional, Tuple
import pandas as pd

def fetch_price_history(ticker: str, interval: str, period: str = "max") -> pd.DataFrame:
    """Fetch OHLCV data for ticker."""
    ...

def calculate_sma(prices: pd.Series, period: int) -> pd.Series:
    """Calculate Simple Moving Average."""
    ...

class IndicatorService:
    @staticmethod
    def create_custom_indicator(
        name: str,
        indicator_type: str,
        parameters: Dict[str, any]
    ) -> Optional[Dict]:
        """Create and save custom indicator.

        Args:
            name: Indicator name
            indicator_type: 'overlay' or 'oscillator'
            parameters: Dict of parameter_name → value

        Returns:
            Created indicator dict or None if validation failed
        """
        ...
```

**Generic types**:
```python
from typing import List, Dict, Tuple, Optional, Union, Any

# Lists
def get_tickers() -> List[str]:
    return ["BTC-USD", "ETH-USD"]

# Dictionaries
def get_prices() -> Dict[str, float]:
    return {"BTC-USD": 50000.0}

# Tuples (fixed size)
def get_ohlc() -> Tuple[float, float, float, float]:
    return (100.0, 105.0, 98.0, 103.0)

# Optional (can be None)
def find_indicator(name: str) -> Optional[Dict]:
    return indicator if found else None

# Union (multiple types)
def process_data(data: Union[pd.Series, pd.DataFrame]) -> pd.DataFrame:
    ...
```

### Documentation

#### When to Add Docstrings

**✅ DO add docstrings for**:
- Business logic (services)
- Complex algorithms (RPN evaluation, date alignment)
- Public APIs (module interfaces)
- Reusable components (BaseChart, axes, renderers)

**❌ DO NOT add docstrings for**:
- Simple UI setup (`_setup_ui` with obvious widget creation)
- Getters/setters
- Obvious widgets (creating a `QPushButton` labeled "Submit")

#### Docstring Style

**One-line for simple functions**:
```python
def clear_cache():
    """Clear the market data cache."""
    _cache.clear()
```

**Multi-line for complex functions**:
```python
def parse_equation(equation: str) -> pd.Series:
    """Parse ticker equation and return evaluated result.

    Supports mathematical expressions with tickers:
    - =BTC-USD (single ticker)
    - =BTC-USD/SPX (ratio)
    - =(BTC-USD+ETH-USD)/2 (average)

    Args:
        equation: Mathematical expression with tickers (must start with =)

    Returns:
        Pandas Series with evaluated result, indexed by date

    Raises:
        ValueError: If equation syntax is invalid
        KeyError: If ticker not found

    Example:
        >>> parse_equation("=BTC-USD/SPX")
        2024-01-01    0.5234
        2024-01-02    0.5312
        dtype: float64
    """
    ...
```

### Qt Conventions

#### Signals

**Use snake_case for signal names**:
```python
from PySide6.QtCore import Signal

class MyWidget(QWidget):
    # Signals
    theme_changed = Signal(str)          # Emits theme name
    ticker_updated = Signal(str)         # Emits ticker symbol
    indicator_applied = Signal(list)     # Emits list of indicator names
    data_loaded = Signal()               # No arguments
```

#### Slots

**Prefix slot methods with `_on_`**:
```python
def _on_theme_changed(self, theme: str):
    """Handle theme change."""
    self._apply_theme()

def _on_ticker_changed(self, ticker: str):
    """Handle ticker change."""
    self._load_data(ticker)

def _on_button_clicked(self):
    """Handle button click."""
    self._process_action()
```

#### Private Widgets

**Prefix private widget attributes with `_`**:
```python
class ChartModule(QWidget):
    def __init__(self, theme_manager):
        super().__init__()

        # Private widgets
        self._chart_widget = PriceChart(theme_manager)
        self._control_bar = ChartControls(theme_manager)
        self._indicator_panel = IndicatorPanel(theme_manager)

        # Public widgets (rare - only if other classes need direct access)
        self.status_label = QLabel("Ready")
```

#### Layout Organization

**Standard pattern**:
```python
def _setup_ui(self):
    """Setup module UI."""
    layout = QVBoxLayout(self)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(10)

    # Header
    header = self._create_header()
    layout.addWidget(header)

    # Main content
    self._chart_widget = PriceChart(self.theme_manager)
    layout.addWidget(self._chart_widget, stretch=1)

    # Footer / controls
    controls = self._create_controls()
    layout.addWidget(controls)
```

### File Naming

**Modules**: `{module_name}_module.py`
- `chart_module.py`
- `portfolio_module.py`
- `risk_analytics_module.py`

**Widgets**: `{widget_name}.py`
- `price_chart.py`
- `holdings_table.py`
- `indicator_panel.py`

**Services**: `{service_name}.py`
- `indicator_service.py`
- `portfolio_service.py`
- `market_data.py`

**Dialogs**: `{dialog_name}_dialog.py`
- `chart_settings_dialog.py`
- `create_indicator_dialog.py`
- `add_holding_dialog.py`

**One class per file** (with rare exceptions for tightly coupled helper classes)

### Naming Conventions

**Classes**: PascalCase
```python
class PortfolioModule(QWidget):
class IndicatorService:
class PriceAxisItem(DraggableAxisItem):
class ChartSettingsDialog(QDialog):
```

**Functions/Methods**: snake_case
```python
def fetch_price_history():
def calculate_returns():
def _apply_theme():
def _on_button_clicked():
```

**Constants**: UPPER_SNAKE_CASE
```python
DEFAULT_TICKER = "BTC-USD"
TILE_WIDTH = 453
TILE_HEIGHT = 285
MAX_INDICATORS = 10
```

**Private Methods/Attributes**: prefix with `_`
```python
def _setup_ui(self):
def _load_data(self):
self._chart_widget = None
self._current_ticker = "BTC-USD"
```

**Module-Level "Constants"** (actually config variables):
```python
# Good - clearly constants
WINDOW_WIDTH = 1400
WINDOW_HEIGHT = 900

# Avoid - mutable, not a constant
_cache = {}  # Use this for module-level state
```

---

## 7. UI/UX Design Guidelines

### Custom Title Bar Pattern

**All windows and dialogs use frameless design with custom title bars for complete theme control**

#### Why Frameless?

OS-controlled title bars cannot be styled (colors, borders, fonts are OS-dependent). Frameless windows with custom title bars enable:
- Complete theme integration (Dark, Light, Bloomberg)
- Consistent styling across all platforms (Windows, macOS, Linux)
- Custom controls and branding

#### Implementation for Dialogs

**Full Example**:

```python
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QMouseEvent

class CustomDialog(QDialog):
    """Dialog with frameless window and custom title bar."""

    def __init__(self, theme_manager, parent=None):
        super().__init__(parent)
        self.setModal(True)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.theme_manager = theme_manager
        self._drag_pos = QPoint()  # For window dragging

        self._setup_ui()
        self._apply_theme()

        # Connect to theme changes
        self.theme_manager.theme_changed.connect(self._apply_theme)

    def _setup_ui(self):
        """Setup dialog with custom title bar."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Custom title bar
        self.title_bar = self._create_title_bar("Dialog Title")
        layout.addWidget(self.title_bar)

        # Content container
        content = QWidget()
        content.setObjectName("dialogContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(15, 15, 15, 15)

        # Add content widgets here...
        label = QLabel("Dialog content goes here")
        content_layout.addWidget(label)

        layout.addWidget(content)

    def _create_title_bar(self, title: str) -> QWidget:
        """Create custom title bar with close button."""
        title_bar = QWidget()
        title_bar.setObjectName("titleBar")
        title_bar.setFixedHeight(32)

        bar_layout = QHBoxLayout(title_bar)
        bar_layout.setContentsMargins(10, 0, 5, 0)
        bar_layout.setSpacing(5)

        # Dialog title
        title_label = QLabel(title)
        title_label.setObjectName("titleLabel")
        bar_layout.addWidget(title_label)
        bar_layout.addStretch()

        # Close button
        close_btn = QPushButton("✕")
        close_btn.setObjectName("titleBarCloseButton")
        close_btn.setFixedSize(40, 32)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.reject)
        bar_layout.addWidget(close_btn)

        # Enable dragging
        title_bar.mousePressEvent = self._title_bar_mouse_press
        title_bar.mouseMoveEvent = self._title_bar_mouse_move

        return title_bar

    def _title_bar_mouse_press(self, event: QMouseEvent) -> None:
        """Handle mouse press for dragging."""
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def _title_bar_mouse_move(self, event: QMouseEvent) -> None:
        """Handle mouse move for dragging."""
        if event.buttons() == Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def _apply_theme(self):
        """Apply current theme."""
        theme = self.theme_manager.current_theme

        if theme == "light":
            stylesheet = self._get_light_stylesheet()
        elif theme == "bloomberg":
            stylesheet = self._get_bloomberg_stylesheet()
        else:
            stylesheet = self._get_dark_stylesheet()

        self.setStyleSheet(stylesheet)

    def _get_dark_stylesheet(self) -> str:
        return """
            #titleBar {
                background-color: #2a2a2a;
                border-bottom: 1px solid #3a3a3a;
            }
            #titleLabel {
                background-color: transparent;  /* CRITICAL */
                color: #ffffff;
                font-size: 13px;
                font-weight: 500;
            }
            #titleBarCloseButton {
                background-color: transparent;
                color: #ffffff;
                border: none;
                font-size: 14px;
                font-weight: bold;
            }
            #titleBarCloseButton:hover {
                background-color: #d32f2f;  /* Red on all themes */
                color: #ffffff;
            }
            #dialogContent {
                background-color: #1e1e1e;
                color: #ffffff;
            }
        """

    def _get_light_stylesheet(self) -> str:
        return """
            #titleBar {
                background-color: #f0f0f0;
                border-bottom: 1px solid #d0d0d0;
            }
            #titleLabel {
                background-color: transparent;  /* CRITICAL */
                color: #000000;
                font-size: 13px;
                font-weight: 500;
            }
            #titleBarCloseButton {
                background-color: transparent;
                color: #000000;
                border: none;
                font-size: 14px;
                font-weight: bold;
            }
            #titleBarCloseButton:hover {
                background-color: #d32f2f;  /* Red on all themes */
                color: #ffffff;
            }
            #dialogContent {
                background-color: #ffffff;
                color: #000000;
            }
        """

    def _get_bloomberg_stylesheet(self) -> str:
        return """
            #titleBar {
                background-color: #0a1018;
                border-bottom: 2px solid #FF8000;
            }
            #titleLabel {
                background-color: transparent;  /* CRITICAL */
                color: #FF8000;
                font-size: 13px;
                font-weight: 500;
            }
            #titleBarCloseButton {
                background-color: transparent;
                color: #e8e8e8;
                border: none;
                font-size: 14px;
                font-weight: bold;
            }
            #titleBarCloseButton:hover {
                background-color: #d32f2f;  /* Red on all themes */
                color: #ffffff;
            }
            #dialogContent {
                background-color: #0d1420;
                color: #e8e8e8;
            }
        """
```

**Critical Requirements**:
- `setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)` for dialogs
- `setWindowFlags(Qt.FramelessWindowHint)` for main windows
- Title label must have `background-color: transparent` in ALL themes
- Close button turns red (`#d32f2f`) on hover across ALL themes
- For main windows, add minimize and maximize buttons (dialogs only have close)
- Implement title bar dragging via `mousePressEvent` and `mouseMoveEvent`

### Transparent Overlays with Widget Masking

**Critical for home button overlays on modules**

#### Why Masking Instead of Event Forwarding?

Qt's `:hover` pseudo-state detection is based on **physical z-order hierarchy**. Even if you forward `MouseMove` events to a button, Qt won't activate the button's `:hover` state if another widget (the overlay) is physically positioned above it in the z-order.

**Event Forwarding (doesn't work for `:hover`)**:
```python
# ❌ This forwards events but doesn't activate :hover
def mouseMoveEvent(self, event):
    self.button.mouseMoveEvent(event)  # Button receives event
    # But Qt still sees overlay on top → no :hover activation
```

**Widget Masking (works for `:hover`)**:
```python
# ✅ This makes overlay transparent in unmasked areas
def _update_mask(self):
    button_rect = self._home_button.geometry()
    region = QRegion(button_rect)
    self.setMask(region)  # Overlay only "exists" in button area
    # Qt sees button directly → :hover activates
```

#### Implementation Pattern

**Complete Example**:

```python
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QRegion

class TransparentOverlay(QWidget):
    """Transparent overlay with widget masking for proper :hover detection."""

    def __init__(self, parent=None):
        super().__init__(parent)

        # Critical: Set size policy to fill container
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Critical: Set transparent background
        self.setStyleSheet("background: transparent;")

        # Store home button reference
        self._home_button = None

    def set_home_button(self, button):
        """Set the home button and update mask."""
        self._home_button = button

        # Install event filter to watch for button move/resize
        button.installEventFilter(self)

        # Initial mask update
        self._update_mask()

    def _update_mask(self):
        """Update the mask to only include the home button area.

        This makes the overlay physically transparent in unmasked areas,
        allowing widgets below to receive events directly from Qt.
        """
        if not self._home_button:
            return

        button_rect = self._home_button.geometry()
        region = QRegion(button_rect)
        self.setMask(region)  # Overlay only "exists" in this rectangle

    def eventFilter(self, obj, event):
        """Update mask when home button is moved or resized."""
        if obj == self._home_button:
            if event.type() in (QEvent.Move, QEvent.Resize):
                self._update_mask()
        return super().eventFilter(obj, event)

    def resizeEvent(self, event):
        """Update mask when overlay is resized."""
        super().resizeEvent(event)
        self._update_mask()
```

**Usage in HubWindow**:

```python
from PySide6.QtWidgets import QStackedLayout

class HubWindow(QWidget):
    def _create_module_container(self, module_widget):
        """Wrap module with transparent home button overlay."""
        container = QWidget()
        stack = QStackedLayout(container)
        stack.setStackingMode(QStackedLayout.StackAll)  # Overlay mode

        # Add module (bottom layer)
        stack.addWidget(module_widget)

        # Add transparent overlay (top layer)
        overlay = TransparentOverlay()
        stack.addWidget(overlay)

        # Create home button
        home_button = QPushButton("Home")
        home_button.setParent(overlay)
        home_button.setGeometry(10, 10, 100, 40)  # Top-left corner
        home_button.clicked.connect(self._return_to_home)

        # Set home button and update mask
        overlay.set_home_button(home_button)

        return container
```

**Key Points**:
- `setMask(QRegion)` makes overlay physically transparent in unmasked areas
- Event filter updates mask dynamically when button moves/resizes
- `resizeEvent` updates mask when overlay resizes
- Works because Qt sees button directly in unmasked areas → `:hover` activates

### Theme Awareness

**All UI components must respond to theme changes**

#### Pattern

```python
from PySide6.QtWidgets import QWidget

class MyWidget(QWidget):
    def __init__(self, theme_manager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager

        self._setup_ui()
        self._apply_theme()

        # Connect to theme changes
        self.theme_manager.theme_changed.connect(self._apply_theme)

    def _apply_theme(self):
        """Apply current theme."""
        theme = self.theme_manager.current_theme

        if theme == "light":
            stylesheet = self._get_light_stylesheet()
        elif theme == "bloomberg":
            stylesheet = self._get_bloomberg_stylesheet()
        else:  # dark
            stylesheet = self._get_dark_stylesheet()

        self.setStyleSheet(stylesheet)

    def _get_dark_stylesheet(self) -> str:
        return """
            QWidget {
                background-color: #1e1e1e;
                color: #ffffff;
            }
            QPushButton {
                background-color: transparent;
                color: #00d4ff;  /* Dark theme accent */
                border: 1px solid transparent;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: rgba(0, 212, 255, 0.15);
                border: 1px solid #00d4ff;
            }
        """

    def _get_light_stylesheet(self) -> str:
        return """
            QWidget {
                background-color: #ffffff;
                color: #000000;
            }
            QPushButton {
                background-color: transparent;
                color: #0066cc;  /* Light theme accent */
                border: 1px solid transparent;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: rgba(0, 102, 204, 0.15);
                border: 1px solid #0066cc;
            }
        """

    def _get_bloomberg_stylesheet(self) -> str:
        return """
            QWidget {
                background-color: #0d1420;
                color: #e8e8e8;
            }
            QPushButton {
                background-color: transparent;
                color: #FF8000;  /* Bloomberg theme accent */
                border: 1px solid transparent;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: rgba(255, 128, 0, 0.15);
                border: 1px solid #FF8000;
            }
        """
```

**Theme Accent Colors**:
- **Dark**: Cyan `#00d4ff`
- **Light**: Blue `#0066cc`
- **Bloomberg**: Orange `#FF8000`

### Button Styling Standard

**All buttons use transparent styling with hover highlights**

**Automatic via ThemeManager** - No custom stylesheets needed on individual buttons

**States**:
- **Default**: Transparent background, transparent border
- **Hover**: 15% opacity theme-colored background, solid theme-colored border
- **Pressed**: Solid theme-colored background, inverted text color
- **Checked** (toggle buttons): Solid theme-colored background, inverted text color (same as pressed)
- **Disabled**: 40% opacity

**Implementation**:

ThemeManager applies this automatically to all `QPushButton` widgets. Just create buttons normally:

```python
btn = QPushButton("My Button")
# No custom stylesheet needed - ThemeManager handles it
```

**Toggle Buttons**:

```python
btn = QPushButton("Indicators")
btn.setCheckable(True)  # Checked state shows solid background
btn.setChecked(True)
```

**No Emojis**: Button text should be clean (e.g., "Settings" not "⚙️ Settings")

### Tile-Based Navigation

**Module tiles follow consistent sizing and behavior**

**Specifications**:
- **Tile Size**: 453×285px
  - Screenshot: 453×255px (16:9 aspect ratio)
  - Label: 30px height
- **Grid Layout**: 3 columns, 20px spacing, horizontally centered
- **Star Button**: Top-right corner, 32×32px, transparent background
- **Hover Effect**: Border changes to theme accent color
- **Click Behavior**: Opens module full-screen

**Favorites-First Sorting**:

Sort key: `(not is_favorite, label.lower())`
- `False < True` in Python, so `not is_favorite` puts favorites (False) before non-favorites (True)
- Then alphabetical by label (case-insensitive)

**Example**:
```
Favorites:
  1. Charts (favorited)
  2. Portfolio (favorited)

Non-Favorites:
  3. Analysis
  4. Crypto Dashboard
  5. DeFi
  ...
```

### Section Organization

**Modules are grouped under logical sections**

Defined in `core/config.py`:

```python
MODULE_SECTIONS = {
    "Charting": [
        {"id": "charts", "label": "Charts", "emoji": "📈"}
    ],
    "Crypto": [
        {"id": "crypto_dashboard", "label": "Crypto Dashboard", "emoji": "₿"},
        {"id": "defi", "label": "DeFi", "emoji": "🪙"},
        {"id": "nft_tracker", "label": "NFT Tracker", "emoji": "🖼️"}
    ],
    "Portfolio": [
        {"id": "portfolio", "label": "Portfolio", "emoji": "💼"},
        {"id": "watchlist", "label": "Watchlist", "emoji": "👁️"}
    ],
    "Market Data": [
        {"id": "news", "label": "News", "emoji": "📰"},
        {"id": "screener", "label": "Screener", "emoji": "🔍"}
    ],
    "Analysis": [
        {"id": "analysis", "label": "Analysis", "emoji": "📊"}
    ]
}
```

**Current Sections**:
- **Charting**: Chart analysis tools
- **Crypto**: Cryptocurrency-specific modules
- **Portfolio**: Investment tracking and management
- **Market Data**: News, screening, and market information
- **Analysis**: Valuation and analysis tools

**Future Sections** (as modules are added):
- **Trading**: Backtesting, strategy builder, paper trading
- **Risk**: Risk analytics, VaR, stress testing
- **Research**: DCF valuation, comp analysis, scenario modeling

### Search Behavior

**Real-time search filtering**

**Specifications**:
- **Search Bar**: Centered, 926px width (equivalent to 2 tiles)
- **Matching**: Case-insensitive against module label
- **Filtering**: Stacks on top of section filtering (if active)
- **Empty Search**: Shows all modules (respects section filter)
- **Clear Button**: X button to reset search

**Example**:
- User types "port" → Shows "Portfolio" tile
- User in "Crypto" section, types "de" → Shows "DeFi" tile only
- User clears search → Returns to section view or all tiles

---

## 8. Configuration & Data Persistence

### Default Settings

Defined in `core/config.py`:

**Window**:
- Size: 1400×900px
- Launches: Maximized
- Title bar: Custom (32px height, frameless)

**Chart Defaults**:
- Ticker: `BTC-USD`
- Interval: `daily`
- Chart Type: `Candles`
- Scale: `Logarithmic`
- Period: 365 days (max for fetch)

**Tile Layout**:
- Columns: 3 (fixed)
- Tile Size: 453×285px
- Spacing: 20px
- Screenshot: 453×255px (16:9 aspect ratio)

**Themes**:
- **Default**: Bloomberg
- **Available**: Dark, Light, Bloomberg
- **Dark Accent**: Cyan (#00d4ff)
- **Light Accent**: Blue (#0066cc)
- **Bloomberg Accent**: Orange (#FF8000)

### User Data Directories

All user data stored in `~/.quant_terminal/`:

**`custom_indicators.json`**:
- User-created technical indicators
- Managed by `IndicatorService`
- Format: List of `{"name": str, "type": str, "parameters": dict}`

**`favorites.json`**:
- Favorited module IDs
- Managed by `FavoritesService`
- Format: List of module IDs `["charts", "portfolio"]`

**`screenshots/`**:
- Module preview images (453×255px PNG)
- Managed by `ScreenshotManager`
- Generated on-demand (lazy loading)
- Section-based color coding with emoji

**`holdings.json`** (future - Portfolio module):
- Portfolio holdings
- Managed by `HoldingsService`
- Format: List of `{"ticker": str, "shares": float, "cost_basis": float}`

### Persistence Services

**FavoritesService** (`services/favorites_service.py`):
- Singleton pattern (class-level storage)
- `toggle_favorite(module_id)`: Add/remove from favorites
- `is_favorite(module_id) → bool`: Check favorite status
- `get_all_favorites() → List[str]`: Get all favorited module IDs
- Saves to `~/.quant_terminal/favorites.json` on every toggle

**IndicatorService** (`modules/chart/services/indicator_service.py`):
- Singleton pattern
- `save_custom_indicator(indicator)`: Persist custom indicator
- `load_custom_indicators() → List[Dict]`: Load all custom indicators
- `delete_custom_indicator(name)`: Remove custom indicator
- Saves to `~/.quant_terminal/custom_indicators.json`

**ChartSettingsManager** (`modules/chart/services/chart_settings_manager.py`):
- Singleton pattern
- `save_settings(settings)`: Persist chart preferences
- `load_settings() → Dict`: Load chart preferences
- Saves to `~/.quant_terminal/chart_settings.json`

**ScreenshotManager** (`utils/screenshot_manager.py`):
- Static methods only (no persistence of metadata)
- `generate_screenshot(module_id, emoji, color)`: Create placeholder image
- `get_screenshot_path(module_id) → Path`: Get path to screenshot
- Saves to `~/.quant_terminal/screenshots/{module_id}.png`

### Environment Variables

**None currently used**

All configuration is hardcoded in `core/config.py`. Future: Consider environment variables for:
- Data directory path (`QUANT_TERMINAL_DATA_DIR`)
- Default theme (`QUANT_TERMINAL_THEME`)
- API keys for market data services

---

## 9. Key Features

### Ticker Equations

**Parse and evaluate mathematical expressions combining tickers**

**Syntax**: Prefix expression with `=`

**Supported Operations**: `+`, `-`, `*`, `/`, `()`

**Examples**:
```python
=BTC-USD              # Single ticker (passthrough)
=BTC-USD/SPX          # Ratio: Bitcoin relative to S&P 500
=BTC-USD*2            # Scaled: Bitcoin price doubled
=(BTC-USD+ETH-USD)/2  # Average of Bitcoin and Ethereum
=BTC-USD-10000        # Offset: Bitcoin price minus 10000
=(BTC-USD/ETH-USD)*100  # Ratio percentage
```

**Implementation**: `TickerEquationParser` in `modules/chart/services/ticker_equation_parser.py`

**Process**:
1. **Tokenize**: Split expression into tokens (tickers, operators, numbers, parens)
2. **Shunting Yard**: Convert infix to Reverse Polish Notation (RPN)
3. **Evaluate**: Process RPN with stack-based evaluation
4. **Date Alignment**: Align dates when combining multiple tickers (inner join on date index)
5. **Caching**: Cache ticker data to avoid re-fetching

**Date Alignment Example**:
```
BTC-USD has data for 2024-01-01, 2024-01-02, 2024-01-03
ETH-USD has data for 2024-01-01, 2024-01-03, 2024-01-04

Result of =BTC-USD+ETH-USD only includes 2024-01-01 and 2024-01-03 (inner join)
```

### Technical Indicators

**9 Built-In Indicator Types**

**Overlays** (plotted on price chart):
- **SMA** (Simple Moving Average): `period`
- **EMA** (Exponential Moving Average): `period`
- **Bollinger Bands**: `period`, `std_dev`
- **VWAP** (Volume Weighted Average Price): no parameters

**Oscillators** (plotted in separate subplot):
- **RSI** (Relative Strength Index): `period`
- **MACD** (Moving Average Convergence Divergence): `fast_period`, `slow_period`, `signal_period`
- **ATR** (Average True Range): `period`
- **Stochastic**: `period`, `smooth_k`, `smooth_d`
- **OBV** (On-Balance Volume): no parameters

**Custom Indicator Creation**:
- Dialog: `CreateIndicatorDialog`
- User inputs: name, type (overlay/oscillator), parameters
- Persistence: `~/.quant_terminal/custom_indicators.json`
- Plugin system: Inherit from `BaseIndicator` ABC

**Multi-Selection**: Apply multiple indicators simultaneously (up to 10)

**Example Usage**:
```python
from modules.chart.services import IndicatorService

# Calculate SMA
sma = IndicatorService.calculate_sma(prices, period=50)

# Calculate RSI
rsi = IndicatorService.calculate_rsi(prices, period=14)

# Create custom indicator
IndicatorService.save_custom_indicator({
    "name": "My Custom SMA",
    "type": "overlay",
    "indicator": "SMA",
    "parameters": {"period": 20}
})
```

### Charting

**Multi-Timeframe Support**:
- **Daily**: 1 day per candle
- **Weekly**: 1 week per candle
- **Monthly**: 1 month per candle
- **Yearly**: 1 year per candle (resampled from monthly data)

**Chart Types**:
- **Candlestick**: OHLC bars with wicks (high/low) and bodies (open/close)
- **Line**: Close price line chart

**Scaling**:
- **Regular**: Linear y-axis
- **Logarithmic**: Log-scale y-axis (better for large price ranges)

**Interactivity**:
- **Draggable Axes**: Click and drag y-axis to zoom/pan
- **Crosshair**: Follows mouse, shows price and date
- **Mouse Price Label**: Shows price at mouse y-position
- **Date Labels**: Smart date formatting based on zoom level
- **Auto-Range**: Fits data to view

**Data Source**: Yahoo Finance via yfinance
- Period: Up to "max" (all available data)
- Automatic interval conversion (daily→1d, weekly→1wk, etc.)

### Dual Plot System

**Main Plot**: Price chart with overlays

**Oscillator Subplot**: Separate pane for oscillators (RSI, MACD, etc.)

**Features**:
- **Synchronized X-Axis**: Both plots share same x-range (dates)
- **Draggable Resize Handle**: Adjust relative heights of main/oscillator
- **Independent Y-Axes**: Each plot has own y-range
- **Theme-Aware**: Both plots update on theme change

**Implementation**:
- Main chart: `PriceChart` (inherits from `BaseChart`)
- Oscillator: `OscillatorPane` (separate widget)
- Resize: `ResizeHandle` (emits `resize_requested` signal)

### Order Book / Depth Chart

**Binance Integration**: Real-time order book data from Binance and Binance.US

**Data**:
- **Levels**: Up to 500 price levels (bids + asks)
- **Update Rate**: 500ms for ladder view
- **Spread**: Calculated as `(best_ask - best_bid)`
- **Spread %**: `(spread / best_bid) * 100`

**Views**:

**Ladder View** (default):
- Traditional order book format
- Columns: Price, Size, Total (cumulative)
- Color-coded: Bids (green), Asks (red)
- Center spread indicator

**Depth Chart**:
- Cumulative volume visualization
- X-axis: Price
- Y-axis: Cumulative volume
- Filled areas: Bids (green), Asks (red)
- Auto-ranging to fit data

**Toggle**: Switch between views via buttons in `OrderBookPanel`

**Supported Tickers**: All Binance trading pairs (e.g., BTCUSDT, ETHUSDT)

---

## 10. Technical Implementation Details

### Event API Differences

**QMouseEvent** (mouse clicks, moves):
```python
def mouseMoveEvent(self, event: QMouseEvent):
    pos = event.pos()  # QPoint
    global_pos = event.globalPosition().toPoint()  # QPoint
```

**QWheelEvent** (mouse wheel scrolling):
```python
def wheelEvent(self, event: QWheelEvent):
    pos = event.position().toPoint()  # QPoint (NOT .pos())
    delta = event.angleDelta().y()
```

**Key Difference**: `QWheelEvent` uses `.position().toPoint()` instead of `.pos()`

### Widget Masking for Overlays

**Why Masking Over Event Forwarding?**

Qt's `:hover` pseudo-state is determined by **physical z-order hierarchy**, not event routing.

**Event Forwarding Fails**:
```python
# ❌ Forwards events but doesn't activate :hover
class Overlay(QWidget):
    def mouseMoveEvent(self, event):
        self.button.mouseMoveEvent(event)  # Button gets event
        # But Qt sees overlay on top → no :hover
```

**Widget Masking Succeeds**:
```python
# ✅ Makes overlay transparent → Qt sees button directly
class Overlay(QWidget):
    def _update_mask(self):
        button_rect = self.button.geometry()
        self.setMask(QRegion(button_rect))  # Only exists in button area
        # Qt sees button in unmasked area → :hover works
```

**When to Use**: Transparent overlays that need to preserve hover states of widgets below

### PyQtGraph Integration

**PlotWidget vs GraphicsLayoutWidget**:

**PlotWidget**: Single-plot widget
```python
chart = pg.PlotWidget()
chart.plot(x, y, pen='b')
```

**GraphicsLayoutWidget**: Multi-plot layout (used for price + oscillator)
```python
layout = pg.GraphicsLayoutWidget()
plot1 = layout.addPlot(row=0, col=0)  # Main chart
plot2 = layout.addPlot(row=1, col=0)  # Oscillator
```

**BaseChart uses GraphicsLayoutWidget** for flexibility (future multi-plot support)

**ViewBox Management**:
```python
self.plot_item = self.getPlotItem()
self.view_box = self.plot_item.getViewBox()
self.view_box.setMouseMode(pg.ViewBox.RectMode)  # Pan mode
```

**Date Axis Handling**:
- PyQtGraph expects numeric x-values
- Convert DatetimeIndex to `range(len(data))`
- Custom axis formatter maps numeric → date strings

### Theme System

**Signal-Based Propagation**:

```python
# ThemeManager emits signal
class ThemeManager(QObject):
    theme_changed = Signal(str)

    def set_theme(self, theme: str):
        self.current_theme = theme
        self.theme_changed.emit(theme)

# Widgets subscribe
class MyWidget(QWidget):
    def __init__(self, theme_manager):
        super().__init__()
        self.theme_manager = theme_manager
        self.theme_manager.theme_changed.connect(self._apply_theme)

    def _apply_theme(self):
        # Generate stylesheet based on self.theme_manager.current_theme
        ...
```

**Stylesheet Generation Pattern**:

Each widget implements 3 methods:
- `_get_dark_stylesheet() → str`
- `_get_light_stylesheet() → str`
- `_get_bloomberg_stylesheet() → str`

Called from `_apply_theme()` based on current theme.

**Centralized Stylesheets** (for shared components):

ThemeManager provides:
- `get_title_bar_stylesheet(theme) → str`
- `get_home_button_stylesheet(theme) → str`
- `get_global_stylesheet(theme) → str` (for QPushButton, QLineEdit, etc.)

### Data Fetching Strategy

**MarketDataService** (`services/market_data.py`):

**Interval Conversion**:
```python
interval_map = {
    "daily": "1d",
    "weekly": "1wk",
    "monthly": "1mo",
    "yearly": "1mo"  # Then resampled to yearly
}
```

**Fetching**:
```python
import yfinance as yf

def fetch_price_history(ticker: str, interval: str, period: str = "max") -> pd.DataFrame:
    yf_interval = interval_map[interval]
    data = yf.download(ticker, period=period, interval=yf_interval)

    # Normalize MultiIndex columns (yfinance sometimes returns MultiIndex)
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.droplevel(1)

    # Resample if yearly
    if interval == "yearly":
        data = data.resample('Y').agg({
            'Open': 'first',
            'High': 'max',
            'Low': 'min',
            'Close': 'last',
            'Volume': 'sum'
        })

    return data
```

**Caching** (`services/market_data_cache.py`):
- In-memory dictionary cache
- 5-minute TTL (time-to-live)
- `clear_cache()` for manual invalidation
- Future: Consider using `functools.lru_cache` or Redis

**Threading**:
- Not currently implemented (yfinance is fast enough for 1-year data)
- Future: Use QThread for multi-ticker fetching in Portfolio module

---

## 11. Testing Strategy

### Manual Testing Checklist

**After Any UI Change**:
- [ ] All button clicks work
- [ ] All button hover effects work
- [ ] Text input focus and interaction works
- [ ] Dropdown menus work
- [ ] Mouse wheel scrolling/zooming works
- [ ] Chart/widget dragging and panning works

**Theme Switching**:
- [ ] Dark → Light: All colors update
- [ ] Light → Bloomberg: All colors update
- [ ] Bloomberg → Dark: All colors update
- [ ] Title bar updates correctly
- [ ] Tiles update correctly
- [ ] Search bar updates correctly
- [ ] Section tabs update correctly
- [ ] Module content updates correctly
- [ ] All dialogs update correctly

**Navigation**:
- [ ] Home screen loads on startup
- [ ] Section tabs filter tiles correctly
- [ ] Search filters case-insensitively
- [ ] Tile clicks open modules in full-screen
- [ ] Home button returns to home screen
- [ ] Favorites toggle and persist across sessions
- [ ] Favorites-first sorting works

**Chart Module**:
- [ ] Ticker input (symbol): Loads data and displays chart
- [ ] Ticker input (equation): Parses and evaluates correctly
- [ ] Interval selector: Daily, weekly, monthly, yearly all work
- [ ] Chart type toggle: Candles ↔ Line
- [ ] Scale toggle: Regular ↔ Log
- [ ] Indicator creation dialog opens and saves
- [ ] Indicator apply: Adds indicator to chart
- [ ] Indicator delete: Removes indicator
- [ ] Multi-indicator support: 5+ indicators work
- [ ] Oscillator subplot appears when oscillator applied
- [ ] Resize handle drags correctly
- [ ] Depth chart toggle shows/hides depth panel
- [ ] Settings dialog opens and saves preferences

### Automated Testing

**None currently implemented**

**Future Considerations**:

**Unit Tests** (pytest):
- Services layer (TickerEquationParser, IndicatorService, PortfolioService)
- Utilities (formatters, validators)
- Example:
  ```python
  def test_parse_equation_ratio():
      result = TickerEquationParser.parse_equation("=BTC-USD/SPX")
      assert isinstance(result, pd.Series)
      assert len(result) > 0
  ```

**Integration Tests** (pytest-qt):
- Widget interactions (button clicks, text input)
- Signal connections
- Example:
  ```python
  def test_chart_controls_ticker_changed(qtbot):
      controls = ChartControls(theme_manager)
      qtbot.addWidget(controls)

      with qtbot.waitSignal(controls.ticker_changed) as blocker:
          controls.ticker_input.setText("AAPL")
          controls.ticker_input.returnPressed.emit()

      assert blocker.args[0] == "AAPL"
  ```

**End-to-End Tests** (pytest-qt):
- Full workflows (open app → change ticker → apply indicator → switch theme)
- Module navigation

---

## 12. Project Entry Point

**Main Entry**: `src/app/main.py`

**Complete Startup Flow**:

```python
import sys
from PySide6.QtWidgets import QApplication

from app.core.theme_manager import ThemeManager
from app.services.favorites_service import FavoritesService
from app.ui.hub_window import HubWindow

# Module imports
from app.ui.modules.chart.chart_module import ChartModule
from app.ui.modules.portfolio.portfolio_module import PortfolioModule  # Future
# ... other modules

def main():
    # 1. Create QApplication
    app = QApplication(sys.argv)
    app.setApplicationName("Quant Terminal")
    app.setOrganizationName("Quant Terminal")

    # 2. Initialize FavoritesService (loads favorites.json)
    FavoritesService.initialize()

    # 3. Initialize ThemeManager (default: Bloomberg)
    theme_manager = ThemeManager()
    theme_manager.set_theme("bloomberg")

    # 4. Create HubWindow (frameless window with custom title bar)
    hub = HubWindow(theme_manager, FavoritesService)

    # 5. Add all modules (each wrapped with home button overlay)
    hub.add_module("charts", ChartModule(theme_manager))
    # hub.add_module("portfolio", PortfolioModule(theme_manager))  # Future
    # ... add other modules

    # 6. Show maximized
    hub.showMaximized()

    # 7. Start Qt event loop
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
```

**Startup Sequence Details**:

1. **QApplication**: Qt application instance, sets app name and organization
2. **FavoritesService.initialize()**: Creates `~/.quant_terminal/favorites.json` if doesn't exist
3. **ThemeManager**: Sets Bloomberg theme as default, emits `theme_changed` signal
4. **HubWindow**:
   - Creates frameless window with custom title bar (32px)
   - Sets up QStackedWidget for HomeScreen ↔ Modules
   - Initializes HomeScreen with section tabs, search, and tile grid
5. **hub.add_module()**: For each module:
   - Wraps module widget in container
   - Adds transparent overlay with home button (top-left, 100×40px)
   - Registers module in QStackedWidget
6. **hub.showMaximized()**: Shows window in maximized state
7. **app.exec()**: Starts Qt event loop, blocks until app quits

---

## 13. Git Workflow

### Branches

- **Main Branch**: `main` (stable, production-ready code)
- **Active Development**: `bb` (current work branch)

### Commit Pattern

```bash
git add .
git commit -m "Brief one-line description

Detailed multi-line explanation of changes:
- Change 1: What and why
- Change 2: What and why
- Change 3: What and why

Technical details if needed:
- File X modified to do Y
- New feature Z added for reason W

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

**Example**:
```
Refactor chart module into reusable components

Extract chart infrastructure into reusable components to support future modules:
- Created BaseChart (~600 lines) for all chart modules
- Extracted axes (draggable, price, date) into charting/axes/
- Extracted CandlestickItem renderer into charting/renderers/
- Moved ResizeHandle to charting/overlays/

PriceChart now inherits from BaseChart (reduced from 2,076 → 500 lines).
Portfolio, Risk, and Monte Carlo modules can now reuse BaseChart infrastructure.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

### Recent Work

**Completed**:
- Tile-based navigation system (HomeScreen, tiles, section tabs, search)
- Custom title bar pattern (frameless windows, draggable title bars)
- Favorites system with persistence
- Chart module refactoring (8 phases):
  1. Extract theme service
  2. Extract control bar widget
  3. Extract indicator panel widget
  4. Extract overlay components (ResizeHandle)
  5. Extract axis components (3 classes)
  6. Extract renderer components (CandlestickItem)
  7. Create BaseChart foundation
  8. Document chart architecture
- Service reorganization (module-scoped pattern)

**In Progress**:
- Portfolio module implementation
- Additional placeholder module implementation

**Next**:
- Risk Analytics module
- Monte Carlo Simulation module
- Backtesting Engine module

---

## 14. Future Expansion Plans

### Planned Modules (25+ Total)

**Portfolio & Risk** (priority):
- **Portfolio Performance**: Cumulative returns, drawdowns, Sharpe ratio, benchmark comparison
- **Risk Analytics**: VaR, CVaR, beta, correlation matrices, stress testing
- **Monte Carlo Simulation**: Portfolio projections, probability distributions, scenario analysis

**Analysis**:
- **DCF Valuation**: Discounted cash flow models, WACC calculation, sensitivity analysis
- **Comparable Company Analysis**: Multiples analysis (P/E, EV/EBITDA, etc.)
- **Scenario Analysis**: Bull/base/bear scenarios, tornado charts

**Market Data**:
- **Earnings Calendar**: Upcoming earnings, historical beats/misses
- **Economic Calendar**: Fed meetings, GDP releases, CPI/PPI data
- **Sector Heatmap**: Real-time sector performance visualization

**Crypto** (expand existing):
- **DeFi Protocol Tracker**: TVL, APY, yields across protocols
- **NFT Marketplace Analytics**: Floor prices, volume, rarity rankings
- **On-Chain Metrics**: Network activity, whale movements, miner revenues

**Trading**:
- **Backtesting Engine**: Historical strategy testing, performance metrics
- **Strategy Builder**: Visual strategy editor, no-code backtesting
- **Paper Trading**: Simulated trading with real-time data

### Reusable Components Ready

**Infrastructure in Place**:

**BaseChart** (~600 lines):
- Core plotting functionality
- Theme support
- Event handling
- View management

**Axes** (~197 lines total):
- DraggableAxisItem: Click-and-drag zoom/pan
- PriceAxisItem: Price formatting ($1,234.56)
- DateIndexAxisItem: Smart date formatting

**Renderers** (~88 lines):
- CandlestickItem: OHLC bar rendering

**Overlays** (~100 lines):
- ResizeHandle: Draggable split pane resize

**Navigation** (~1,000+ lines):
- HomeScreen: Section tabs + search + tile grid
- ModuleTile: 453×285px tiles with favorites
- ModuleTileGrid: 3-column layout with filtering
- SectionTabBar: Horizontal section tabs

**Total Reusable**: ~2,000 lines of infrastructure ready for new modules

### Module Development Time Estimates

**Simple Modules** (2-4 hours):
- News: RSS feed aggregation, article list
- Watchlist: Ticker list, price updates
- Screener: Filter stocks by criteria

**Medium Modules** (1-2 days):
- Portfolio: Holdings table, performance chart, metrics
- Risk Analytics: VaR/CVaR calculations, correlation heatmap
- Earnings Calendar: Fetch earnings dates, display grid

**Complex Modules** (3-5 days):
- Backtesting: Strategy builder, historical testing, performance metrics
- Monte Carlo: Simulation engine, probability distributions, visualization
- DCF Valuation: Financial model inputs, calculations, sensitivity analysis

### Efficiency Gain

**Without Reusable Infrastructure** (old approach):
- Portfolio Chart: ~650 lines (600 BaseChart + 50 portfolio-specific)
- Risk Chart: ~650 lines (600 BaseChart + 50 risk-specific)
- Monte Carlo Chart: ~650 lines (600 BaseChart + 50 MC-specific)
- **Total**: 1,950 lines

**With Reusable Infrastructure** (current approach):
- Portfolio Chart: ~50 lines (inherits BaseChart)
- Risk Chart: ~50 lines (inherits BaseChart)
- Monte Carlo Chart: ~50 lines (inherits BaseChart)
- **Total**: 150 lines written, 1,950 lines functionality

**Result**: **12x reduction** in code written (150 vs 1,950)

---

## Summary for AI Assistants

**This codebase is designed for scalability**:
- Module-scoped services prevent global services clutter
- Reusable charting infrastructure (BaseChart + components)
- Tile-based navigation for unlimited module growth
- Comprehensive theme system (Dark, Light, Bloomberg)
- Signal-based architecture for loose coupling

**When building a new module**:
1. Follow the Module Development Guide (Section 4)
2. Use the Module Development Checklist
3. Inherit from BaseChart for any chart modules
4. Use relative imports within the module
5. Connect to `theme_changed` signal
6. Register in `core/config.py` and `main.py`

**When in doubt**:
- Check existing patterns in Chart module
- Prefer composition over inheritance
- Keep services separate from widgets
- Use signal-based communication
- Test theme switching after any UI change

**Code reduction target**: Write ~50 lines instead of 600+ for chart modules
