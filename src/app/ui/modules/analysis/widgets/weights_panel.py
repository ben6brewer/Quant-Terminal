"""Weights Panel - Right sidebar showing portfolio weights for special portfolios."""

from __future__ import annotations

from typing import Dict, Any, List

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
)
from PySide6.QtCore import Qt, Signal

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common import LazyThemeMixin
from app.services.theme_stylesheet_service import ThemeStylesheetService


class CollapsibleWeightsSection(QWidget):
    """A collapsible section with a header and weights table."""

    toggled = Signal()

    def __init__(self, title: str, metric_label: str, parent=None):
        super().__init__(parent)
        self._metric_label = metric_label

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 4)
        layout.setSpacing(2)

        # Header row
        header_row = QHBoxLayout()
        header_row.setSpacing(4)

        self.toggle_btn = QPushButton("v")
        self.toggle_btn.setFixedSize(20, 20)
        self.toggle_btn.setObjectName("toggle_btn")
        self.toggle_btn.clicked.connect(self._toggle)
        header_row.addWidget(self.toggle_btn)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("section_title")
        header_row.addWidget(self.title_label)

        header_row.addStretch()

        self.metric_value = QLabel("")
        self.metric_value.setObjectName("metric_value")
        header_row.addWidget(self.metric_value)

        layout.addLayout(header_row)

        # Weights table
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Ticker", "Weight %"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self.table.horizontalHeader().resizeSection(1, 80)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        layout.addWidget(self.table, stretch=0)

        self._expanded = True

    def _toggle(self):
        self._expanded = not self._expanded
        self.table.setVisible(self._expanded)
        self.toggle_btn.setText("v" if self._expanded else ">")
        self.toggled.emit()

    def ideal_table_height(self):
        row_count = self.table.rowCount()
        if row_count == 0:
            return 0
        row_h = self.table.verticalHeader().defaultSectionSize()
        header_h = self.table.horizontalHeader().height()
        return header_h + row_count * row_h + 2

    def set_data(self, tickers: List[str], weights: List[float], metric_value: float):
        """Populate the table with weights data.

        Only shows tickers with weight > 0.1%.
        """
        self.metric_value.setText(f"{self._metric_label}: {metric_value:.3f}")

        # Filter to significant weights and sort descending
        pairs = [(t, w) for t, w in zip(tickers, weights) if w > 0.001]
        pairs.sort(key=lambda p: p[1], reverse=True)

        self.table.setRowCount(len(pairs))
        for row, (ticker, weight) in enumerate(pairs):
            ticker_item = QTableWidgetItem(ticker)
            ticker_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.table.setItem(row, 0, ticker_item)

            weight_item = QTableWidgetItem(f"{weight * 100:.2f}%")
            weight_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row, 1, weight_item)

    def clear_data(self):
        self.table.setRowCount(0)
        self.table.setFixedHeight(0)
        self.metric_value.setText("")


