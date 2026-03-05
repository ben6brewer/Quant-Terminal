"""Rate Probability Toolbar - Home button, info bar, and view tabs."""

from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QButtonGroup
from PySide6.QtCore import Signal, Qt

from app.ui.modules.module_toolbar import ModuleToolbar


class RateProbabilityToolbar(ModuleToolbar):
    """Toolbar with home button, view tabs, info bar, and settings."""

    view_changed = Signal(int)  # 0=FedWatch, 1=Rate Path, 2=Evolution

    def setup_center(self, layout: QHBoxLayout):
        # View tab buttons
        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)

        view_names = ["FedWatch", "Rate Path", "Evolution"]
        self._view_buttons = []
        for i, name in enumerate(view_names):
            btn = QPushButton(name)
            btn.setObjectName("viewTab")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setMinimumWidth(90)
            btn.setFixedHeight(40)
            if i == 0:
                btn.setChecked(True)
            btn.clicked.connect(lambda checked, idx=i: self.view_changed.emit(idx))
            layout.addWidget(btn)
            self.button_group.addButton(btn)
            self._view_buttons.append(btn)

        # Separator + info labels
        layout.addWidget(self._sep())

        self.rate_label = QLabel("Rate: --")
        self.rate_label.setObjectName("info_label")
        layout.addWidget(self.rate_label)

        layout.addWidget(self._sep())

        self.meeting_label = QLabel("Next FOMC: --")
        self.meeting_label.setObjectName("info_label")
        layout.addWidget(self.meeting_label)

        layout.addWidget(self._sep())

        self.updated_label = QLabel("")
        self.updated_label.setObjectName("info_label_muted")
        layout.addWidget(self.updated_label)

    def set_active_view(self, index: int):
        """Set active view programmatically."""
        if 0 <= index < len(self._view_buttons):
            self._view_buttons[index].setChecked(True)

    def update_info(self, target_rate=None, next_meeting=None, days_until=None):
        """Update info bar labels."""
        if target_rate:
            lower, upper = target_rate
            self.rate_label.setText(f"Rate: {lower:.2f}-{upper:.2f}%")

        if next_meeting:
            meeting_str = next_meeting.strftime("%b %d")
            if days_until is not None:
                self.meeting_label.setText(f"Next FOMC: {meeting_str} (in {days_until}d)")
            else:
                self.meeting_label.setText(f"Next FOMC: {meeting_str}")

        self._update_timestamp()
