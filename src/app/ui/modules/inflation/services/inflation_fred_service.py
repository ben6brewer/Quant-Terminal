"""Inflation FRED Service - Fetches CPI, PCE, PPI, and expectations data from FRED."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional

from app.services.base_fred_service import BaseFredService

if TYPE_CHECKING:
    import pandas as pd

# ─── Series definitions ───────────────────────────────────────────────────────

CPI_SERIES: Dict[str, str] = {
    "Headline CPI": "CPIAUCSL",
    "Core CPI":     "CPILFESL",
    "Food & Beverages": "CPIFABSL",
    "Energy":       "CPIENGSL",
    "Housing":      "CPIHOSSL",
    "Transportation": "CPITRNSL",
    "Medical Care": "CPIMEDSL",
    "Apparel":      "CPIAPPSL",
    "Education":    "CPIEDUSL",
    "Recreation":   "CPIRECSL",
}

PCE_SERIES: Dict[str, str] = {
    "PCE":      "PCEPI",
    "Core PCE": "PCEPILFE",
}

PPI_SERIES: Dict[str, str] = {
    "PPI Final Demand": "PPIFID",
    "PPI Core":         "PPICOR",
    "PPI Energy":       "PPIDES",
    "PPI Services":     "PPIFDS",
}

# Breakevens are already in % (market-implied), Michigan is already in %
EXPECTATIONS_SERIES: Dict[str, str] = {
    "5Y Breakeven":  "T5YIEM",
    "10Y Breakeven": "T10YIEM",
    "Michigan 1Y":   "MICH",
}

# Cache paths
_CACHE_DIR = Path.home() / ".quant_terminal" / "cache" / "fred"
CPI_CACHE_FILE         = _CACHE_DIR / "cpi_data.parquet"
PCE_CACHE_FILE         = _CACHE_DIR / "pce_data.parquet"
PPI_CACHE_FILE         = _CACHE_DIR / "ppi_data.parquet"
EXPECTATIONS_CACHE_FILE = _CACHE_DIR / "inflation_expectations_data.parquet"


class InflationFredService(BaseFredService):
    """
    Fetches all inflation data (CPI, PCE, PPI, Expectations) from FRED.

    Class-level cache: once fetched, subsequent callers in the same session
    return instantly without hitting FRED again.

    Monthly series (CPI, PCE, PPI) — cache freshness: 45 days.
    Expectations (monthly breakevens + Michigan) — cache freshness: 7 days.
    """

    _data: Optional[Dict[str, "pd.DataFrame"]] = None
    _last_cpi_fetch: Optional[float] = None
    _last_pce_fetch: Optional[float] = None
    _last_ppi_fetch: Optional[float] = None
    _last_exp_fetch: Optional[float] = None

    @classmethod
    def fetch_all_data(cls) -> Optional[Dict[str, "pd.DataFrame"]]:
        """
        Fetch all inflation data, using cache when current.

        Returns dict with keys:
          "cpi"          - DataFrame (YoY %) with Headline CPI, Core CPI, 8 components
          "pce"          - DataFrame (YoY %) with PCE, Core PCE
          "ppi"          - DataFrame (YoY %) with 4 PPI series
          "expectations" - DataFrame (already %) with 5Y Breakeven, 10Y Breakeven, Michigan 1Y
        Returns None if API key missing or all fetches fail.
        """
        import pandas as pd

        cpi_raw = cls._get_group(CPI_SERIES, CPI_CACHE_FILE, "_last_cpi_fetch")
        pce_raw = cls._get_group(PCE_SERIES, PCE_CACHE_FILE, "_last_pce_fetch")
        ppi_raw = cls._get_group(PPI_SERIES, PPI_CACHE_FILE, "_last_ppi_fetch")
        exp_df  = cls._get_group(EXPECTATIONS_SERIES, EXPECTATIONS_CACHE_FILE, "_last_exp_fetch", max_age_days=7)

        result: Dict[str, pd.DataFrame] = {}

        if cpi_raw is not None and not cpi_raw.empty:
            result["cpi"] = cls._compute_yoy(cpi_raw)

        if pce_raw is not None and not pce_raw.empty:
            result["pce"] = cls._compute_yoy(pce_raw)

        if ppi_raw is not None and not ppi_raw.empty:
            result["ppi"] = cls._compute_yoy(ppi_raw)

        if exp_df is not None and not exp_df.empty:
            result["expectations"] = exp_df

        if not result:
            return None

        cls._data = result
        return result

    @classmethod
    def get_latest_stats(cls, data: Dict) -> Optional[Dict]:
        """
        Extract the most recent readings for CPI Overview stat cards.

        Returns dict with: headline_cpi, core_cpi, pce, core_pce, date
        """
        if not data:
            return None

        result = {}

        cpi_df = data.get("cpi")
        if cpi_df is not None and not cpi_df.empty:
            if "Headline CPI" in cpi_df.columns:
                s = cpi_df["Headline CPI"].dropna()
                if not s.empty:
                    result["headline_cpi"] = round(float(s.iloc[-1]), 2)
                    result["date"] = s.index[-1].strftime("%b %Y")
            if "Core CPI" in cpi_df.columns:
                s = cpi_df["Core CPI"].dropna()
                if not s.empty:
                    result["core_cpi"] = round(float(s.iloc[-1]), 2)

        pce_df = data.get("pce")
        if pce_df is not None and not pce_df.empty:
            if "PCE" in pce_df.columns:
                s = pce_df["PCE"].dropna()
                if not s.empty:
                    result["pce"] = round(float(s.iloc[-1]), 2)
            if "Core PCE" in pce_df.columns:
                s = pce_df["Core PCE"].dropna()
                if not s.empty:
                    result["core_pce"] = round(float(s.iloc[-1]), 2)

        return result if result else None
