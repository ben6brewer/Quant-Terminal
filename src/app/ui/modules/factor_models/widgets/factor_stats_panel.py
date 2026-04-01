"""Factor Stats Panel — full-width main view showing multi-factor regression statistics."""

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
)
from PySide6.QtCore import Qt

from app.ui.widgets.common import LazyThemeMixin
from app.services.theme_stylesheet_service import ThemeStylesheetService

if TYPE_CHECKING:
    from ..services.factor_regression_service import FactorRegressionResult

# Factor colors (shared with chart)
FACTOR_COLORS: dict[str, str] = {
    "Mkt-RF": "#4FC3F7", "SMB": "#66BB6A", "HML": "#EF5350",
    "RMW": "#26C6DA", "CMA": "#FFA726", "UMD": "#AB47BC",
    "R_MKT": "#4FC3F7", "R_ME": "#66BB6A", "R_IA": "#FFA726",
    "R_ROE": "#26C6DA", "R_EG": "#EC407A",
    "BAB": "#FF7043", "QMJ": "#7E57C2", "HML_DEVIL": "#D4E157",
    "Alpha": "#FFD54F", "Residual": "#9E9E9E",
}

# Column definitions: (key, header_text)  — "ci" header is dynamic
_COL_DEFS = [
    ("coeff", "Coefficient"),
    ("se", "Std Error"),
    ("t", "T-Stat"),
    ("p", "P-Value"),
    ("ci", "{ci_pct}% CI"),
]

_COL_SETTING_MAP = {
    "coeff": "show_col_coefficient",
    "se": "show_col_std_error",
    "t": "show_col_t_stat",
    "p": "show_col_p_value",
    "ci": "show_col_ci",
}


