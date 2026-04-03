"""Stock Heatmap Widget — Squarified treemap with QPainter rendering."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication, QMenu, QToolTip, QWidget

import squarify

from app.services.theme_stylesheet_service import ThemeStylesheetService

# Sector header height in pixels
_HEADER_HEIGHT = 28
# Minimum rect dimensions for text rendering
_MIN_TEXT_WIDTH = 38
_MIN_TEXT_HEIGHT = 22
_MIN_PCT_HEIGHT = 36
# Minimum area for showing a logo
_MIN_LOGO_AREA = 8000

# Color anchors for the -3% to +3% gradient
_RED = (191, 24, 24)
_NEUTRAL = (45, 45, 45)
_GREEN = (24, 167, 46)


class StockHeatmapWidget(QWidget):
    """Squarified treemap visualisation of S&P 500 stocks."""

    ticker_clicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._theme = "bloomberg"
        self._heatmap_data: Optional[List[Dict]] = None
        self._view_mode = "Sector Grouped"
        self._rects: List[Tuple[QRectF, Dict]] = []
        self._sector_rects: List[Tuple[QRectF, str]] = []
        self._hovered_index = -1
        self._show_hover_tooltip = True
        self._show_ticker = True
        self._show_logo = True
        self._color_scale = 3.0
        self._placeholder_text = "Loading..."
        self._show_placeholder = True
        self._logo_cache: Dict[str, Optional[QPixmap]] = {}
        self.setMouseTracking(True)
        self._apply_tooltip_style()

    # ── Public API (called by module) ─────────────────────────────────────

    def update_data(self, heatmap_data: Optional[List[Dict]], settings: dict):
        if heatmap_data is None or len(heatmap_data) == 0:
            self.show_placeholder("No data available.")
            return
        self._heatmap_data = heatmap_data
        self._view_mode = settings.get("view_mode", "Sector Grouped")
        self._show_hover_tooltip = settings.get("show_hover_tooltip", True)
        self._show_ticker = settings.get("show_ticker", True)
        self._show_logo = settings.get("show_logo", True)
        self._color_scale = max(0.5, settings.get("color_scale", 3.0))
        self._show_placeholder = False
        self._compute_layout()
        self.update()

    def set_theme(self, theme: str):
        self._theme = theme
        self._apply_tooltip_style()
        self.update()

    def _apply_tooltip_style(self):
        bg = ThemeStylesheetService.get_background_rgb(self._theme)
        text = ThemeStylesheetService.get_text_rgb(self._theme)
        self.setStyleSheet(
            f"QToolTip {{"
            f"  background-color: rgb({bg[0]+15},{bg[1]+15},{bg[2]+15});"
            f"  color: rgb({text[0]},{text[1]},{text[2]});"
            f"  border: 1px solid rgba({text[0]},{text[1]},{text[2]},80);"
            f"  border-radius: 6px;"
            f"  padding: 8px 10px;"
            f"  font-size: 12px;"
            f"}}"
        )

    def show_placeholder(self, message: str):
        self._placeholder_text = message
        self._show_placeholder = True
        self._rects = []
        self._sector_rects = []
        self.update()

    # ── Layout computation ────────────────────────────────────────────────

    def _compute_layout(self):
        if not self._heatmap_data:
            return

        w = self.width()
        h = self.height()
        if w < 10 or h < 10:
            return

        self._rects = []
        self._sector_rects = []

        if self._view_mode == "Sector Grouped":
            self._compute_grouped_layout(w, h)
        else:
            self._compute_flat_layout(w, h)

    def _compute_flat_layout(self, w: float, h: float):
        data = sorted(self._heatmap_data, key=lambda d: d["weight"], reverse=True)
        sizes = [max(d["weight"], 1e-10) for d in data]
        normed = squarify.normalize_sizes(sizes, w, h)
        rects = squarify.squarify(normed, 0, 0, w, h)

        for rect_dict, stock in zip(rects, data):
            r = QRectF(rect_dict["x"], rect_dict["y"], rect_dict["dx"], rect_dict["dy"])
            self._rects.append((r, stock))

    def _compute_grouped_layout(self, w: float, h: float):
        # Group by sector
        sectors: Dict[str, List[Dict]] = {}
        for stock in self._heatmap_data:
            sector = stock.get("sector", "Other")
            sectors.setdefault(sector, []).append(stock)

        # Sort sectors by total weight descending
        sector_weights = []
        for sector_name, stocks in sectors.items():
            total = sum(max(s["weight"], 1e-10) for s in stocks)
            sector_weights.append((sector_name, total, stocks))
        sector_weights.sort(key=lambda x: x[1], reverse=True)

        sector_names = [sw[0] for sw in sector_weights]
        sector_sizes = [sw[1] for sw in sector_weights]

        normed = squarify.normalize_sizes(sector_sizes, w, h)
        sector_rects = squarify.squarify(normed, 0, 0, w, h)

        for rect_dict, (sector_name, _, stocks) in zip(sector_rects, sector_weights):
            sx, sy = rect_dict["x"], rect_dict["y"]
            sw, sh = rect_dict["dx"], rect_dict["dy"]

            # Sector header rect
            header_h = min(_HEADER_HEIGHT, sh * 0.3)
            self._sector_rects.append(
                (QRectF(sx, sy, sw, header_h), sector_name)
            )

            # Subdivide remaining area among stocks
            inner_y = sy + header_h
            inner_h = sh - header_h
            if inner_h < 2 or sw < 2:
                continue

            stocks_sorted = sorted(stocks, key=lambda s: s["weight"], reverse=True)
            stock_sizes = [max(s["weight"], 1e-10) for s in stocks_sorted]
            stock_normed = squarify.normalize_sizes(stock_sizes, sw, inner_h)
            stock_rects = squarify.squarify(stock_normed, sx, inner_y, sw, inner_h)

            for sr, stock in zip(stock_rects, stocks_sorted):
                r = QRectF(sr["x"], sr["y"], sr["dx"], sr["dy"])
                self._rects.append((r, stock))

    # ── Painting ──────────────────────────────────────────────────────────

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)

        bg = ThemeStylesheetService.get_background_rgb(self._theme)
        painter.fillRect(self.rect(), QColor(*bg))

        if self._show_placeholder:
            text_rgb = ThemeStylesheetService.get_text_rgb(self._theme)
            painter.setPen(QColor(*text_rgb))
            painter.setFont(QFont("Helvetica", 16))
            painter.drawText(self.rect(), Qt.AlignCenter, self._placeholder_text)
            painter.end()
            return

        border_color = QColor(*bg)
        border_pen = QPen(border_color, 1)

        # Draw stock tiles
        for i, (rect, data) in enumerate(self._rects):
            pct = data.get("pct_change", 0.0)
            fill = self._pct_to_color(pct)
            painter.fillRect(rect, fill)

            # Border
            painter.setPen(border_pen)
            painter.drawRect(rect)

            rw, rh = rect.width(), rect.height()

            # Try to get logo for larger tiles
            has_logo = False
            if self._show_logo and rw * rh >= _MIN_LOGO_AREA:
                logo = self._get_logo(data["ticker"], data.get("logo_path"))
                if logo is not None:
                    has_logo = True
                    # Scale logo to ~55% of shorter dimension
                    logo_size = int(min(rw, rh) * 0.55)
                    logo_size = max(24, min(logo_size, 128))
                    scaled = logo.scaled(logo_size, logo_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    sw, sh = scaled.width(), scaled.height()

                    # Circle-crop
                    circle = QPixmap(sw, sh)
                    circle.fill(Qt.transparent)
                    cp = QPainter(circle)
                    cp.setRenderHint(QPainter.Antialiasing)
                    path = QPainterPath()
                    path.addEllipse(0, 0, sw, sh)
                    cp.setClipPath(path)
                    cp.drawPixmap(0, 0, scaled)
                    cp.end()

                    lx = rect.x() + (rw - sw) / 2
                    ly = rect.y() + (rh - sh) / 2
                    painter.drawPixmap(int(lx), int(ly), circle)

            # Text
            if self._show_ticker and rw >= _MIN_TEXT_WIDTH and rh >= _MIN_TEXT_HEIGHT:
                painter.setPen(QColor(255, 255, 255))
                fs = self._font_size_for_rect(rw, rh)
                bold_font = QFont("Helvetica", fs)
                bold_font.setBold(True)
                painter.setFont(bold_font)
                text_rect = rect.adjusted(4, 2, -4, -2)

                if has_logo:
                    # Centered ticker above logo, centered % below
                    painter.drawText(text_rect, Qt.AlignTop | Qt.AlignHCenter, data["ticker"])
                    if rh >= _MIN_PCT_HEIGHT:
                        pct_text = f"{pct:+.2f}%"
                        small_font = QFont("Helvetica", max(7, fs - 2))
                        painter.setFont(small_font)
                        painter.drawText(text_rect, Qt.AlignBottom | Qt.AlignHCenter, pct_text)
                else:
                    # No logo — top-left ticker, bottom-left %
                    painter.drawText(text_rect, Qt.AlignTop | Qt.AlignLeft, data["ticker"])
                    if rh >= _MIN_PCT_HEIGHT:
                        pct_text = f"{pct:+.2f}%"
                        small_font = QFont("Helvetica", max(7, fs - 2))
                        painter.setFont(small_font)
                        painter.drawText(text_rect, Qt.AlignBottom | Qt.AlignLeft, pct_text)

        # Draw sector headers
        for sector_rect, sector_name in self._sector_rects:
            # Semi-transparent header background
            painter.fillRect(sector_rect, QColor(0, 0, 0, 120))
            painter.setPen(QColor(255, 255, 255, 240))
            header_font = QFont("Helvetica", 11)
            header_font.setBold(True)
            painter.setFont(header_font)
            # Truncate sector name if needed
            fm = painter.fontMetrics()
            elided = fm.elidedText(sector_name, Qt.ElideRight, int(sector_rect.width()) - 12)
            painter.drawText(sector_rect.adjusted(6, 0, -6, 0), Qt.AlignVCenter | Qt.AlignLeft, elided)

        painter.end()

    # ── Color mapping ─────────────────────────────────────────────────────

    def _pct_to_color(self, pct: float) -> QColor:
        scale = self._color_scale
        clamped = max(-scale, min(scale, pct))
        if clamped < 0:
            t = clamped / -scale
            r = int(_NEUTRAL[0] + t * (_RED[0] - _NEUTRAL[0]))
            g = int(_NEUTRAL[1] + t * (_RED[1] - _NEUTRAL[1]))
            b = int(_NEUTRAL[2] + t * (_RED[2] - _NEUTRAL[2]))
        else:
            t = clamped / scale
            r = int(_NEUTRAL[0] + t * (_GREEN[0] - _NEUTRAL[0]))
            g = int(_NEUTRAL[1] + t * (_GREEN[1] - _NEUTRAL[1]))
            b = int(_NEUTRAL[2] + t * (_GREEN[2] - _NEUTRAL[2]))
        return QColor(r, g, b)

    @staticmethod
    def _font_size_for_rect(w: float, h: float) -> int:
        area = w * h
        if area > 20000:
            return 12
        if area > 8000:
            return 10
        if area > 3000:
            return 9
        return 8

    # ── Mouse interaction ─────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            pos = event.position()
            for rect, data in self._rects:
                if rect.contains(pos):
                    self.ticker_clicked.emit(data["ticker"])
                    break
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        pos = event.position()
        found = -1
        for i, (rect, _) in enumerate(self._rects):
            if rect.contains(pos):
                found = i
                break

        if found != self._hovered_index:
            self._hovered_index = found
            if found >= 0 and self._show_hover_tooltip:
                data = self._rects[found][1]
                cap_str = self._format_market_cap(data.get("market_cap", 0))
                pct = data.get("pct_change", 0.0)
                pct_color = "#4caf50" if pct >= 0 else "#ef5350"
                QToolTip.showText(
                    event.globalPosition().toPoint(),
                    f"<b>{data.get('name', '')}</b> ({data['ticker']})<br>"
                    f"Change: <span style='color:{pct_color};font-weight:bold'>{pct:+.2f}%</span><br>"
                    f"Market Cap: {cap_str}<br>"
                    f"Sector: {data.get('sector', '')}",
                    self,
                )
            else:
                QToolTip.hideText()

    def leaveEvent(self, event):
        self._hovered_index = -1
        QToolTip.hideText()
        super().leaveEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._heatmap_data and not self._show_placeholder:
            self._compute_layout()

    # ── Context menu ──────────────────────────────────────────────────────

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        copy_action = menu.addAction("Copy to Clipboard")
        save_action = menu.addAction("Save as PNG...")

        action = menu.exec(event.globalPos())
        if action == copy_action:
            pixmap = self.grab()
            QApplication.clipboard().setPixmap(pixmap)
        elif action == save_action:
            from PySide6.QtWidgets import QFileDialog
            path, _ = QFileDialog.getSaveFileName(
                self, "Save Heatmap", "stock_heatmap.png", "PNG Files (*.png)"
            )
            if path:
                self.grab().save(path)

    # ── Helpers ───────────────────────────────────────────────────────────

    def _get_logo(self, ticker: str, logo_path: Optional[str]) -> Optional[QPixmap]:
        if not logo_path:
            return None
        if ticker in self._logo_cache:
            return self._logo_cache[ticker]

        if logo_path.endswith(".svg"):
            renderer = QSvgRenderer(logo_path)
            if not renderer.isValid():
                self._logo_cache[ticker] = None
                return None
            # Render SVG to a 128x128 pixmap
            pixmap = QPixmap(128, 128)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            renderer.render(painter)
            painter.end()
        else:
            pixmap = QPixmap(logo_path)

        if pixmap.isNull():
            self._logo_cache[ticker] = None
            return None
        self._logo_cache[ticker] = pixmap
        return pixmap

    @staticmethod
    def _format_market_cap(cap: float) -> str:
        if cap >= 1e12:
            return f"${cap / 1e12:.1f}T"
        if cap >= 1e9:
            return f"${cap / 1e9:.1f}B"
        if cap >= 1e6:
            return f"${cap / 1e6:.1f}M"
        return f"${cap:,.0f}"
