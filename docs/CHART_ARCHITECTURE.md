# Chart Architecture - Reusable Components Guide

## Overview

The chart module has been refactored into a modular, reusable architecture that supports building 25+ Bloomberg-scale chart modules. All charting components are located in `src/app/ui/widgets/charting/`.

## Component Hierarchy

```
src/app/ui/widgets/charting/
├── base_chart.py           # Base class for all chart modules (~210 lines)
├── axes/                   # Reusable axis components
│   ├── draggable_axis.py      # Base drag-to-zoom axis (~75 lines)
│   ├── price_axis.py          # USD formatting with log scale (~47 lines)
│   └── date_index_axis.py     # Date display for integer indices (~79 lines)
├── renderers/              # Chart item renderers
│   └── candlestick.py         # OHLC candlestick renderer (~96 lines)
└── overlays/               # UI overlays for charts
    └── resize_handle.py       # Draggable resize handle (~100 lines)
```

## Building a New Chart Module

### Example: Portfolio Performance Chart

```python
from app.ui.widgets.charting import BaseChart
from app.ui.widgets.charting.axes import DraggableAxisItem
import pyqtgraph as pg

class PortfolioPerformanceChart(BaseChart):
    """Portfolio cumulative returns chart."""

    def __init__(self, theme_manager, parent=None):
        super().__init__(parent=parent)
        self.theme_manager = theme_manager

        # Create plot with custom axes
        self.plot_item = self.addPlot(
            axisItems={
                'bottom': pg.DateAxisItem(orientation='bottom'),
                'left': DraggableAxisItem(orientation='left')
            }
        )
        self.view_box = self.plot_item.getViewBox()
        self.view_box.setMouseEnabled(x=True, y=True)

        # Create crosshair (optional)
        self._crosshair_v, self._crosshair_h = self._create_crosshair(
            self.plot_item, self.view_box
        )

        # Apply theme
        self.set_theme(theme_manager.current_theme)
        theme_manager.theme_changed.connect(self.set_theme)

        # Add legend
        self.legend = pg.LegendItem(offset=(10, 10))
        self.legend.setParentItem(self.view_box)
        self.legend.anchor(itemPos=(0, 0), parentPos=(0, 0))

    def plot_returns(self, returns_df):
        """Plot cumulative returns data."""
        self.clear_plot()

        # Convert to cumulative returns (%)
        cumulative = (1 + returns_df['returns']).cumprod() - 1

        # Plot line
        line = self.plot_item.plot(
            returns_df.index.to_pydatetime(),
            cumulative.values * 100,
            pen=pg.mkPen(color=self._get_theme_accent_color(), width=2),
            name='Portfolio Returns'
        )
        self.legend.addItem(line, 'Portfolio Returns')

    def _on_mouse_move(self, ev):
        """Show crosshair and value on mouse move."""
        pos = ev.pos()
        if self.plot_item.sceneBoundingRect().contains(pos):
            mouse_point = self.view_box.mapSceneToView(pos)
            self._crosshair_v.setPos(mouse_point.x())
            self._crosshair_h.setPos(mouse_point.y())
            self._crosshair_v.setVisible(True)
            self._crosshair_h.setVisible(True)

    def _on_mouse_leave(self, ev):
        """Hide crosshair on mouse leave."""
        self._crosshair_v.setVisible(False)
        self._crosshair_h.setVisible(False)
```

**What you get for free:**
- Theme management (dark/light/bloomberg) - ~50 lines
- Background color application - ~15 lines
- Gridline calculation and styling - ~40 lines
- Crosshair creation and color management - ~50 lines
- Event handler hooks (mouse move, leave) - ~20 lines
- Utility methods (clear_plot, add_item, remove_item) - ~15 lines
- Color helpers (accent, text color) - ~20 lines

**Total inherited: ~210 lines of infrastructure**

### Example: Efficient Frontier Chart

```python
from app.ui.widgets.charting import BaseChart
from app.ui.widgets.charting.axes import DraggableAxisItem

class EfficientFrontierChart(BaseChart):
    """Modern Portfolio Theory efficient frontier visualization."""

    def __init__(self, theme_manager, parent=None):
        super().__init__(parent=parent)

        # Create plot
        self.plot_item = self.addPlot(
            axisItems={
                'bottom': DraggableAxisItem(orientation='bottom'),  # Risk (volatility)
                'left': DraggableAxisItem(orientation='left')       # Return
            }
        )
        self.plot_item.setLabel('bottom', 'Risk (Volatility %)')
        self.plot_item.setLabel('left', 'Expected Return %')

        self.view_box = self.plot_item.getViewBox()
        self.view_box.setMouseEnabled(x=True, y=True)

        # Apply theme
        self.set_theme(theme_manager.current_theme)
        theme_manager.theme_changed.connect(self.set_theme)

    def plot_frontier(self, risk_returns_df):
        """Plot efficient frontier curve and portfolio points."""
        self.clear_plot()

        # Plot frontier curve
        frontier = self.plot_item.plot(
            risk_returns_df['volatility'] * 100,
            risk_returns_df['return'] * 100,
            pen=pg.mkPen(color=self._get_theme_accent_color(), width=3)
        )

        # Plot individual portfolio points
        scatter = pg.ScatterPlotItem(
            risk_returns_df['volatility'] * 100,
            risk_returns_df['return'] * 100,
            size=8,
            pen=pg.mkPen(color=self._get_theme_accent_color()),
            brush=pg.mkBrush(color=self._get_theme_accent_color())
        )
        self.add_item(scatter)
```

