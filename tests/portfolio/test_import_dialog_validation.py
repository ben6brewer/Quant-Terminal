"""Characterization (UI, ``--full``): ImportDialog input validation.

The dialog is driven through its real widgets; modal message boxes are
intercepted by the ``nonblocking_dialogs`` fixture.  Nothing is persisted.
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QDialog, QLabel, QLineEdit, QPushButton

from app.services.custom_data_service import CustomImportMeta
from app.ui.modules.import_data.import_dialog import ImportDialog
from app.ui.widgets.common import NoScrollComboBox

from ._helpers import CUSTOM_NAME, PREFIX

pytestmark = pytest.mark.ui


@pytest.fixture
def messages(nonblocking_dialogs):
    """Record (labels...) of every CustomMessageBox shown; answer questions with ``answer``."""
    shown = []
    state = {"answer": None}

    def on_exec(dialog):
        shown.append([lbl.text() for lbl in dialog.findChildren(QLabel) if lbl.text()])
        if state["answer"]:
            for btn in dialog.findChildren(QPushButton):
                if btn.text() == state["answer"]:
                    btn.click()
                    return 1
        return 0

    nonblocking_dialogs.on_exec = on_exec
    return {"shown": shown, "state": state, "recorder": nonblocking_dialogs}


def _button(dialog, text):
    return next(b for b in dialog.findChildren(QPushButton) if b.text() == text)


def _name_edit(dialog):
    return next(e for e in dialog.findChildren(QLineEdit) if e.placeholderText() == "e.g. MyCustomFund")


def _combos(dialog):
    return dialog.findChildren(NoScrollComboBox)


def _pick_file(dialog, messages, path):
    messages["recorder"].file_result = str(path)
    _button(dialog, "Browse…").click()


@pytest.fixture
def csv_file(tmp_path):
    path = tmp_path / "_QT_TEST_upload.csv"
    path.write_text("Date,Value\n2024-01-02,0.01\n2024-01-03,0.02\n", encoding="utf-8")
    return path


@pytest.fixture
def make_dialog(qtbot, theme_manager):
    """Build an ImportDialog whose lifetime is managed by qtbot (closed + deleted at teardown)."""
    def make(existing_names=(), reimport_target=None):
        dlg = ImportDialog(theme_manager, existing_names=list(existing_names), reimport_target=reimport_target)
        qtbot.addWidget(dlg)
        return dlg
    return make


def _submit(dialog):
    _button(dialog, "Import").click()
    return dialog.result() == QDialog.Accepted


class TestImportDialog:
    def test_defaults_and_getters(self, make_dialog, messages, csv_file):
        dlg = make_dialog()
        freq, asset = _combos(dlg)
        assert [freq.itemText(i) for i in range(freq.count())] == ["Daily", "Weekly", "Monthly", "Yearly"]
        assert [asset.itemText(i) for i in range(asset.count())] == [
            "Equity", "Fixed Income", "Real Estate", "Commodities", "Alternatives", "Cash", "Other"]

        _pick_file(dlg, messages, csv_file)
        _name_edit(dlg).setText(f"  {CUSTOM_NAME}  ")
        freq.setCurrentText("Monthly")
        asset.setCurrentText("Real Estate")
        assert _submit(dlg) is True
        assert messages["shown"] == []
        assert (dlg.get_file_path(), dlg.get_name(), dlg.get_frequency(), dlg.get_asset_class()) == (
            str(csv_file), CUSTOM_NAME, "monthly", "Real Estate")

    @pytest.mark.parametrize("name, fragment", [
        ("", "Enter a ticker name."),
        ("   ", "Enter a ticker name."),
        (f"{PREFIX}[x]", "Ticker name cannot contain '[', ']', '/' or '\\'."),
        (f"{PREFIX}a/b", "Ticker name cannot contain"),
        (f"{PREFIX}a\\b", "Ticker name cannot contain"),
        ("con", "'con' is a reserved name on Windows. Pick a different name."),
        ("LPT9", "is a reserved name on Windows"),
    ])
    def test_invalid_names_are_rejected(self, make_dialog, messages, csv_file, name, fragment):
        dlg = make_dialog()
        _pick_file(dlg, messages, csv_file)
        _name_edit(dlg).setText(name)
        assert _submit(dlg) is False
        assert len(messages["shown"]) == 1
        assert any(fragment in text for text in messages["shown"][0])

    def test_file_checks(self, make_dialog, messages, tmp_path):
        dlg = make_dialog()
        _name_edit(dlg).setText(CUSTOM_NAME)
        assert _submit(dlg) is False  # no file chosen
        assert any("Please choose a CSV or XLSX file to import." in t for t in messages["shown"][-1])

        txt = tmp_path / "_QT_TEST_returns.txt"
        txt.write_text("x", encoding="utf-8")
        _pick_file(dlg, messages, txt)
        assert _submit(dlg) is False
        assert any("File extension '.txt' is not supported" in t for t in messages["shown"][-1])

        _pick_file(dlg, messages, tmp_path / "_QT_TEST_gone.csv")  # chosen, then missing on disk
        assert _submit(dlg) is False
        assert any("Please choose a CSV or XLSX file" in t for t in messages["shown"][-1])

    def test_existing_name_asks_to_replace(self, make_dialog, messages, csv_file):
        dlg = make_dialog([CUSTOM_NAME])
        _pick_file(dlg, messages, csv_file)
        _name_edit(dlg).setText(CUSTOM_NAME.lower())  # conflict check is case-insensitive
        assert _submit(dlg) is False  # question declined (default)
        assert any(f"An import named '{CUSTOM_NAME.lower()}' already exists. Replace it?" in t
                   for t in messages["shown"][-1])

        messages["state"]["answer"] = "Yes"
        assert _submit(dlg) is True
        assert dlg.get_name() == CUSTOM_NAME.lower()

    def test_reimport_locks_name_and_preselects(self, make_dialog, messages, csv_file):
        meta = CustomImportMeta(name=CUSTOM_NAME, asset_class="Commodities", frequency="weekly",
                                start_date="2024-01-01", end_date="2024-06-28", row_count=10,
                                imported_at="2024-07-01T00:00:00", source_filename="_QT_TEST_old.csv")
        dlg = make_dialog([CUSTOM_NAME], reimport_target=meta)
        edit = _name_edit(dlg)
        assert edit.text() == CUSTOM_NAME and not edit.isEnabled()
        freq, asset = _combos(dlg)
        assert (freq.currentText(), asset.currentText()) == ("Weekly", "Commodities")

        _pick_file(dlg, messages, csv_file)
        assert _submit(dlg) is True
        assert messages["shown"] == []  # no "replace existing?" question on reimport
        assert (dlg.get_name(), dlg.get_frequency(), dlg.get_asset_class()) == (
            CUSTOM_NAME, "weekly", "Commodities")
