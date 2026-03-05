"""Portfolio Toolbar - Top Control Bar."""

from typing import List
from PySide6.QtWidgets import QHBoxLayout, QLabel, QComboBox, QPushButton, QSizePolicy
from PySide6.QtCore import Signal

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common import SmoothScrollListView
from app.ui.modules.module_toolbar import ModuleToolbar


class PortfolioToolbar(ModuleToolbar):
    """Toolbar: Home | stretch | Portfolio | Save/Import/Export/Rename/Delete | stretch | Settings."""

    portfolio_changed = Signal(str)
    save_clicked = Signal()
    import_clicked = Signal()
    export_clicked = Signal()
    new_portfolio_clicked = Signal()
    rename_portfolio_clicked = Signal()
    delete_portfolio_clicked = Signal()

    def setup_center(self, layout: QHBoxLayout):
        layout.addStretch(1)

        # Portfolio selector
        self.portfolio_label = QLabel("Portfolio:")
        self.portfolio_label.setObjectName("portfolio_label")
        layout.addWidget(self.portfolio_label)
        self.portfolio_combo = QComboBox()
        self.portfolio_combo.setEditable(True)
        self.portfolio_combo.lineEdit().setReadOnly(True)
        self.portfolio_combo.lineEdit().setPlaceholderText("Select Portfolio...")
        self.portfolio_combo.setMinimumWidth(150)
        self.portfolio_combo.setMaximumWidth(250)
        self.portfolio_combo.setFixedHeight(45)
        self.portfolio_combo.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        smooth_view = SmoothScrollListView(self.portfolio_combo)
        smooth_view.setAlternatingRowColors(True)
        self.portfolio_combo.setView(smooth_view)
        self.portfolio_combo.currentTextChanged.connect(self._on_portfolio_changed)
        layout.addWidget(self.portfolio_combo)

        layout.addSpacing(8)

        # Save button
        self.save_btn = QPushButton("Save")
        self.save_btn.setMinimumWidth(55)
        self.save_btn.setMaximumWidth(80)
        self.save_btn.setFixedHeight(40)
        self.save_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.save_btn.clicked.connect(self.save_clicked.emit)
        layout.addWidget(self.save_btn)

        layout.addSpacing(4)

        # Import button
        self.import_btn = QPushButton("Import")
        self.import_btn.setMinimumWidth(55)
        self.import_btn.setMaximumWidth(80)
        self.import_btn.setFixedHeight(40)
        self.import_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.import_btn.clicked.connect(self.import_clicked.emit)
        layout.addWidget(self.import_btn)

        layout.addSpacing(4)

        # Export button
        self.export_btn = QPushButton("Export")
        self.export_btn.setMinimumWidth(55)
        self.export_btn.setMaximumWidth(80)
        self.export_btn.setFixedHeight(40)
        self.export_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.export_btn.clicked.connect(self.export_clicked.emit)
        layout.addWidget(self.export_btn)

        layout.addSpacing(4)

        # Rename button
        self.rename_btn = QPushButton("Rename")
        self.rename_btn.setMinimumWidth(55)
        self.rename_btn.setMaximumWidth(80)
        self.rename_btn.setFixedHeight(40)
        self.rename_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.rename_btn.clicked.connect(self.rename_portfolio_clicked.emit)
        layout.addWidget(self.rename_btn)

        layout.addSpacing(4)

        # Delete button
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setMinimumWidth(55)
        self.delete_btn.setMaximumWidth(80)
        self.delete_btn.setFixedHeight(40)
        self.delete_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.delete_btn.setObjectName("delete_btn")
        self.delete_btn.clicked.connect(self.delete_portfolio_clicked.emit)
        layout.addWidget(self.delete_btn)

    def _on_portfolio_changed(self, name: str):
        if name == "Create New Portfolio":
            self.portfolio_combo.blockSignals(True)
            found_portfolio = False
            for i in range(self.portfolio_combo.count()):
                item_text = self.portfolio_combo.itemText(i)
                if item_text != "Create New Portfolio":
                    self.portfolio_combo.setCurrentIndex(i)
                    if item_text.startswith("[Port] "):
                        self.portfolio_combo.lineEdit().setText(item_text[7:])
                    found_portfolio = True
                    break
            if not found_portfolio:
                self.portfolio_combo.setCurrentIndex(-1)
            self.portfolio_combo.blockSignals(False)
            self.new_portfolio_clicked.emit()
        elif name:
            if name.startswith("[Port] "):
                self.portfolio_combo.lineEdit().setText(name[7:])
            self.portfolio_changed.emit(name)

    def set_view_mode(self, is_transaction_view: bool):
        self.save_btn.setVisible(is_transaction_view)
        self.import_btn.setVisible(is_transaction_view)
        self.rename_btn.setVisible(is_transaction_view)
        self.delete_btn.setVisible(is_transaction_view)

    def update_portfolio_list(self, portfolios: List[str], current: str = None):
        self.portfolio_combo.blockSignals(True)
        self.portfolio_combo.clear()
        self.portfolio_combo.addItem("Create New Portfolio")
        for p in portfolios:
            self.portfolio_combo.addItem(f"[Port] {p}")
        if current and current in portfolios:
            self.portfolio_combo.setCurrentText(f"[Port] {current}")
            self.portfolio_combo.lineEdit().setText(current)
        else:
            self.portfolio_combo.setCurrentIndex(-1)
        self.portfolio_combo.blockSignals(False)
        self._update_button_states(current is not None and current in portfolios)

    def _update_button_states(self, portfolio_loaded: bool):
        self.save_btn.setEnabled(portfolio_loaded)
        self.import_btn.setEnabled(portfolio_loaded)
        self.export_btn.setEnabled(portfolio_loaded)
        self.rename_btn.setEnabled(portfolio_loaded)
        self.delete_btn.setEnabled(portfolio_loaded)

    def get_current_portfolio(self) -> str:
        current = self.portfolio_combo.currentText()
        if not current or current == "Create New Portfolio":
            return ""
        return current
