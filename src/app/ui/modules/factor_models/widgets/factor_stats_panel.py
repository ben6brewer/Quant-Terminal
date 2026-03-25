"""Factor Stats Panel — right sidebar showing multi-factor regression statistics."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QGridLayout,
    QScrollArea,
    QFrame,
    QPushButton,
)
from PySide6.QtCore import Qt

from app.ui.widgets.common import LazyThemeMixin, VerticalLabel
from app.services.theme_stylesheet_service import ThemeStylesheetService

if TYPE_CHECKING:
    from ..services.factor_regression_service import FactorRegressionResult


class FactorStatsPanel(LazyThemeMixin, QWidget):
    """Collapsible panel showing multi-factor regression statistics."""

    _EXPANDED_WIDTH = 320
    _COLLAPSED_WIDTH = 36

    def __init__(self, theme_manager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._theme_dirty = False
        self._expanded = True

        # Dynamic coefficient rows
        self._coeff_labels: list[dict[str, QLabel]] = []

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

        # Header row
        header_row = QHBoxLayout()
        header_row.setContentsMargins(4, 6, 4, 2)
        header_row.setSpacing(4)

        self._toggle_btn = QPushButton("\u25C0")
        self._toggle_btn.setObjectName("collapse_btn")
        self._toggle_btn.setFixedSize(24, 24)
        self._toggle_btn.setCursor(Qt.PointingHandCursor)
        self._toggle_btn.clicked.connect(self._toggle)
        header_row.addWidget(self._toggle_btn)

        self._header = QLabel("Factor Model Statistics")
        self._header.setObjectName("panel_header")
        self._header.setAlignment(Qt.AlignCenter)
        header_row.addWidget(self._header, 1)

        outer.addLayout(header_row)

        # Scroll area
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setFrameShape(QFrame.NoFrame)
        outer.addWidget(self._scroll)

        self._content = QWidget()
        self._scroll.setWidget(self._content)

        self._layout = QVBoxLayout(self._content)
        self._layout.setContentsMargins(12, 8, 12, 12)
        self._layout.setSpacing(8)

        # Coefficient section (built dynamically)
        coeff_label = QLabel("Coefficients")
        coeff_label.setObjectName("section_header")
        self._layout.addWidget(coeff_label)

        self._coeff_grid = QGridLayout()
        self._coeff_grid.setSpacing(4)
        self._layout.addLayout(self._coeff_grid)

        self._layout.addSpacing(12)

        # Goodness of Fit
        gof_label = QLabel("Goodness of Fit")
        gof_label.setObjectName("section_header")
        self._layout.addWidget(gof_label)

        self._gof_grid = QGridLayout()
        self._gof_grid.setSpacing(4)

        gof_items = [
            ("R\u00b2", "_r2_value"),
            ("Adj R\u00b2", "_adj_r2_value"),
            ("F-statistic", "_f_stat_value"),
            ("Prob(F-stat)", "_f_p_value"),
        ]

        for row, (name, attr) in enumerate(gof_items):
            name_lbl = QLabel(name)
            name_lbl.setObjectName("stat_name")
            self._gof_grid.addWidget(name_lbl, row, 0)

            val_lbl = QLabel("--")
            val_lbl.setAlignment(Qt.AlignRight)
            val_lbl.setObjectName("stat_value")
            self._gof_grid.addWidget(val_lbl, row, 1)
            setattr(self, attr, val_lbl)

        self._layout.addLayout(self._gof_grid)
        self._layout.addSpacing(12)

        # Diagnostics
        diag_label = QLabel("Diagnostics")
        diag_label.setObjectName("section_header")
        self._layout.addWidget(diag_label)

        self._diag_grid = QGridLayout()
        self._diag_grid.setSpacing(4)

        diag_items = [
            ("Durbin-Watson", "_dw_value"),
            ("Residual Std", "_resid_std_value"),
            ("N observations", "_n_obs_value"),
            ("Frequency", "_freq_value"),
        ]

        for row, (name, attr) in enumerate(diag_items):
            name_lbl = QLabel(name)
            name_lbl.setObjectName("stat_name")
            self._diag_grid.addWidget(name_lbl, row, 0)

            val_lbl = QLabel("--")
            val_lbl.setAlignment(Qt.AlignRight)
            val_lbl.setObjectName("stat_value")
            self._diag_grid.addWidget(val_lbl, row, 1)
            setattr(self, attr, val_lbl)

        self._layout.addLayout(self._diag_grid)
        self._layout.addStretch(1)

        # Placeholder
        self._placeholder = QLabel("")
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._placeholder.setObjectName("placeholder")
        self._placeholder.setWordWrap(True)
        self._placeholder.hide()
        self._layout.addWidget(self._placeholder)

        # Collapsed label
        self._collapsed_label = VerticalLabel("Statistics")
        self._collapsed_label.setObjectName("collapsed_label")
        self._collapsed_label.setAlignment(Qt.AlignCenter)
        self._collapsed_label.hide()
        outer.addWidget(self._collapsed_label, 1)

    def _toggle(self):
        self._expanded = not self._expanded
        self._scroll.setVisible(self._expanded)
        self._header.setVisible(self._expanded)
        self._collapsed_label.setVisible(not self._expanded)
        self._toggle_btn.setText("\u25C0" if self._expanded else "\u25B6")
        self.setFixedWidth(
            self._EXPANDED_WIDTH if self._expanded else self._COLLAPSED_WIDTH
        )

    # ── Build dynamic coefficient grid ──────────────────────────────────────

    def _rebuild_coeff_grid(self, factor_names: list[str]):
        """Rebuild the coefficient grid for the given factor names."""
        # Clear existing
        while self._coeff_grid.count():
            item = self._coeff_grid.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._coeff_labels.clear()

        # Column headers
        for col, text in enumerate(["", "Coeff", "Std Err", "T-stat", "P-value"]):
            lbl = QLabel(text)
            lbl.setObjectName("col_header")
            lbl.setAlignment(Qt.AlignRight if col > 0 else Qt.AlignLeft)
            self._coeff_grid.addWidget(lbl, 0, col)

        # Rows: Alpha (annualized), then each factor
        row_names = ["Alpha (ann.)"] + factor_names
        for row_idx, name in enumerate(row_names, start=1):
            row_labels = {}

            name_lbl = QLabel(name)
            name_lbl.setObjectName("row_label")
            self._coeff_grid.addWidget(name_lbl, row_idx, 0)
            row_labels["name"] = name_lbl

            for col, attr_key in enumerate(["coeff", "se", "t", "p"], start=1):
                lbl = QLabel("--")
                lbl.setAlignment(Qt.AlignRight)
                if attr_key == "p":
                    lbl.setObjectName("p_value")
                self._coeff_grid.addWidget(lbl, row_idx, col)
                row_labels[attr_key] = lbl

            self._coeff_labels.append(row_labels)

    # ── Public Methods ──────────────────────────────────────────────────────

    def update_stats(self, result: "FactorRegressionResult") -> None:
        """Populate all statistics from a factor regression result."""
        self._placeholder.hide()
        self._content.show()

        # Rebuild grid for this model's factors
        self._rebuild_coeff_grid(result.factor_names)

        # Alpha row (index 0)
        alpha_row = self._coeff_labels[0]
        alpha_row["coeff"].setText(f"{result.alpha_annualized:.6f}")
        alpha_row["se"].setText(f"{result.std_errors.get('Alpha', 0) * result.annualization_factor:.4f}")
        alpha_row["t"].setText(f"{result.t_stats.get('Alpha', 0):.2f}")
        self._set_p_value(alpha_row["p"], result.p_values.get("Alpha", 1.0))

        # Factor rows
        for i, f in enumerate(result.factor_names):
            row = self._coeff_labels[i + 1]
            row["coeff"].setText(f"{result.betas.get(f, 0):.4f}")
            row["se"].setText(f"{result.std_errors.get(f, 0):.4f}")
            row["t"].setText(f"{result.t_stats.get(f, 0):.2f}")
            self._set_p_value(row["p"], result.p_values.get(f, 1.0))

        # Goodness of fit
        self._r2_value.setText(f"{result.r_squared:.4f}")
        self._adj_r2_value.setText(f"{result.adj_r_squared:.4f}")
        self._f_stat_value.setText(f"{result.f_statistic:.2f}")
        self._set_p_value(self._f_p_value, result.f_p_value)

        # Diagnostics
        self._dw_value.setText(f"{result.durbin_watson:.3f}")
        self._resid_std_value.setText(f"{result.residual_std_error:.6f}")
        self._n_obs_value.setText(str(result.n_observations))
        freq_display = result.frequency.capitalize()
        self._freq_value.setText(f"{freq_display} (x{result.annualization_factor})")

    def clear_stats(self):
        """Reset all labels to placeholder dashes."""
        for row in self._coeff_labels:
            for key in ("coeff", "se", "t", "p"):
                row[key].setText("--")
                row[key].setStyleSheet("")

        for lbl in [
            self._r2_value, self._adj_r2_value, self._f_stat_value, self._f_p_value,
            self._dw_value, self._resid_std_value, self._n_obs_value, self._freq_value,
        ]:
            lbl.setText("--")
            lbl.setStyleSheet("")

    def show_placeholder(self, msg: str):
        self.clear_stats()
        self._placeholder.setText(msg)
        self._placeholder.show()

    def _set_p_value(self, label: QLabel, p: float):
        label.setText(f"{p:.4f}")

        if p < 0.01:
            label.setStyleSheet("color: #00cc66; background: transparent;")
        elif p < 0.05:
            label.setStyleSheet("color: #cccc00; background: transparent;")
        else:
            c = ThemeStylesheetService.get_colors(self.theme_manager.current_theme)
            label.setStyleSheet(f"color: {c['text_muted']}; background: transparent;")

    def _apply_theme(self):
        c = ThemeStylesheetService.get_colors(self.theme_manager.current_theme)

        self.setStyleSheet(f"""
            QWidget {{
                background-color: {c['bg']};
                color: {c['text']};
            }}
            QScrollArea {{
                background-color: {c['bg']};
                border: none;
            }}
            QLabel#panel_header {{
                font-size: 15px;
                font-weight: bold;
                color: {c['accent']};
                background: transparent;
                padding: 4px;
            }}
            QLabel#section_header {{
                font-size: 13px;
                font-weight: bold;
                color: {c['accent']};
                background: transparent;
                padding: 2px 0px;
                border-bottom: 1px solid {c['border']};
            }}
            QLabel#col_header {{
                font-size: 11px;
                font-weight: bold;
                color: {c['text_muted']};
                background: transparent;
            }}
            QLabel#row_label {{
                font-size: 12px;
                font-weight: 600;
                color: {c['text']};
                background: transparent;
            }}
            QLabel#stat_name {{
                font-size: 12px;
                color: {c['text_muted']};
                background: transparent;
            }}
            QLabel#stat_value {{
                font-size: 12px;
                font-weight: 500;
                color: {c['text']};
                background: transparent;
            }}
            QLabel#placeholder {{
                font-size: 13px;
                color: {c['text_muted']};
                background: transparent;
                padding: 20px;
            }}
            QLabel {{
                background: transparent;
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
