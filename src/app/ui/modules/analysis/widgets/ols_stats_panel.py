"""OLS Stats Panel - Right sidebar showing regression statistics."""

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
    from ..services.ols_regression_service import OLSRegressionResult


class OLSStatsPanel(LazyThemeMixin, QWidget):
    """Collapsible panel showing OLS regression statistics."""

    _EXPANDED_WIDTH = 320
    _COLLAPSED_WIDTH = 36

    def __init__(self, theme_manager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._theme_dirty = False
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

        # Header row (toggle button + title) — outside scroll area
        header_row = QHBoxLayout()
        header_row.setContentsMargins(4, 6, 4, 2)
        header_row.setSpacing(4)

        self._toggle_btn = QPushButton("\u25C0")
        self._toggle_btn.setObjectName("collapse_btn")
        self._toggle_btn.setFixedSize(24, 24)
        self._toggle_btn.setCursor(Qt.PointingHandCursor)
        self._toggle_btn.clicked.connect(self._toggle)
        header_row.addWidget(self._toggle_btn)

        self._header = QLabel("Regression Statistics")
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

        layout = QVBoxLayout(self._content)
        layout.setContentsMargins(12, 8, 12, 12)
        layout.setSpacing(8)

        # Collapsed vertical label (hidden by default)
        self._collapsed_label = VerticalLabel("Statistics")
        self._collapsed_label.setObjectName("collapsed_label")
        self._collapsed_label.setAlignment(Qt.AlignCenter)
        self._collapsed_label.hide()
        outer.addWidget(self._collapsed_label, 1)

        # ── Coefficients Section ──────────────────────────────────────
        coeff_label = QLabel("Annualized Coefficients")
        coeff_label.setObjectName("section_header")
        layout.addWidget(coeff_label)

        self._coeff_grid = QGridLayout()
        self._coeff_grid.setSpacing(4)

        # Column headers
        for col, text in enumerate(["", "Coeff", "Std Err", "T-stat", "P-value"]):
            lbl = QLabel(text)
            lbl.setObjectName("col_header")
            lbl.setAlignment(Qt.AlignRight if col > 0 else Qt.AlignLeft)
            self._coeff_grid.addWidget(lbl, 0, col)

        # Alpha row
        self._alpha_name = QLabel("Alpha")
        self._alpha_name.setObjectName("row_label")
        self._coeff_grid.addWidget(self._alpha_name, 1, 0)
        self._alpha_coeff = QLabel("--")
        self._alpha_coeff.setAlignment(Qt.AlignRight)
        self._coeff_grid.addWidget(self._alpha_coeff, 1, 1)
        self._alpha_se = QLabel("--")
        self._alpha_se.setAlignment(Qt.AlignRight)
        self._coeff_grid.addWidget(self._alpha_se, 1, 2)
        self._alpha_t = QLabel("--")
        self._alpha_t.setAlignment(Qt.AlignRight)
        self._coeff_grid.addWidget(self._alpha_t, 1, 3)
        self._alpha_p = QLabel("--")
        self._alpha_p.setAlignment(Qt.AlignRight)
        self._alpha_p.setObjectName("p_value")
        self._coeff_grid.addWidget(self._alpha_p, 1, 4)

        # Beta row
        self._beta_name = QLabel("Beta")
        self._beta_name.setObjectName("row_label")
        self._coeff_grid.addWidget(self._beta_name, 2, 0)
        self._beta_coeff = QLabel("--")
        self._beta_coeff.setAlignment(Qt.AlignRight)
        self._coeff_grid.addWidget(self._beta_coeff, 2, 1)
        self._beta_se = QLabel("--")
        self._beta_se.setAlignment(Qt.AlignRight)
        self._coeff_grid.addWidget(self._beta_se, 2, 2)
        self._beta_t = QLabel("--")
        self._beta_t.setAlignment(Qt.AlignRight)
        self._coeff_grid.addWidget(self._beta_t, 2, 3)
        self._beta_p = QLabel("--")
        self._beta_p.setAlignment(Qt.AlignRight)
        self._beta_p.setObjectName("p_value")
        self._coeff_grid.addWidget(self._beta_p, 2, 4)

        layout.addLayout(self._coeff_grid)

        # Confidence intervals
        layout.addSpacing(4)
        self._alpha_ci_label = QLabel("95% CI (Alpha): --")
        self._alpha_ci_label.setObjectName("ci_label")
        layout.addWidget(self._alpha_ci_label)

        self._beta_ci_label = QLabel("95% CI (Beta):  --")
        self._beta_ci_label.setObjectName("ci_label")
        layout.addWidget(self._beta_ci_label)

        layout.addSpacing(12)

        # ── Goodness of Fit Section ───────────────────────────────────
        gof_label = QLabel("Goodness of Fit")
        gof_label.setObjectName("section_header")
        layout.addWidget(gof_label)

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

        layout.addLayout(self._gof_grid)

        layout.addSpacing(12)

        # ── Diagnostics Section ───────────────────────────────────────
        diag_label = QLabel("Diagnostics")
        diag_label.setObjectName("section_header")
        layout.addWidget(diag_label)

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

        layout.addLayout(self._diag_grid)
        layout.addStretch(1)

        # Placeholder
        self._placeholder = QLabel("")
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._placeholder.setObjectName("placeholder")
        self._placeholder.setWordWrap(True)
        self._placeholder.hide()
        layout.addWidget(self._placeholder)

    def _toggle(self):
        """Toggle between expanded and collapsed states."""
        self._expanded = not self._expanded
        self._scroll.setVisible(self._expanded)
        self._header.setVisible(self._expanded)
        self._collapsed_label.setVisible(not self._expanded)
        self._toggle_btn.setText("\u25C0" if self._expanded else "\u25B6")
        self.setFixedWidth(
            self._EXPANDED_WIDTH if self._expanded else self._COLLAPSED_WIDTH
        )

    def update_stats(self, result: "OLSRegressionResult") -> None:
        """Populate all statistics from an OLS result."""
        self._placeholder.hide()
        self._content.show()

        # Coefficients (annualized alpha)
        self._alpha_coeff.setText(f"{result.annualized_alpha:.6f}")
        self._alpha_se.setText(f"{result.annualized_alpha_std_error:.4f}")
        self._alpha_t.setText(f"{result.alpha_t_stat:.2f}")
        self._set_p_value(self._alpha_p, result.alpha_p_value)

        self._beta_coeff.setText(f"{result.beta:.4f}")
        self._beta_se.setText(f"{result.beta_std_error:.4f}")
        self._beta_t.setText(f"{result.beta_t_stat:.2f}")
        self._set_p_value(self._beta_p, result.beta_p_value)

        # Confidence intervals (annualized alpha CI)
        self._alpha_ci_label.setText(
            f"95% CI (Alpha): [{result.annualized_alpha_ci_lower:.6f}, {result.annualized_alpha_ci_upper:.6f}]"
        )
        self._beta_ci_label.setText(
            f"95% CI (Beta):  [{result.beta_ci_lower:.4f}, {result.beta_ci_upper:.4f}]"
        )

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
        for lbl in [
            self._alpha_coeff, self._alpha_se, self._alpha_t, self._alpha_p,
            self._beta_coeff, self._beta_se, self._beta_t, self._beta_p,
            self._r2_value, self._adj_r2_value, self._f_stat_value, self._f_p_value,
            self._dw_value, self._resid_std_value, self._n_obs_value, self._freq_value,
        ]:
            lbl.setText("--")
            lbl.setStyleSheet("")

        self._alpha_ci_label.setText("95% CI (Alpha): --")
        self._beta_ci_label.setText("95% CI (Beta):  --")

    def show_placeholder(self, msg: str):
        """Show a placeholder message instead of stats."""
        self.clear_stats()
        self._placeholder.setText(msg)
        self._placeholder.show()

    def _set_p_value(self, label: QLabel, p: float):
        """Set p-value text with color coding."""
        label.setText(f"{p:.4f}")
        c = ThemeStylesheetService.get_colors(self.theme_manager.current_theme)

        if p < 0.01:
            label.setStyleSheet(f"color: #00cc66; background: transparent;")
        elif p < 0.05:
            label.setStyleSheet(f"color: #cccc00; background: transparent;")
        else:
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
            QLabel#ci_label {{
                font-size: 11px;
                color: {c['text_muted']};
                background: transparent;
                font-family: monospace;
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
