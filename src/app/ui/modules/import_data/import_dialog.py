"""Dialog for importing a custom returns series from CSV/XLSX."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from app.core.theme_manager import ThemeManager
from app.services.custom_data_service import (
    ALLOWED_FREQUENCIES,
    ASSET_CLASSES,
    CustomImportMeta,
)
from app.ui.widgets.common import (
    CustomMessageBox,
    NoScrollComboBox,
    ThemedDialog,
)


_INVALID_NAME_CHARS = set("[]/\\")
_WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
}


class ImportDialog(ThemedDialog):
    """Capture: file path + ticker name + frequency + asset class."""

    def __init__(
        self,
        theme_manager: ThemeManager,
        existing_names: List[str],
        reimport_target: Optional[CustomImportMeta] = None,
        parent=None,
    ):
        self._existing_lower = {n.lower() for n in existing_names}
        self._reimport_target = reimport_target
        self._file_path: str = ""
        self._confirmed_overwrite: bool = reimport_target is not None
        # Widgets — populated in _setup_content
        self._path_edit: Optional[QLineEdit] = None
        self._name_edit: Optional[QLineEdit] = None
        self._frequency_combo: Optional[NoScrollComboBox] = None
        self._asset_class_combo: Optional[NoScrollComboBox] = None

        title = (
            f"Reimport: {reimport_target.name}"
            if reimport_target is not None
            else "Import Custom Data"
        )
        super().__init__(theme_manager, title, parent, min_width=520)

    # ── Layout ───────────────────────────────────────────────────────────

    def _setup_content(self, layout: QVBoxLayout):
        layout.setSpacing(10)

        help_label = QLabel(
            "Pick a CSV or XLSX with two columns: <b>Date</b> and <b>Value</b>.<br>"
            "Values must be decimal returns (e.g. 0.05 = 5%). A trailing "
            "'%' will be auto-stripped."
        )
        help_label.setWordWrap(True)
        layout.addWidget(help_label)

        # File row
        layout.addWidget(QLabel("File:"))
        file_row = QHBoxLayout()
        self._path_edit = QLineEdit()
        self._path_edit.setReadOnly(True)
        self._path_edit.setPlaceholderText("No file selected...")
        file_row.addWidget(self._path_edit, stretch=1)
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._on_browse)
        file_row.addWidget(browse_btn)
        layout.addLayout(file_row)

        # Ticker name
        layout.addWidget(QLabel("Ticker Name:"))
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("e.g. MyCustomFund")
        if self._reimport_target is not None:
            self._name_edit.setText(self._reimport_target.name)
            self._name_edit.setEnabled(False)
        layout.addWidget(self._name_edit)

        # Frequency
        layout.addWidget(QLabel("Frequency:"))
        self._frequency_combo = NoScrollComboBox()
        self._frequency_combo.addItems([f.capitalize() for f in ALLOWED_FREQUENCIES])
        if self._reimport_target is not None:
            idx = self._frequency_combo.findText(
                self._reimport_target.frequency.capitalize()
            )
            if idx >= 0:
                self._frequency_combo.setCurrentIndex(idx)
        layout.addWidget(self._frequency_combo)

        # Asset class
        layout.addWidget(QLabel("Asset Class:"))
        self._asset_class_combo = NoScrollComboBox()
        self._asset_class_combo.addItems(ASSET_CLASSES)
        if self._reimport_target is not None:
            idx = self._asset_class_combo.findText(self._reimport_target.asset_class)
            if idx >= 0:
                self._asset_class_combo.setCurrentIndex(idx)
        layout.addWidget(self._asset_class_combo)

        layout.addSpacing(6)

        # Buttons
        button_row = QHBoxLayout()
        button_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(cancel_btn)
        import_btn = QPushButton("Import")
        import_btn.setObjectName("defaultButton")
        import_btn.setDefault(True)
        import_btn.clicked.connect(self._validate_and_accept)
        button_row.addWidget(import_btn)
        layout.addLayout(button_row)

    # ── Handlers ─────────────────────────────────────────────────────────

    def _on_browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select returns file",
            "",
            "CSV or Excel (*.csv *.xlsx *.xls);;All Files (*.*)",
        )
        if path:
            self._file_path = path
            self._path_edit.setText(path)

    def _validate_and_accept(self):
        # File required and exists
        if not self._file_path or not Path(self._file_path).exists():
            CustomMessageBox.warning(
                self.theme_manager, self, "No file selected",
                "Please choose a CSV or XLSX file to import."
            )
            return
        ext = Path(self._file_path).suffix.lower()
        if ext not in {".csv", ".xlsx", ".xls"}:
            CustomMessageBox.warning(
                self.theme_manager, self, "Unsupported file type",
                f"File extension {ext!r} is not supported. Use .csv, .xlsx or .xls."
            )
            return

        # Name validation (skip on reimport — name is locked)
        name = self._name_edit.text().strip()
        if not name:
            CustomMessageBox.warning(
                self.theme_manager, self, "Missing name",
                "Enter a ticker name."
            )
            return

        if any(c in _INVALID_NAME_CHARS for c in name):
            CustomMessageBox.warning(
                self.theme_manager, self, "Invalid name",
                "Ticker name cannot contain '[', ']', '/' or '\\'."
            )
            return
        if name.upper() in _WINDOWS_RESERVED:
            CustomMessageBox.warning(
                self.theme_manager, self, "Invalid name",
                f"{name!r} is a reserved name on Windows. Pick a different name."
            )
            return

        # Conflict check (skip if this is a reimport of the same name)
        is_reimport = self._reimport_target is not None
        if not is_reimport and name.lower() in self._existing_lower:
            response = CustomMessageBox.question(
                self.theme_manager, self,
                "Replace existing import?",
                f"An import named '{name}' already exists. Replace it?",
            )
            if response != CustomMessageBox.Yes:
                return
            self._confirmed_overwrite = True

        self.accept()

    # ── Getters ──────────────────────────────────────────────────────────

    def get_file_path(self) -> str:
        return self._file_path

    def get_name(self) -> str:
        return self._name_edit.text().strip()

    def get_frequency(self) -> str:
        return self._frequency_combo.currentText().lower()

    def get_asset_class(self) -> str:
        return self._asset_class_combo.currentText()