class FactorStatsPanel(LazyThemeMixin, QWidget):
    """Full-width panel showing comprehensive factor regression statistics."""

    def __init__(self, theme_manager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._theme_dirty = False

        self._coeff_labels: list[dict[str, QLabel]] = []
        self._last_result: "FactorRegressionResult | None" = None
        self._settings: dict = {}

        self._setup_ui()
        self._apply_theme()
        self.theme_manager.theme_changed.connect(self._on_theme_changed_lazy)

    def showEvent(self, event):
        super().showEvent(event)
        self._check_theme_dirty()

    # ── UI Setup ───────────────────────────────────────────────────────────

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Scroll area wrapping all content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)
        outer.addWidget(scroll)

        self._content = QWidget()
        scroll.setWidget(self._content)

        self._layout = QVBoxLayout(self._content)
        self._layout.setContentsMargins(24, 20, 24, 24)
        self._layout.setSpacing(0)

        # ── Model Info Header ──────────────────────────────────────────
        self._model_header = QLabel("")
        self._model_header.setObjectName("modelHeader")
        self._model_header.setWordWrap(True)
        self._layout.addWidget(self._model_header)

        self._model_desc = QLabel("")
        self._model_desc.setObjectName("modelDesc")
        self._model_desc.setWordWrap(True)
        self._layout.addWidget(self._model_desc)
        self._layout.addSpacing(20)

        # ── Coefficients Section ───────────────────────────────────────
        self._add_section_header("Coefficients")
        self._layout.addSpacing(8)

        self._coeff_grid = QGridLayout()
        self._coeff_grid.setSpacing(0)
        self._coeff_grid.setContentsMargins(0, 0, 0, 0)
        self._layout.addLayout(self._coeff_grid)
        self._layout.addSpacing(24)

        # ── Two-column: Goodness of Fit | Diagnostics ──────────────────
        self._cards_wrapper = QWidget()
        cards_row = QHBoxLayout(self._cards_wrapper)
        cards_row.setContentsMargins(0, 0, 0, 0)
        cards_row.setSpacing(20)

        # Goodness of Fit card
        self._gof_card = self._make_card()
        gof_layout = self._gof_card.layout()
        self._add_card_header(gof_layout, "Goodness of Fit")

        self._gof_grid = QGridLayout()
        self._gof_grid.setSpacing(6)
        self._gof_grid.setColumnStretch(0, 1)
        self._gof_grid.setColumnStretch(1, 0)

        gof_items = [
            ("R\u00b2", "_r2_value"),
            ("Adjusted R\u00b2", "_adj_r2_value"),
            ("F-statistic", "_f_stat_value"),
            ("Prob (F-stat)", "_f_p_value"),
        ]
        for row, (name, attr) in enumerate(gof_items):
            name_lbl = QLabel(name)
            name_lbl.setObjectName("cardStatName")
            self._gof_grid.addWidget(name_lbl, row, 0)
            val_lbl = QLabel("--")
            val_lbl.setAlignment(Qt.AlignRight)
            val_lbl.setObjectName("cardStatValue")
            self._gof_grid.addWidget(val_lbl, row, 1)
            setattr(self, attr, val_lbl)

        gof_layout.addLayout(self._gof_grid)
        gof_layout.addStretch(1)
        cards_row.addWidget(self._gof_card, 1)

        # Diagnostics card
        self._diag_card = self._make_card()
        diag_layout = self._diag_card.layout()
        self._add_card_header(diag_layout, "Diagnostics")

        self._diag_grid = QGridLayout()
        self._diag_grid.setSpacing(6)
        self._diag_grid.setColumnStretch(0, 1)
        self._diag_grid.setColumnStretch(1, 0)

        diag_items = [
            ("Durbin-Watson", "_dw_value"),
            ("Residual Std Error", "_resid_std_value"),
            ("N Observations", "_n_obs_value"),
            ("Frequency", "_freq_value"),
        ]
        for row, (name, attr) in enumerate(diag_items):
            name_lbl = QLabel(name)
            name_lbl.setObjectName("cardStatName")
            self._diag_grid.addWidget(name_lbl, row, 0)
            val_lbl = QLabel("--")
            val_lbl.setAlignment(Qt.AlignRight)
            val_lbl.setObjectName("cardStatValue")
            self._diag_grid.addWidget(val_lbl, row, 1)
            setattr(self, attr, val_lbl)

        diag_layout.addLayout(self._diag_grid)
        diag_layout.addStretch(1)
        cards_row.addWidget(self._diag_card, 1)

        self._layout.addWidget(self._cards_wrapper)

        self._layout.addStretch(1)

        # ── Placeholder (shown before first run) ──────────────────────
        self._placeholder = QLabel("Select a ticker or portfolio and click Run to analyze factor exposures")
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._placeholder.setObjectName("placeholder")
        self._placeholder.setWordWrap(True)
        outer.addWidget(self._placeholder)
        self._placeholder.show()
        self._content.hide()

    def _add_section_header(self, text: str):
        lbl = QLabel(text)
        lbl.setObjectName("sectionHeader")
        self._layout.addWidget(lbl)

    def _add_card_header(self, layout: QVBoxLayout, text: str):
        lbl = QLabel(text)
        lbl.setObjectName("cardHeader")
        layout.addWidget(lbl)
        layout.addSpacing(8)

    def _make_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("statsCard")
        card.setFrameShape(QFrame.NoFrame)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(4)
        return card

    # ── Determine visible columns ──────────────────────────────────────

    def _visible_columns(self, settings: dict) -> list[tuple[str, str]]:
        """Return list of (key, header_text) for columns that should be shown."""
        ci_pct = int(round(settings.get("confidence_level", 0.95) * 100))
        cols = [("name", "")]  # always shown
        for key, header in _COL_DEFS:
            setting_key = _COL_SETTING_MAP[key]
            if settings.get(setting_key, True):
                header_text = header.format(ci_pct=ci_pct) if "{ci_pct}" in header else header
                cols.append((key, header_text))
        return cols

    # ── Build dynamic coefficient grid ─────────────────────────────────

    def _rebuild_coeff_grid(
        self,
        result: "FactorRegressionResult",
        visible_cols: list[tuple[str, str]],
        visible_factors: list[str],
    ):
        """Rebuild the coefficient grid with only visible columns and rows."""
        while self._coeff_grid.count():
            item = self._coeff_grid.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._coeff_labels.clear()

        num_cols = len(visible_cols)

        # Column headers
        for col, (key, text) in enumerate(visible_cols):
            lbl = QLabel(text)
            lbl.setObjectName("coeffHeader")
            lbl.setAlignment(Qt.AlignRight if col > 0 else Qt.AlignLeft)
            self._coeff_grid.addWidget(lbl, 0, col)

        # Separator line
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setObjectName("coeffSep")
        sep.setFixedHeight(1)
        self._coeff_grid.addWidget(sep, 1, 0, 1, num_cols)

        # Rows: Alpha (annualized), then visible factors
        row_names = ["Alpha (annualized)"] + visible_factors
        for row_idx, name in enumerate(row_names, start=2):
            row_labels: dict[str, QLabel] = {}

            for col, (key, _header) in enumerate(visible_cols):
                if key == "name":
                    color_key = "Alpha" if row_idx == 2 else name
                    color_hex = FACTOR_COLORS.get(color_key, "#888888")
                    name_lbl = QLabel(f'<span style="color:{color_hex};">\u25cf</span> &nbsp;{name}')
                    name_lbl.setObjectName("coeffRowName")
                    name_lbl.setTextFormat(Qt.RichText)
                    self._coeff_grid.addWidget(name_lbl, row_idx, col)
                    row_labels["name"] = name_lbl
                else:
                    lbl = QLabel("--")
                    lbl.setAlignment(Qt.AlignRight)
                    lbl.setObjectName("coeffValue" if key != "p" else "pValue")
                    self._coeff_grid.addWidget(lbl, row_idx, col)
                    row_labels[key] = lbl

            self._coeff_labels.append(row_labels)

        # Set column stretches
        self._coeff_grid.setColumnStretch(0, 3)
        for c in range(1, num_cols):
            self._coeff_grid.setColumnStretch(c, 2)

    # ── Public Methods ─────────────────────────────────────────────────

    def update_stats(self, result: "FactorRegressionResult", settings: dict | None = None) -> None:
        self._placeholder.hide()
        self._content.show()
        self._last_result = result
        if settings is not None:
            self._settings = settings

        s = self._settings

        # Model header
        self._model_header.setText(result.model_name)
        freq_display = result.frequency.capitalize()
        self._model_desc.setText(
            f"{freq_display} frequency  \u00b7  {result.n_observations} observations  "
            f"\u00b7  Annualization \u00d7{result.annualization_factor}"
        )

        # Determine visible columns and rows
        visible_cols = self._visible_columns(s)

        # Significance filtering
        show_only_sig = s.get("show_only_significant", False)
        sig_alpha = 1.0 - s.get("confidence_level", 0.95)
        visible_factors = []
        for f in result.factor_names:
            if show_only_sig:
                p = result.p_values.get(f, 1.0)
                if p >= sig_alpha:
                    continue
            visible_factors.append(f)

        # Rebuild coefficient grid
        self._rebuild_coeff_grid(result, visible_cols, visible_factors)

        # Map of column keys present
        col_keys = {k for k, _ in visible_cols}

        # Alpha row
        alpha_row = self._coeff_labels[0]
        if "coeff" in col_keys:
            alpha_row["coeff"].setText(f"{result.alpha_annualized:.6f}")
        if "se" in col_keys:
            alpha_se_ann = result.std_errors.get("Alpha", 0) * result.annualization_factor
            alpha_row["se"].setText(f"{alpha_se_ann:.6f}")
        if "t" in col_keys:
            alpha_row["t"].setText(f"{result.t_stats.get('Alpha', 0):.3f}")
        if "p" in col_keys:
            self._set_p_value(alpha_row["p"], result.p_values.get("Alpha", 1.0))
        if "ci" in col_keys:
            ci_lo = result.ci_lower.get("Alpha", 0) * result.annualization_factor
            ci_hi = result.ci_upper.get("Alpha", 0) * result.annualization_factor
            alpha_row["ci"].setText(f"[{ci_lo:.6f}, {ci_hi:.6f}]")

        # Factor rows
        for i, f in enumerate(visible_factors):
            row = self._coeff_labels[i + 1]
            if "coeff" in col_keys:
                row["coeff"].setText(f"{result.betas.get(f, 0):.4f}")
            if "se" in col_keys:
                row["se"].setText(f"{result.std_errors.get(f, 0):.4f}")
            if "t" in col_keys:
                row["t"].setText(f"{result.t_stats.get(f, 0):.3f}")
            if "p" in col_keys:
                self._set_p_value(row["p"], result.p_values.get(f, 1.0))
            if "ci" in col_keys:
                lo = result.ci_lower.get(f, 0)
                hi = result.ci_upper.get(f, 0)
                row["ci"].setText(f"[{lo:.4f}, {hi:.4f}]")

        # Card visibility
        self._gof_card.setVisible(s.get("show_goodness_of_fit", True))
        self._diag_card.setVisible(s.get("show_diagnostics", True))
        # Hide the whole wrapper if both cards are hidden
        self._cards_wrapper.setVisible(
            s.get("show_goodness_of_fit", True) or s.get("show_diagnostics", True)
        )

        # Goodness of fit
        self._r2_value.setText(f"{result.r_squared:.4f}")
        self._adj_r2_value.setText(f"{result.adj_r_squared:.4f}")
        self._f_stat_value.setText(f"{result.f_statistic:.2f}")
        self._set_p_value(self._f_p_value, result.f_p_value)

        # Diagnostics
        self._dw_value.setText(f"{result.durbin_watson:.4f}")
        self._resid_std_value.setText(f"{result.residual_std_error:.6f}")
        self._n_obs_value.setText(str(result.n_observations))
        self._freq_value.setText(f"{freq_display} (\u00d7{result.annualization_factor})")

    def apply_display_settings(self, settings: dict):
        """Re-apply display settings to the currently cached result."""
        self._settings = settings
        # Toggle card visibility even if no result yet
        self._gof_card.setVisible(settings.get("show_goodness_of_fit", True))
        self._diag_card.setVisible(settings.get("show_diagnostics", True))
        self._cards_wrapper.setVisible(
            settings.get("show_goodness_of_fit", True) or settings.get("show_diagnostics", True)
        )
        if self._last_result is not None:
            self.update_stats(self._last_result, settings)

    def clear_stats(self):
        for row in self._coeff_labels:
            for key in ("coeff", "se", "t", "p", "ci"):
                if key in row:
                    row[key].setText("--")
                    row[key].setStyleSheet("")

        for lbl in [
            self._r2_value, self._adj_r2_value, self._f_stat_value, self._f_p_value,
            self._dw_value, self._resid_std_value, self._n_obs_value, self._freq_value,
        ]:
            lbl.setText("--")
            lbl.setStyleSheet("")

    def show_placeholder(self, msg: str):
        self._content.hide()
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

    # ── Theme ──────────────────────────────────────────────────────────

    def _apply_theme(self):
        c = ThemeStylesheetService.get_colors(self.theme_manager.current_theme)
        border_subtle = c.get("border", "#333333")
        card_bg = c.get("bg_header", "#1a1a2e")

        self.setStyleSheet(f"""
            QWidget {{
                background-color: {c['bg']};
                color: {c['text']};
            }}
            QScrollArea {{
                background-color: {c['bg']};
                border: none;
            }}

            /* Model header */
            QLabel#modelHeader {{
                font-size: 22px;
                font-weight: bold;
                color: {c['text']};
                background: transparent;
                padding: 0px;
            }}
            QLabel#modelDesc {{
                font-size: 13px;
                color: {c['text_muted']};
                background: transparent;
                padding: 2px 0px 0px 0px;
            }}

            /* Section headers */
            QLabel#sectionHeader {{
                font-size: 15px;
                font-weight: bold;
                color: {c['accent']};
                background: transparent;
                padding: 4px 0px;
                border-bottom: 2px solid {c['accent']};
            }}

            /* Coefficient table */
            QLabel#coeffHeader {{
                font-size: 12px;
                font-weight: bold;
                color: {c['text_muted']};
                background: transparent;
                padding: 6px 8px;
            }}
            QFrame#coeffSep {{
                background-color: {border_subtle};
            }}
            QLabel#coeffRowName {{
                font-size: 13px;
                font-weight: 600;
                color: {c['text']};
                background: transparent;
                padding: 5px 8px;
            }}
            QLabel#coeffValue {{
                font-size: 13px;
                font-family: "Menlo", "Consolas", "Courier New", monospace;
                color: {c['text']};
                background: transparent;
                padding: 5px 8px;
            }}
            QLabel#pValue {{
                font-size: 13px;
                font-family: "Menlo", "Consolas", "Courier New", monospace;
                background: transparent;
                padding: 5px 8px;
            }}

            /* Cards */
            QFrame#statsCard {{
                background-color: {card_bg};
                border: 1px solid {border_subtle};
                border-radius: 8px;
            }}
            QLabel#cardHeader {{
                font-size: 14px;
                font-weight: bold;
                color: {c['accent']};
                background: transparent;
            }}
            QLabel#cardStatName {{
                font-size: 13px;
                color: {c['text_muted']};
                background: transparent;
                padding: 2px 0px;
            }}
            QLabel#cardStatValue {{
                font-size: 13px;
                font-family: "Menlo", "Consolas", "Courier New", monospace;
                font-weight: 500;
                color: {c['text']};
                background: transparent;
                padding: 2px 0px;
            }}

            /* Placeholder */
            QLabel#placeholder {{
                font-size: 16px;
                color: {c['text_muted']};
                background: transparent;
                padding: 40px;
            }}

            QLabel {{
                background: transparent;
            }}
        """)