## Reusable Axes

### DraggableAxisItem
Base axis with drag-to-zoom functionality.

```python
from app.ui.widgets.charting.axes import DraggableAxisItem

# Create draggable Y-axis
y_axis = DraggableAxisItem(orientation='left')

# Drag up = zoom in, Drag down = zoom out (inverted for intuitive feel)
```

### DraggablePriceAxisItem
Price axis with USD formatting and log scale support.

```python
from app.ui.widgets.charting.axes import DraggablePriceAxisItem

price_axis = DraggablePriceAxisItem(orientation='right')
price_axis.set_scale_mode('log')  # or 'regular'

# Displays: $1,234.56 or $0.12345678 (smart formatting)
```

### DraggableIndexDateAxisItem
Date axis that displays dates for integer-indexed data.

```python
from app.ui.widgets.charting.axes import DraggableIndexDateAxisItem

date_axis = DraggableIndexDateAxisItem(orientation='bottom')
date_axis.set_index(df.index)  # Pass DatetimeIndex

# Displays: 2024-01-15, Jan 2024, etc. (smart date formatting)
```

## Reusable Renderers

### CandlestickItem
OHLC candlestick chart renderer.

```python
from app.ui.widgets.charting.renderers import CandlestickItem
import numpy as np

# Prepare data: [[x, open, close, low, high], ...]
candle_data = np.array([
    [0, 100, 105, 98, 107],
    [1, 105, 103, 101, 106],
    # ...
])

candles = CandlestickItem(
    data=candle_data,
    bar_width=0.6,
    up_color=(76, 153, 0),    # Green
    down_color=(200, 50, 50)  # Red
)
plot_item.addItem(candles)

# Update data
candles.setData(new_data)

# Change colors
candles.setColors(new_up_color, new_down_color)
```

## Reusable Overlays

### ResizeHandle
Draggable handle for resizing subplots.

```python
from app.ui.widgets.charting.overlays import ResizeHandle

handle = ResizeHandle(parent=self)
handle.height_changed.connect(self._on_resize)
handle.drag_started.connect(self._on_drag_start)
handle.drag_ended.connect(self._on_drag_end)

def _on_resize(self, delta_y):
    # Adjust subplot height by delta_y pixels
    new_height = current_height + delta_y
    self.set_subplot_height(new_height)
```

## Current Chart Modules

### PriceChart (`src/app/ui/widgets/price_chart.py`)
Specialized OHLC financial chart with:
- Dual plots (price + oscillator)
- Candlestick and line chart types
- Log/regular scaling
- Technical indicators (overlays + oscillators)
- Multi-pane oscillator system
- Price/date/mouse labels
- Crosshair with labels

**Note:** PriceChart remains independent due to its specialized dual-plot architecture and price-specific features. It does NOT inherit from BaseChart - BaseChart is for NEW modules going forward.

## Service Layer

### ChartThemeService (`src/app/services/chart_theme_service.py`)
Centralized chart component stylesheets.

```python
from app.services.chart_theme_service import ChartThemeService

# Get stylesheet for indicator panel
stylesheet = ChartThemeService.get_indicator_panel_stylesheet('bloomberg')
widget.setStyleSheet(stylesheet)

# Available methods:
# - get_indicator_panel_stylesheet(theme)
# - get_control_bar_stylesheet(theme)
# - get_depth_panel_stylesheet(theme)
```

## Widget Layer

### ChartControls (`src/app/ui/widgets/chart_controls.py`)
Control bar for chart configuration.

```python
from app.ui.widgets.chart_controls import ChartControls

controls = ChartControls(theme_manager)
controls.ticker_changed.connect(self._on_ticker_changed)
controls.interval_changed.connect(self._on_interval_changed)
controls.chart_type_changed.connect(self._on_chart_type_changed)
controls.scale_changed.connect(self._on_scale_changed)
controls.settings_clicked.connect(self._on_settings)
controls.indicators_toggled.connect(self._on_indicators_toggle)
controls.depth_toggled.connect(self._on_depth_toggle)

# Getters
ticker = controls.get_ticker()
interval = controls.get_interval()
chart_type = controls.get_chart_type()
scale = controls.get_scale()
```

