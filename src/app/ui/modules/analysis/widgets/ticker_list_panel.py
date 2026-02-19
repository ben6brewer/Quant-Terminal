"""Ticker List Panel - Left sidebar for adding/removing tickers."""

from typing import List

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QAbstractItemView,
    QLineEdit,
)
from PySide6.QtCore import Signal, Qt

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common import LazyThemeMixin, AutoSelectLineEdit, ThemedDialog, VerticalLabel
from app.services.theme_stylesheet_service import ThemeStylesheetService
from ..services.ticker_list_persistence import TickerListPersistence


class SaveTickerListDialog(ThemedDialog):
    """Dialog for saving the current ticker list with a name."""

    def __init__(self, theme_manager: ThemeManager, parent=None):
        self.saved_name = None
        super().__init__(theme_manager, "Save Ticker List", parent, min_width=320)

    def _setup_content(self, layout):
        label = QLabel("List name:")
        label.setObjectName("descLabel")
        layout.addWidget(label)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g. Tech Stocks")
        self.name_input.setFixedHeight(36)
        self.name_input.returnPressed.connect(self._on_save)
        layout.addWidget(self.name_input)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(32)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.setFixedHeight(32)
        save_btn.setObjectName("accentButton")
        save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(save_btn)

        layout.addLayout(btn_row)

    def _on_save(self):
        name = self.name_input.text().strip()
        if name:
            self.saved_name = name
            self.accept()

    def _apply_theme(self):
        super()._apply_theme()
        c = ThemeStylesheetService.get_colors(self.theme_manager.current_theme)
        self.setStyleSheet(self.styleSheet() + f"""
            QLineEdit {{
                background-color: {c['bg_header']};
                color: {c['text']};
                border: 1px solid {c['border']};
                border-radius: 3px;
                padding: 6px 10px;
                font-size: 14px;
            }}
            QLineEdit:focus {{
                border-color: {c['accent']};
            }}
            QPushButton {{
                background-color: {c['bg_header']};
                color: {c['text']};
                border: 1px solid {c['border']};
                border-radius: 3px;
                padding: 6px 16px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                border-color: {c['accent']};
            }}
            QPushButton#accentButton {{
                background-color: {c['accent']};
                color: {c['text_on_accent']};
                border: 1px solid {c['accent']};
                font-weight: bold;
            }}
        """)


class LoadTickerListDialog(ThemedDialog):
    """Dialog for loading a saved ticker list."""

    def __init__(self, theme_manager: ThemeManager, parent=None):
        self.selected_name = None
        super().__init__(theme_manager, "Load Ticker List", parent, min_width=320, min_height=300)

    def _setup_content(self, layout):
        names = TickerListPersistence.list_all()

        if not names:
            empty_label = QLabel("No saved ticker lists.")
            empty_label.setObjectName("descLabel")
            empty_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(empty_label)
            layout.addStretch()
            return

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.NoSelection)
        self.list_widget.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        for name in names:
            self._add_list_row(name)

        layout.addWidget(self.list_widget, stretch=1)

    def _add_list_row(self, name: str):
        item = QListWidgetItem()
        item.setSizeHint(item.sizeHint().__class__(0, 36))

        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(8, 4, 4, 4)
        row_layout.setSpacing(6)

        name_btn = QPushButton(name)
        name_btn.setObjectName("listNameBtn")
        name_btn.setCursor(Qt.PointingHandCursor)
        name_btn.clicked.connect(lambda checked, n=name: self._on_select(n))
        row_layout.addWidget(name_btn, stretch=1)

        delete_btn = QPushButton("x")
        delete_btn.setFixedSize(24, 24)
        delete_btn.setObjectName("deleteBtn")
        delete_btn.setCursor(Qt.PointingHandCursor)
        delete_btn.clicked.connect(lambda checked, n=name: self._on_delete(n))
        row_layout.addWidget(delete_btn)

        self.list_widget.addItem(item)
        self.list_widget.setItemWidget(item, row_widget)

    def _on_select(self, name: str):
        self.selected_name = name
        self.accept()

    def _on_delete(self, name: str):
        TickerListPersistence.delete_list(name)
        # Rebuild list
        self.list_widget.clear()
        for n in TickerListPersistence.list_all():
            self._add_list_row(n)
        if self.list_widget.count() == 0:
            # No more lists — close dialog
            self.reject()

    def _apply_theme(self):
        super()._apply_theme()
        c = ThemeStylesheetService.get_colors(self.theme_manager.current_theme)

        if self.theme_manager.current_theme == "dark":
            delete_hover = "#ff4444"
        elif self.theme_manager.current_theme == "light":
            delete_hover = "#cc0000"
        else:
            delete_hover = "#ff4444"

        self.setStyleSheet(self.styleSheet() + f"""
            QListWidget {{
                background-color: {c['bg_alt']};
                border: 1px solid {c['border']};
                border-radius: 3px;
                outline: none;
            }}
            QListWidget::item {{
                border-bottom: 1px solid {c['border']};
                padding: 0px;
            }}
            QPushButton#listNameBtn {{
                background: transparent;
                color: {c['text']};
                border: none;
                text-align: left;
                padding: 4px 8px;
                font-size: 13px;
            }}
            QPushButton#listNameBtn:hover {{
                color: {c['accent']};
            }}
            QPushButton#deleteBtn {{
                background: transparent;
                color: {c['text_muted']};
                border: none;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton#deleteBtn:hover {{
                color: {delete_hover};
            }}
        """)


