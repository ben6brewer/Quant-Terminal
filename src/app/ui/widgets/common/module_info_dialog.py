"""Module Info Dialog — displays module description, calculation, and data sources."""

from PySide6.QtWidgets import QVBoxLayout, QLabel, QPushButton, QScrollArea, QWidget
from PySide6.QtCore import Qt

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common.themed_dialog import ThemedDialog


class ModuleInfoDialog(ThemedDialog):
    """Themed popup showing what a module displays, how it's calculated, and data sources."""

    def __init__(self, theme_manager: ThemeManager, info: dict, parent=None):
        self._info = info
        super().__init__(
            theme_manager,
            title=info.get("title", "Module Info"),
            parent=parent,
            min_width=520,
        )

    def _setup_content(self, layout: QVBoxLayout):
        info = self._info

        # Scroll area for content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        inner = QVBoxLayout(container)
        inner.setContentsMargins(0, 0, 0, 0)
        inner.setSpacing(12)

        # Description section
        if info.get("description"):
            header = QLabel("Description")
            header.setObjectName("sectionHeader")
            inner.addWidget(header)

            body = QLabel(info["description"])
            body.setObjectName("infoBody")
            body.setWordWrap(True)
            inner.addWidget(body)

        # Calculation section
        if info.get("calculation"):
            header = QLabel("Calculation")
            header.setObjectName("sectionHeader")
            inner.addWidget(header)

            body = QLabel(info["calculation"])
            body.setObjectName("infoBody")
            body.setWordWrap(True)
            inner.addWidget(body)

        # Data Sources section
        sources = info.get("data_sources", [])
        if sources:
            header = QLabel("Data Sources")
            header.setObjectName("sectionHeader")
            inner.addWidget(header)

            source_label = info.get("source", "")
            html = ""
            if source_label:
                html += f"<p style='margin:0 0 6px 0;'><b>{source_label}</b></p>"
            html += "<ul style='margin:0; padding-left:18px;'>"
            for src in sources:
                sid = src.get("id", "")
                name = src.get("name", "")
                freq = src.get("frequency", "")
                freq_str = f" &mdash; {freq}" if freq else ""
                html += f"<li><b>{sid}</b> &mdash; {name}{freq_str}</li>"
            html += "</ul>"

            body = QLabel(html)
            body.setObjectName("sourcesBody")
            body.setTextFormat(Qt.RichText)
            body.setWordWrap(True)
            inner.addWidget(body)

        inner.addStretch(1)
        scroll.setWidget(container)
        layout.addWidget(scroll, stretch=1)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.setObjectName("defaultButton")
        close_btn.setFixedWidth(100)
        close_btn.setFixedHeight(36)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignRight)
