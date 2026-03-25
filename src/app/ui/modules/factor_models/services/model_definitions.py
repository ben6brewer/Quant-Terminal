"""Factor Model Definitions — frozen dataclass registry for all supported models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FactorModelSpec:
    """Specification for a single factor model."""

    name: str  # Display name (e.g., "Fama-French 5")
    key: str  # Internal ID (e.g., "ff5")
    factors: tuple[str, ...]  # Column names in unified factor DataFrame
    source: str  # "ff" | "q" | "aqr" | "mixed"
    description: str  # Tooltip text
    min_frequency: str  # Lowest supported frequency ("daily" or "monthly")


# ── Model Registry ──────────────────────────────────────────────────────────

MODELS: dict[str, FactorModelSpec] = {}


def _register(*specs: FactorModelSpec) -> None:
    for s in specs:
        MODELS[s.key] = s


_register(
    FactorModelSpec(
        name="CAPM",
        key="capm",
        factors=("Mkt-RF",),
        source="ff",
        description="Capital Asset Pricing Model — single market factor",
        min_frequency="daily",
    ),
    FactorModelSpec(
        name="Fama-French 3",
        key="ff3",
        factors=("Mkt-RF", "SMB", "HML"),
        source="ff",
        description="Fama-French 3-factor: Market, Size, Value",
        min_frequency="daily",
    ),
    FactorModelSpec(
        name="Carhart 4-Factor",
        key="carhart4",
        factors=("Mkt-RF", "SMB", "HML", "UMD"),
        source="ff",
        description="Carhart 4-factor: FF3 + Momentum",
        min_frequency="daily",
    ),
    FactorModelSpec(
        name="Fama-French 5",
        key="ff5",
        factors=("Mkt-RF", "SMB", "HML", "RMW", "CMA"),
        source="ff",
        description="Fama-French 5-factor: Market, Size, Value, Profitability, Investment",
        min_frequency="daily",
    ),
    FactorModelSpec(
        name="FF5 + Momentum",
        key="ff5mom",
        factors=("Mkt-RF", "SMB", "HML", "RMW", "CMA", "UMD"),
        source="ff",
        description="Fama-French 5-factor + Momentum",
        min_frequency="daily",
    ),
    FactorModelSpec(
        name="Q-Factor (HXZ)",
        key="q4",
        factors=("R_MKT", "R_ME", "R_IA", "R_ROE"),
        source="q",
        description="Hou-Xue-Zhang Q-factor: Market, Size, Investment, Profitability",
        min_frequency="daily",
    ),
    FactorModelSpec(
        name="Q5-Factor",
        key="q5",
        factors=("R_MKT", "R_ME", "R_IA", "R_ROE", "R_EG"),
        source="q",
        description="Q5-factor: Q4 + Expected Growth",
        min_frequency="daily",
    ),
    FactorModelSpec(
        name="FF3 + BAB",
        key="aqr_bab",
        factors=("Mkt-RF", "SMB", "HML", "UMD", "BAB"),
        source="mixed",
        description="FF3 + Momentum + Betting Against Beta (AQR)",
        min_frequency="monthly",
    ),
    FactorModelSpec(
        name="FF3 + QMJ",
        key="aqr_qmj",
        factors=("Mkt-RF", "SMB", "HML", "UMD", "QMJ"),
        source="mixed",
        description="FF3 + Momentum + Quality Minus Junk (AQR)",
        min_frequency="monthly",
    ),
    FactorModelSpec(
        name="AQR Full",
        key="aqr_full",
        factors=("Mkt-RF", "SMB", "HML", "UMD", "BAB", "QMJ", "HML_DEVIL"),
        source="mixed",
        description="FF3 + Momentum + BAB + QMJ + HML Devil (AQR)",
        min_frequency="monthly",
    ),
)

# Ordered list for toolbar dropdown
MODEL_ORDER: list[str] = [
    "capm", "ff3", "carhart4", "ff5", "ff5mom",
    "q4", "q5",
    "aqr_bab", "aqr_qmj", "aqr_full",
]
