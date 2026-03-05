"""Generic checkbox settings dialog for FRED modules."""

from PySide6.QtWidgets import QCheckBox, QDialogButtonBox

from app.ui.widgets.common.themed_dialog import ThemedDialog


class CheckboxSettingsDialog(ThemedDialog):
    """
    Generic settings dialog with a list of checkboxes.

    Replaces ~10 identical inline dialog class definitions across FRED modules.

    Usage:
        dialog = CheckboxSettingsDialog(
            theme_manager,
            title="PCE Settings",
            options=[("show_gridlines", "Show gridlines"), ("show_legend", "Show legend")],
            current_settings=settings_manager.get_all_settings(),
            parent=self,
        )
        if dialog.exec() == QDialog.Accepted:
            new_settings = dialog.get_settings()
    """

    def __init__(self, theme_manager, title, options, current_settings, parent=None, min_width=340):
        self._current = current_settings
        self._options = options
        self._checks = {}
        super().__init__(theme_manager, title, parent, min_width=min_width)

    def _setup_content(self, layout):
        for key, label in self._options:
            cb = QCheckBox(label)
            cb.setChecked(self._current.get(key, True))
            self._checks[key] = cb
            layout.addWidget(cb)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)

    def get_settings(self):
        return {k: cb.isChecked() for k, cb in self._checks.items()}