class TickerListPanel(LazyThemeMixin, QWidget):
    """Left sidebar panel for managing a list of tickers.

    Provides an input field, scrollable list with delete buttons, and clear all.
    """

    _EXPANDED_WIDTH = 200
    _COLLAPSED_WIDTH = 36

    tickers_changed = Signal(list)

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._theme_dirty = False
        self._tickers: List[str] = []
        self._expanded = True

        self.setFixedWidth(self._EXPANDED_WIDTH)
        self._setup_ui()
        self._apply_theme()
        self.theme_manager.theme_changed.connect(self._on_theme_changed_lazy)

    def showEvent(self, event):
        super().showEvent(event)
        self._check_theme_dirty()

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Header row (title + toggle button)
        header_row = QHBoxLayout()
        header_row.setContentsMargins(4, 6, 4, 2)
        header_row.setSpacing(4)

        self._header = QLabel("Tickers")
        self._header.setObjectName("panel_header")
        self._header.setAlignment(Qt.AlignCenter)
        header_row.addWidget(self._header, 1)

        self._toggle_btn = QPushButton("\u25B6")
        self._toggle_btn.setObjectName("collapse_btn")
        self._toggle_btn.setFixedSize(24, 24)
        self._toggle_btn.setCursor(Qt.PointingHandCursor)
        self._toggle_btn.clicked.connect(self._toggle)
        header_row.addWidget(self._toggle_btn)

        outer.addLayout(header_row)

        # Body (all content below header)
        self._body = QWidget()
        body_layout = QVBoxLayout(self._body)
        body_layout.setContentsMargins(8, 4, 8, 8)
        body_layout.setSpacing(6)

        # Ticker input row
        input_row = QHBoxLayout()
        input_row.setSpacing(4)

        self.ticker_input = AutoSelectLineEdit()
        self.ticker_input.setPlaceholderText("Add ticker...")
        self.ticker_input.setFixedHeight(32)
        self.ticker_input.returnPressed.connect(self._add_ticker)
        input_row.addWidget(self.ticker_input)

        self.add_btn = QPushButton("+")
        self.add_btn.setFixedSize(32, 32)
        self.add_btn.setObjectName("add_btn")
        self.add_btn.clicked.connect(self._add_ticker)
        input_row.addWidget(self.add_btn)

        body_layout.addLayout(input_row)

        # Ticker list
        self.ticker_list = QListWidget()
        self.ticker_list.setSelectionMode(QAbstractItemView.NoSelection)
        self.ticker_list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.ticker_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        body_layout.addWidget(self.ticker_list, stretch=1)

        # Count label + Clear button
        bottom_row = QHBoxLayout()
        self.count_label = QLabel("0 tickers")
        self.count_label.setObjectName("count_label")
        bottom_row.addWidget(self.count_label)
        bottom_row.addStretch()

        self.clear_btn = QPushButton("Clear All")
        self.clear_btn.setFixedHeight(28)
        self.clear_btn.setObjectName("clear_btn")
        self.clear_btn.clicked.connect(self._clear_all)
        bottom_row.addWidget(self.clear_btn)

        body_layout.addLayout(bottom_row)

        # Save / Load buttons
        save_load_row = QHBoxLayout()
        save_load_row.setSpacing(6)

        self.save_btn = QPushButton("Save List")
        self.save_btn.setFixedHeight(28)
        self.save_btn.setObjectName("save_btn")
        self.save_btn.clicked.connect(self._show_save_dialog)
        save_load_row.addWidget(self.save_btn)

        self.load_btn = QPushButton("Load")
        self.load_btn.setFixedHeight(28)
        self.load_btn.setObjectName("load_btn")
        self.load_btn.clicked.connect(self._show_load_dialog)
        save_load_row.addWidget(self.load_btn)

        body_layout.addLayout(save_load_row)

        outer.addWidget(self._body)

        # Collapsed vertical label (hidden by default)
        self._collapsed_label = VerticalLabel("Tickers")
        self._collapsed_label.setObjectName("collapsed_label")
        self._collapsed_label.setAlignment(Qt.AlignCenter)
        self._collapsed_label.hide()
        outer.addWidget(self._collapsed_label, 1)

    def _toggle(self):
        """Toggle between expanded and collapsed states."""
        self._expanded = not self._expanded
        self._body.setVisible(self._expanded)
        self._header.setVisible(self._expanded)
        self._collapsed_label.setVisible(not self._expanded)
        self._toggle_btn.setText("\u25B6" if self._expanded else "\u25C0")
        self.setFixedWidth(
            self._EXPANDED_WIDTH if self._expanded else self._COLLAPSED_WIDTH
        )

    def _add_ticker(self):
        """Add a ticker from the input field."""
        text = self.ticker_input.text().strip().upper()
        if not text or text in self._tickers:
            self.ticker_input.clear()
            return

        self._tickers.append(text)
        self._refresh_list()
        self.ticker_input.clear()
        self.tickers_changed.emit(list(self._tickers))

    def _remove_ticker(self, ticker: str):
        """Remove a specific ticker."""
        if ticker in self._tickers:
            self._tickers.remove(ticker)
            self._refresh_list()
            self.tickers_changed.emit(list(self._tickers))

    def _clear_all(self):
        """Remove all tickers."""
        if not self._tickers:
            return
        self._tickers.clear()
        self._refresh_list()
        self.tickers_changed.emit(list(self._tickers))

    def _refresh_list(self):
        """Rebuild the QListWidget from internal ticker list."""
        self.ticker_list.clear()
        for ticker in self._tickers:
            item = QListWidgetItem()
            item.setSizeHint(item.sizeHint().__class__(0, 30))

            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(6, 2, 2, 2)
            row_layout.setSpacing(4)

            label = QLabel(ticker)
            label.setObjectName("ticker_label")
            row_layout.addWidget(label)
            row_layout.addStretch()

            remove_btn = QPushButton("x")
            remove_btn.setFixedSize(22, 22)
            remove_btn.setObjectName("remove_btn")
            remove_btn.clicked.connect(lambda checked, t=ticker: self._remove_ticker(t))
            row_layout.addWidget(remove_btn)

            self.ticker_list.addItem(item)
            self.ticker_list.setItemWidget(item, row_widget)

        n = len(self._tickers)
        self.count_label.setText(f"{n} ticker{'s' if n != 1 else ''}")

    def set_tickers(self, tickers: List[str]):
        """Set the ticker list (replaces existing)."""
        self._tickers = list(tickers)
        self._refresh_list()

    def get_tickers(self) -> List[str]:
        """Get the current ticker list."""
        return list(self._tickers)

    def _show_save_dialog(self):
        """Open dialog to save current tickers as a named list."""
        if not self._tickers:
            return
        dialog = SaveTickerListDialog(self.theme_manager, self)
        if dialog.exec() and dialog.saved_name:
            TickerListPersistence.save_list(dialog.saved_name, self._tickers)

    def _show_load_dialog(self):
        """Open dialog to load a saved ticker list."""
        dialog = LoadTickerListDialog(self.theme_manager, self)
        if dialog.exec() and dialog.selected_name:
            tickers = TickerListPersistence.load_list(dialog.selected_name)
            if tickers is not None:
                self._tickers = tickers
                self._refresh_list()
                self.tickers_changed.emit(list(self._tickers))

    def _apply_theme(self):
        c = ThemeStylesheetService.get_colors(self.theme_manager.current_theme)

        if self.theme_manager.current_theme == "dark":
            remove_hover = "#ff4444"
            add_hover = "#00bfe6"
        elif self.theme_manager.current_theme == "light":
            remove_hover = "#cc0000"
            add_hover = "#0055aa"
        else:  # bloomberg
            remove_hover = "#ff4444"
            add_hover = "#e67300"

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
            QLabel#ticker_label {{
                font-size: 13px;
                color: {c['text']};
                background: transparent;
            }}
            QLabel#count_label {{
                font-size: 12px;
                color: {c['text_muted']};
                background: transparent;
            }}
            QLineEdit {{
                background-color: {c['bg_header']};
                color: {c['text']};
                border: 1px solid {c['border']};
                border-radius: 3px;
                padding: 4px 8px;
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border-color: {c['accent']};
            }}
            QListWidget {{
                background-color: {c['bg_alt']};
                border: 1px solid {c['border']};
                border-radius: 3px;
                outline: none;
            }}
            QListWidget::item {{
                border-bottom: 1px solid {c['border']};
                padding: 0px;
            }}
            QPushButton#add_btn {{
                background-color: {c['accent']};
                color: {c['text_on_accent']};
                border: none;
                border-radius: 3px;
                font-size: 16px;
                font-weight: bold;
            }}
            QPushButton#add_btn:hover {{
                background-color: {add_hover};
            }}
            QPushButton#remove_btn {{
                background-color: transparent;
                color: {c['text_muted']};
                border: none;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton#remove_btn:hover {{
                color: {remove_hover};
            }}
            QPushButton#clear_btn {{
                background-color: {c['bg_header']};
                color: {c['text_muted']};
                border: 1px solid {c['border']};
                border-radius: 3px;
                padding: 2px 8px;
                font-size: 12px;
            }}
            QPushButton#clear_btn:hover {{
                color: {remove_hover};
                border-color: {remove_hover};
            }}
            QPushButton#save_btn, QPushButton#load_btn {{
                background-color: {c['bg_header']};
                color: {c['text']};
                border: 1px solid {c['border']};
                border-radius: 3px;
                padding: 2px 8px;
                font-size: 12px;
            }}
            QPushButton#save_btn:hover, QPushButton#load_btn:hover {{
                border-color: {c['accent']};
                color: {c['accent']};
            }}
            QPushButton#collapse_btn {{
                background: transparent;
                color: {c['text_muted']};
                border: none;
                font-size: 12px;
                padding: 0px;
            }}
            QPushButton#collapse_btn:hover {{
                color: {c['accent']};
            }}
            QLabel#collapsed_label {{
                font-size: 12px;
                font-weight: bold;
                color: {c['text_muted']};
                background: transparent;
            }}
        """)