### IndicatorPanel (`src/app/ui/modules/chart/indicator_panel.py`)
Sidebar for technical indicator management.

```python
from app.ui.modules.chart.indicator_panel import IndicatorPanel

panel = IndicatorPanel(theme_manager)
panel.apply_clicked.connect(self._apply_indicators)
panel.clear_clicked.connect(self._clear_indicators)
panel.create_clicked.connect(self._create_custom_indicator)
panel.edit_clicked.connect(self._edit_indicator)
panel.delete_clicked.connect(self._delete_indicator)

# Get selections
overlays = panel.get_selected_overlays()
oscillators = panel.get_selected_oscillators()

# Refresh after custom indicator changes
panel.refresh_indicators(preserve_selection=True)
```

## Design Principles

### 1. Composition Over Inheritance
Components are designed to be composed rather than deeply inherited.

### 2. Single Responsibility
Each component has one clear purpose:
- Axes handle coordinate mapping and display
- Renderers handle visual representation
- Overlays handle UI elements on top of charts
- BaseChart handles theme and infrastructure

### 3. Theme Awareness
All components support dark, light, and bloomberg themes.

### 4. Reusability First
Every component is designed to be used across multiple chart types.

### 5. Event-Driven
Components communicate via Qt signals/slots for loose coupling.

## Future Modules Roadmap

Ready to build with BaseChart + components:

1. **Portfolio Analysis**
   - Performance chart (cumulative returns)
   - Asset allocation pie/bar charts
   - Sector exposure visualization

2. **Risk Analytics**
   - Value at Risk (VaR) distribution
   - Correlation heatmap
   - Drawdown chart

3. **Portfolio Theory**
   - Efficient frontier chart
   - Capital allocation line
   - Sharpe ratio visualization

4. **Monte Carlo Simulations**
   - Multi-path simulation chart
   - Confidence interval bands
   - Probability distributions

Each of these modules can be built in ~100-200 lines by inheriting from BaseChart and composing with axes/renderers.

## Line Count Summary

### Before Refactoring
- `chart_module.py`: 999 lines
- `price_chart.py`: 2,076 lines
- **Total: 3,075 lines** (all in 2 files)

### After Refactoring
```
Services:
  chart_theme_service.py          235 lines

Widgets:
  chart_controls.py               180 lines

Modules:
  chart_module.py                 ~700 lines (refactored)
  indicator_panel.py              200 lines

Charting Components:
  base_chart.py                   210 lines
  axes/draggable_axis.py           75 lines
  axes/price_axis.py               47 lines
  axes/date_index_axis.py          79 lines
  renderers/candlestick.py         96 lines
  overlays/resize_handle.py       100 lines
  price_chart.py                ~1,300 lines (refactored)

Total: ~3,222 lines across 11 files
Reusable components: ~607 lines
```

### Benefits
- ✅ No file exceeds 1,400 lines (was 2,076)
- ✅ Clear separation of concerns
- ✅ ~607 lines of reusable components for future modules
- ✅ Easy to find code (11 focused files vs 2 large files)
- ✅ Clear location for new features
- ✅ Theme duplication eliminated
- ✅ Future modules need ~100-200 lines each (inherit BaseChart infrastructure)

## Migration Guide

### Creating a New Chart Module

1. **Inherit from BaseChart**
   ```python
   from app.ui.widgets.charting import BaseChart

   class MyChart(BaseChart):
       def __init__(self, theme_manager, parent=None):
           super().__init__(parent=parent)
   ```

2. **Set up plot and ViewBox**
   ```python
   self.plot_item = self.addPlot(axisItems={...})
   self.view_box = self.plot_item.getViewBox()
   ```

3. **Apply theme**
   ```python
   self.set_theme(theme_manager.current_theme)
   theme_manager.theme_changed.connect(self.set_theme)
   ```

4. **Add optional crosshair**
   ```python
   self._crosshair_v, self._crosshair_h = self._create_crosshair(
       self.plot_item, self.view_box
   )
   ```

5. **Implement mouse handlers (optional)**
   ```python
   def _on_mouse_move(self, ev):
       # Custom mouse tracking
       pass

   def _on_mouse_leave(self, ev):
       # Hide crosshair/labels
       pass
   ```

6. **Add plotting methods**
   ```python
   def plot_data(self, data):
       self.clear_plot()
       # Use self.plot_item.plot(), self.add_item(), etc.
   ```

You now have a fully functional, theme-aware chart module in ~50-100 lines!
