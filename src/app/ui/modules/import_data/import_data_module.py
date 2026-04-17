"""Import Data module: import & manage user-supplied custom return series."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QStackedWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.theme_manager import ThemeManager
from app.services.custom_data_service import (
    CustomImportMeta,
    delete_custom_import,
    list_custom_tickers,
    save_custom_import,
)
from app.ui.modules.base_module import BaseModule
from app.ui.widgets.common import CustomMessageBox, SmoothScrollTableWidget

from .import_dialog import ImportDialog
from .parser import parse_returns_file


_COLUMNS = [
    "Name",
    "Asset Class",
    "Frequency",
    "Start Date",
    "End Date",
    "# Rows",
    "Imported At",
]


def _parse_and_save(
    file_path: str,
    name: str,
    frequency: str,
    asset_class: str,
) -> CustomImportMeta:
    """Worker function: parse the file, then persist."""
    series = parse_returns_file(file_path)
    return save_custom_import(
        name=name,
        returns=series,
        frequency=frequency,
        asset_class=asset_class,
        source_filename=Path(file_path).name,
    )


class ImportDataModule(BaseModule):
    """Manage user-imported custom return series."""

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(theme_manager, parent)
        self._table: Optional[SmoothScrollTableWidget] = None
        self._empty_label: Optional[QLabel] = None
        self._stack: Optional[QStackedWidget] = None
        self._setup_ui()
        self._refresh_table()

    # ── Layout ───────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 70, 40, 40)
        layout.setSpacing(20)

        # Header row: title + buttons
        header_row = QHBoxLayout()
        header_row.setSpacing(10)

        title = QLabel("Import Data")
        title.setObjectName("headerLabel")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        header_row.addWidget(title)

        header_row.addStretch()

        self._import_btn = QPushButton("Import New")
        self._import_btn.setCursor(Qt.PointingHandCursor)
        self._import_btn.clicked.connect(self._on_import_new)
        header_row.addWidget(self._import_btn)

        self._reimport_btn = QPushButton("Reimport Selected")
        self._reimport_btn.setCursor(Qt.PointingHandCursor)
        self._reimport_btn.clicked.connect(self._on_reimport_selected)
        header_row.addWidget(self._reimport_btn)

        self._delete_btn = QPushButton("Delete Selected")
        self._delete_btn.setCursor(Qt.PointingHandCursor)
        self._delete_btn.clicked.connect(self._on_delete_selected)
        header_row.addWidget(self._delete_btn)

        layout.addLayout(header_row)

        # Help / hint
        hint = QLabel(
            "Custom imports are referenced from other modules with the prefix "
            "<b>[Custom] tickername</b> (e.g. <code>[Custom] MyFund</code>). "
            "Files must have two columns: <b>Date</b> and <b>Value</b> "
            "(decimal returns; trailing '%' auto-stripped)."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #888888;")
        layout.addWidget(hint)

        # Stack: empty-state vs table
        self._stack = QStackedWidget()

        # Empty-state widget
        empty_holder = QWidget()
        empty_layout = QVBoxLayout(empty_holder)
        empty_layout.addStretch()
        self._empty_label = QLabel(
            "No custom data imported yet.\nClick 'Import New' to add a CSV/XLSX of returns."
        )
        self._empty_label.setAlignment(Qt.AlignCenter)
        self._empty_label.setStyleSheet("color: #888888; font-size: 14px;")
        empty_layout.addWidget(self._empty_label)
        empty_layout.addStretch()
        self._stack.addWidget(empty_holder)

        # Table
        self._table = SmoothScrollTableWidget()
        self._table.setColumnCount(len(_COLUMNS))
        self._table.setHorizontalHeaderLabels(_COLUMNS)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setAlternatingRowColors(True)
        self._table.setSortingEnabled(True)
        self._table.verticalHeader().setVisible(False)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)
        self._stack.addWidget(self._table)

        layout.addWidget(self._stack, stretch=1)

    # ── Table state ──────────────────────────────────────────────────────

    def _refresh_table(self) -> None:
        items = list_custom_tickers()
        if not items:
            self._stack.setCurrentIndex(0)
            self._reimport_btn.setEnabled(False)
            self._delete_btn.setEnabled(False)
            return

        self._stack.setCurrentIndex(1)
        self._reimport_btn.setEnabled(True)
        self._delete_btn.setEnabled(True)

        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(items))
        for row, m in enumerate(items):
            self._set_row(row, m)
        self._table.setSortingEnabled(True)
        self._table.resizeColumnsToContents()

    def _set_row(self, row: int, meta: CustomImportMeta) -> None:
        cells = [
            meta.name,
            meta.asset_class,
            meta.frequency.capitalize(),
            meta.start_date,
            meta.end_date,
            str(meta.row_count),
            meta.imported_at,
        ]
        for col, value in enumerate(cells):
            item = QTableWidgetItem(value)
            if col == 5:
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self._table.setItem(row, col, item)

    def _selected_meta(self) -> Optional[CustomImportMeta]:
        if self._table is None:
            return None
        row = self._table.currentRow()
        if row < 0:
            return None
        name_item = self._table.item(row, 0)
        if name_item is None:
            return None
        from app.services.custom_data_service import get_metadata
        return get_metadata(name_item.text())

    # ── Actions ──────────────────────────────────────────────────────────

    def _existing_names(self) -> List[str]:
        return [m.name for m in list_custom_tickers()]

    def _on_import_new(self) -> None:
        dialog = ImportDialog(
            theme_manager=self.theme_manager,
            existing_names=self._existing_names(),
            reimport_target=None,
            parent=self,
        )
        if dialog.exec() != ImportDialog.Accepted:
            return
        self._launch_save_worker(
            file_path=dialog.get_file_path(),
            name=dialog.get_name(),
            frequency=dialog.get_frequency(),
            asset_class=dialog.get_asset_class(),
        )

    def _on_reimport_selected(self) -> None:
        meta = self._selected_meta()
        if meta is None:
            CustomMessageBox.information(
                self.theme_manager, self,
                "No selection",
                "Select an import to reimport, or click 'Import New'."
            )
            return
        dialog = ImportDialog(
            theme_manager=self.theme_manager,
            existing_names=self._existing_names(),
            reimport_target=meta,
            parent=self,
        )
        if dialog.exec() != ImportDialog.Accepted:
            return
        self._launch_save_worker(
            file_path=dialog.get_file_path(),
            name=dialog.get_name(),
            frequency=dialog.get_frequency(),
            asset_class=dialog.get_asset_class(),
        )

    def _on_delete_selected(self) -> None:
        meta = self._selected_meta()
        if meta is None:
            CustomMessageBox.information(
                self.theme_manager, self,
                "No selection",
                "Select an import to delete."
            )
            return
        response = CustomMessageBox.question(
            self.theme_manager, self,
            "Delete custom import?",
            f"Permanently delete '{meta.name}'? This cannot be undone."
        )
        if response != CustomMessageBox.Yes:
            return
        try:
            delete_custom_import(meta.name)
        except Exception as e:
            CustomMessageBox.critical(
                self.theme_manager, self, "Delete failed", str(e)
            )
            return
        self._refresh_table()

    def _launch_save_worker(
        self,
        file_path: str,
        name: str,
        frequency: str,
        asset_class: str,
    ) -> None:
        self._run_worker(
            _parse_and_save,
            file_path,
            name,
            frequency,
            asset_class,
            loading_message=f"Importing {name}...",
            on_complete=self._on_save_complete,
            on_error=self._on_save_error,
        )

    def _on_save_complete(self, meta: CustomImportMeta) -> None:
        self._refresh_table()
        CustomMessageBox.information(
            self.theme_manager, self,
            "Import complete",
            f"Imported '{meta.name}' ({meta.row_count} rows, "
            f"{meta.start_date} → {meta.end_date}).\n\n"
            f"Reference it from other modules as: [Custom] {meta.name}"
        )

    def _on_save_error(self, error_msg: str) -> None:
        CustomMessageBox.critical(
            self.theme_manager, self, "Import failed", error_msg
        )

    # ── Events ───────────────────────────────────────────────────────────

    def showEvent(self, event):
        super().showEvent(event)
        self._refresh_table()