class WeightsPanel(LazyThemeMixin, QWidget):
    """Right sidebar showing weights for Tangency, Min Vol, and Max Sortino portfolios."""

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._theme_dirty = False

        self.setFixedWidth(280)
        self._setup_ui()
        self._apply_theme()
        self.theme_manager.theme_changed.connect(self._on_theme_changed_lazy)

    def showEvent(self, event):
        super().showEvent(event)
        self._check_theme_dirty()
        self._distribute_heights()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._distribute_heights()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        # Header
        self._header = QLabel("Portfolio Weights")
        self._header.setObjectName("panel_header")
        self._header.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._header)

        # Three collapsible sections
        self.tangency_section = CollapsibleWeightsSection(
            "Max Sharpe", "Sharpe"
        )
        layout.addWidget(self.tangency_section, stretch=0)

        self.min_vol_section = CollapsibleWeightsSection(
            "Min Volatility", "Vol"
        )
        layout.addWidget(self.min_vol_section, stretch=0)

        self.sortino_section = CollapsibleWeightsSection(
            "Max Sortino", "Sortino"
        )
        layout.addWidget(self.sortino_section, stretch=0)

        self._sections = [self.tangency_section, self.min_vol_section, self.sortino_section]
        for s in self._sections:
            s.toggled.connect(self._distribute_heights)

        layout.addStretch(1)

    def _distribute_heights(self):
        visible = [s for s in self._sections if s.isVisible()]
        expanded = [s for s in visible if s._expanded]

        if not expanded or self.height() == 0:
            return

        layout = self.layout()
        margins = layout.contentsMargins()
        overhead = margins.top() + margins.bottom()
        overhead += self._header.sizeHint().height()
        overhead += layout.spacing() * len(visible)  # gaps between header and each section

        for s in visible:
            s_margins = s.layout().contentsMargins()
            overhead += s_margins.top() + s_margins.bottom()
            header_item = s.layout().itemAt(0)  # header_row QHBoxLayout
            if header_item:
                overhead += header_item.sizeHint().height()
            if s._expanded:
                overhead += s.layout().spacing()  # gap between section header and table

        available = self.height() - overhead

        ideals = [s.ideal_table_height() for s in expanded]
        total_ideal = sum(ideals)

        if total_ideal <= available:
            for s, ideal in zip(expanded, ideals):
                s.table.setFixedHeight(ideal)
        else:
            per_table = max(available // len(expanded), 0)
            for s in expanded:
                s.table.setFixedHeight(per_table)

    def set_results(self, results: Dict[str, Any], visibility: Dict[str, bool] | None = None):
        """Populate sections from EF results dict, respecting visibility toggles."""
        tickers = results["tickers"]
        show_sharpe = True if visibility is None else visibility.get("ef_show_max_sharpe", True)
        show_min_vol = True if visibility is None else visibility.get("ef_show_min_vol", True)
        show_sortino = True if visibility is None else visibility.get("ef_show_max_sortino", True)

        if show_sharpe:
            self.tangency_section.set_data(
                tickers, results["tangency_weights"], results["sharpe_ratio"]
            )
            self.tangency_section.show()
        else:
            self.tangency_section.clear_data()
            self.tangency_section.hide()

        if show_min_vol:
            self.min_vol_section.set_data(
                tickers, results["min_vol_weights"], results["min_vol_vol"]
            )
            self.min_vol_section.show()
        else:
            self.min_vol_section.clear_data()
            self.min_vol_section.hide()

        if show_sortino:
            self.sortino_section.set_data(
                tickers, results["sortino_weights"], results["sortino_ratio"]
            )
            self.sortino_section.show()
        else:
            self.sortino_section.clear_data()
            self.sortino_section.hide()

        self._distribute_heights()

    def clear_results(self):
        """Clear all sections."""
        self.tangency_section.clear_data()
        self.min_vol_section.clear_data()
        self.sortino_section.clear_data()
        self._distribute_heights()

    def _apply_theme(self):
        c = ThemeStylesheetService.get_colors(self.theme_manager.current_theme)

        self.setStyleSheet(f"""
            QWidget {{
                background-color: {c['bg']};
                color: {c['text']};
            }}
            QLabel#panel_header {{
                font-size: 15px;
                font-weight: bold;
                color: {c['accent']};
                background: transparent;
                padding: 4px;
            }}
            QLabel#section_title {{
                font-size: 13px;
                font-weight: bold;
                color: {c['text']};
                background: transparent;
            }}
            QLabel#metric_value {{
                font-size: 12px;
                color: {c['accent']};
                background: transparent;
            }}
            QPushButton#toggle_btn {{
                background: transparent;
                color: {c['text_muted']};
                border: none;
                font-size: 12px;
            }}
            QTableWidget {{
                background-color: {c['bg_alt']};
                alternate-background-color: {c['bg']};
                color: {c['text']};
                gridline-color: {c['border']};
                border: 1px solid {c['border']};
                font-size: 12px;
            }}
            QTableWidget::item {{
                padding: 2px 4px;
            }}
            QHeaderView::section {{
                background-color: {c['bg_header']};
                color: {c['text_muted']};
                border: 1px solid {c['border']};
                padding: 3px 6px;
                font-size: 11px;
                font-weight: bold;
            }}
        """)
