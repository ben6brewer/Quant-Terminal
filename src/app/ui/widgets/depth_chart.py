from __future__ import annotations

from typing import List, Tuple, Optional
import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont

from app.services.binance_data import BinanceOrderBook


class DepthChartWidget(pg.PlotWidget):
    """
    Order book depth chart visualization.
    Shows bids and asks with cumulative volume.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        
        self.setLabel("left", "Cumulative Volume")
        self.setLabel("bottom", "Price (USD)")
        self.showGrid(x=True, y=True, alpha=0.3)
        
        # Hide legend initially
        self.legend = None
        
        # Plot items
        self.bid_area = None
        self.ask_area = None
        self.bid_line = None
        self.ask_line = None
        
        # Theme colors
        self._theme = "dark"
        self._apply_theme()
    
    def _apply_theme(self):
        """Apply theme colors."""
        if self._theme == "light":
            self.setBackground('w')
        else:
            self.setBackground('#1e1e1e')
    
    def set_theme(self, theme: str):
        """Set the chart theme."""
        self._theme = theme
        self._apply_theme()
    
    def clear_depth(self):
        """Clear the depth chart."""
        if self.bid_area:
            self.removeItem(self.bid_area)
            self.bid_area = None
        if self.ask_area:
            self.removeItem(self.ask_area)
            self.ask_area = None
        if self.bid_line:
            self.removeItem(self.bid_line)
            self.bid_line = None
        if self.ask_line:
            self.removeItem(self.ask_line)
            self.ask_line = None
        if self.legend:
            try:
                self.legend.scene().removeItem(self.legend)
            except:
                pass
            self.legend = None
    
    def plot_depth(
        self,
        bids: List[Tuple[float, float]],
        asks: List[Tuple[float, float]],
    ):
        """
        Plot order book depth.
        
        Args:
            bids: List of (price, quantity) tuples, sorted descending
            asks: List of (price, quantity) tuples, sorted ascending
        """
        self.clear_depth()
        
        if not bids and not asks:
            return
        
        # Calculate cumulative volumes
        bid_prices = [price for price, _ in bids]
        bid_volumes = [qty for _, qty in bids]
        bid_cumulative = np.cumsum(bid_volumes[::-1])[::-1]  # Cumulative from best bid down
        
        ask_prices = [price for price, _ in asks]
        ask_volumes = [qty for _, qty in asks]
        ask_cumulative = np.cumsum(ask_volumes)  # Cumulative from best ask up
        
        # Colors (green for bids, red for asks)
        bid_color = (76, 175, 80, 150)  # Green with transparency
        ask_color = (244, 67, 54, 150)  # Red with transparency
        bid_line_color = (76, 175, 80, 255)
        ask_line_color = (244, 67, 54, 255)
        
        # Plot bid area (filled)
        if bid_prices and bid_cumulative.size > 0:
            # Create step plot for bids
            bid_x = []
            bid_y = []
            for i in range(len(bid_prices)):
                bid_x.append(bid_prices[i])
                bid_y.append(bid_cumulative[i])
                if i < len(bid_prices) - 1:
                    bid_x.append(bid_prices[i+1])
                    bid_y.append(bid_cumulative[i])
            
            # Add area fill
            self.bid_area = pg.FillBetweenItem(
                pg.PlotCurveItem(bid_x, bid_y),
                pg.PlotCurveItem(bid_x, [0] * len(bid_x)),
                brush=pg.mkBrush(bid_color)
            )
            self.addItem(self.bid_area)
            
            # Add line
            self.bid_line = self.plot(
                bid_x, bid_y,
                pen=pg.mkPen(color=bid_line_color, width=2),
                name="Bids"
            )
        
        # Plot ask area (filled)
        if ask_prices and ask_cumulative.size > 0:
            # Create step plot for asks
            ask_x = []
            ask_y = []
            for i in range(len(ask_prices)):
                ask_x.append(ask_prices[i])
                ask_y.append(ask_cumulative[i])
                if i < len(ask_prices) - 1:
                    ask_x.append(ask_prices[i+1])
                    ask_y.append(ask_cumulative[i])
            
            # Add area fill
            self.ask_area = pg.FillBetweenItem(
                pg.PlotCurveItem(ask_x, ask_y),
                pg.PlotCurveItem(ask_x, [0] * len(ask_x)),
                brush=pg.mkBrush(ask_color)
            )
            self.addItem(self.ask_area)
            
            # Add line
            self.ask_line = self.plot(
                ask_x, ask_y,
                pen=pg.mkPen(color=ask_line_color, width=2),
                name="Asks"
            )
        
        # Add legend
        self.legend = self.addLegend(offset=(10, 10))
        
        # Auto-range to fit data
        self.autoRange()


class OrderBookPanel(QWidget):
    """
    Panel showing order book depth chart and statistics.
    """
    
    def __init__(self, theme_manager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self.binance_api = BinanceOrderBook()
        self.current_ticker = None
        
        # Update timer
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self._refresh_data)
        
        self._setup_ui()
        self._apply_theme()
        
        # Connect to theme changes
        self.theme_manager.theme_changed.connect(self._on_theme_changed)
    
    def _setup_ui(self):
        """Setup the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        # Header with stats
        self.header = QWidget()
        self.header.setObjectName("depthHeader")
        header_layout = QVBoxLayout(self.header)
        header_layout.setContentsMargins(10, 5, 10, 5)
        header_layout.setSpacing(3)
        
        # Title
        title = QLabel("Order Book Depth")
        title.setObjectName("depthTitle")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(11)
        title.setFont(title_font)
        header_layout.addWidget(title)
        
        # Stats row
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(15)
        
        self.spread_label = QLabel("Spread: --")
        self.spread_label.setObjectName("statLabel")
        stats_layout.addWidget(self.spread_label)
        
        self.bid_volume_label = QLabel("Bid Vol: --")
        self.bid_volume_label.setObjectName("statLabel")
        stats_layout.addWidget(self.bid_volume_label)
        
        self.ask_volume_label = QLabel("Ask Vol: --")
        self.ask_volume_label.setObjectName("statLabel")
        stats_layout.addWidget(self.ask_volume_label)
        
        stats_layout.addStretch()
        header_layout.addLayout(stats_layout)
        
        layout.addWidget(self.header)
        
        # Depth chart
        self.depth_chart = DepthChartWidget()
        layout.addWidget(self.depth_chart, stretch=1)
        
        # Status label
        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)
    
    def _on_theme_changed(self, theme: str):
        """Handle theme change."""
        self._apply_theme()
        self.depth_chart.set_theme(theme)
    
    def _apply_theme(self):
        """Apply theme styling."""
        theme = self.theme_manager.current_theme
        
        if theme == "light":
            stylesheet = self._get_light_stylesheet()
        else:
            stylesheet = self._get_dark_stylesheet()
        
        self.setStyleSheet(stylesheet)
    
    def _get_dark_stylesheet(self) -> str:
        """Get dark theme stylesheet."""
        return """
            QWidget {
                background-color: #1e1e1e;
                color: #ffffff;
            }
            #depthHeader {
                background-color: #2d2d2d;
                border-bottom: 2px solid #00d4ff;
            }
            #depthTitle {
                color: #00d4ff;
            }
            #statLabel {
                color: #cccccc;
                font-size: 11px;
            }
            #statusLabel {
                color: #888888;
                font-size: 10px;
                font-style: italic;
                padding: 5px;
            }
        """
    
    def _get_light_stylesheet(self) -> str:
        """Get light theme stylesheet."""
        return """
            QWidget {
                background-color: #ffffff;
                color: #000000;
            }
            #depthHeader {
                background-color: #f5f5f5;
                border-bottom: 2px solid #0066cc;
            }
            #depthTitle {
                color: #0066cc;
            }
            #statLabel {
                color: #333333;
                font-size: 11px;
            }
            #statusLabel {
                color: #666666;
                font-size: 10px;
                font-style: italic;
                padding: 5px;
            }
        """
    
    def set_ticker(self, ticker: str):
        """Set the ticker to display depth for."""
        self.current_ticker = ticker
        
        if not BinanceOrderBook.is_binance_ticker(ticker):
            self.clear_depth()
            self.status_label.setText(f"{ticker} is not available on Binance")
            self.stop_updates()
            return
        
        self.status_label.setText("Loading...")
        self._refresh_data()
        self.start_updates()
    
    def _refresh_data(self):
        """Refresh order book data."""
        if not self.current_ticker:
            return
        
        if not BinanceOrderBook.is_binance_ticker(self.current_ticker):
            return
        
        # Fetch order book
        summary = self.binance_api.get_depth_summary(self.current_ticker, levels=50)
        
        if not summary:
            self.status_label.setText("Failed to fetch depth data")
            return
        
        # Update stats
        spread_pct = summary["spread_pct"]
        self.spread_label.setText(f"Spread: ${summary['spread']:.2f} ({spread_pct:.3f}%)")
        self.bid_volume_label.setText(f"Bid Vol: {summary['bid_volume']:.4f}")
        self.ask_volume_label.setText(f"Ask Vol: {summary['ask_volume']:.4f}")
        
        # Update chart
        self.depth_chart.plot_depth(summary["bids"], summary["asks"])
        
        # Update status
        timestamp = summary["timestamp"].strftime("%H:%M:%S")
        self.status_label.setText(f"Updated: {timestamp}")
    
    def start_updates(self, interval_ms: int = 5000):
        """Start automatic updates."""
        self.update_timer.start(interval_ms)
    
    def stop_updates(self):
        """Stop automatic updates."""
        self.update_timer.stop()
    
    def clear_depth(self):
        """Clear the depth chart and stats."""
        self.depth_chart.clear_depth()
        self.spread_label.setText("Spread: --")
        self.bid_volume_label.setText("Bid Vol: --")
        self.ask_volume_label.setText("Ask Vol: --")
        self.status_label.setText("")
    
    def closeEvent(self, event):
        """Stop updates when widget is closed."""
        self.stop_updates()
        super().closeEvent(event)