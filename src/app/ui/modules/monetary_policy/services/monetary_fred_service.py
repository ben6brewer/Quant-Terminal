"""Monetary Policy FRED Service — M1/M2, Fed Balance Sheet, EFFR, Reserves, M2 Velocity."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional

from app.services.base_fred_service import BaseFredService

if TYPE_CHECKING:
    import pandas as pd

# ─── Series definitions ───────────────────────────────────────────────────────

# Monthly: M1, M2, M2 Velocity, NBER recession indicator
MONTHLY_SERIES: Dict[str, str] = {
    "M1":        "M1SL",
    "M2":        "M2SL",
    "M2 Velocity": "M2V",
    "USREC":     "USREC",
}

# Weekly: Fed balance sheet components
WEEKLY_SERIES: Dict[str, str] = {
    "Total Assets":    "WALCL",
    "Treasuries":      "WSHOTSL",
    "MBS":             "WSHOMCB",
    "Agency Debt":     "WSHOFADSL",
    "Loans":           "WLCFLL",
    "Reserve Balances": "WRBWFRBL",
}

# EFFR series (daily target bounds, monthly effective rate)
EFFR_SERIES: Dict[str, str] = {
    "Fed Funds Rate": "FEDFUNDS",
    "Lower Target":   "DFEDTARL",
    "Upper Target":   "DFEDTARU",
}

# Cache paths
_CACHE_DIR = Path.home() / ".quant_terminal" / "cache" / "fred"
_MONTHLY_CACHE = _CACHE_DIR / "monetary_monthly.parquet"
_WEEKLY_CACHE  = _CACHE_DIR / "monetary_weekly.parquet"
_EFFR_CACHE    = _CACHE_DIR / "monetary_effr.parquet"


class MonetaryFredService(BaseFredService):
    """
    Fetches all monetary policy data from FRED.

    Monthly group (M1, M2, M2V, USREC) — cache freshness: 45 days.
    Weekly group (balance sheet, reserves) — cache freshness: 7 days.
    EFFR group (Fed Funds + target bounds) — cache freshness: 7 days.
    """

    _data: Optional[Dict[str, "pd.DataFrame"]] = None
    _last_monthly_fetch: Optional[float] = None
    _last_weekly_fetch: Optional[float] = None
    _last_effr_fetch: Optional[float] = None

    @classmethod
    def fetch_all_data(cls) -> Optional[Dict[str, "pd.DataFrame"]]:
        """
        Fetch all monetary policy data, using cache when current.

        Returns dict with keys:
          "money_supply"  — Monthly DataFrame with M1, M2 (trillions USD)
          "velocity"      — Monthly/Quarterly DataFrame with M2 Velocity (ratio)
          "usrec"         — Monthly DataFrame with USREC (0/1)
          "balance_sheet" — Weekly DataFrame with Total Assets, Treasuries, MBS, Other (trillions)
          "reserves"      — Weekly DataFrame with Reserve Balances (trillions)
          "effr"          — Monthly+Daily DataFrame with Fed Funds Rate, Lower/Upper Target (%)
        Returns None if API key missing or all fetches fail.
        """
        import pandas as pd

        monthly_raw = cls._get_group(MONTHLY_SERIES, _MONTHLY_CACHE, "_last_monthly_fetch", max_age_days=45)
        weekly_raw  = cls._get_group(WEEKLY_SERIES, _WEEKLY_CACHE, "_last_weekly_fetch", max_age_days=7)
        effr_raw    = cls._get_group(EFFR_SERIES, _EFFR_CACHE, "_last_effr_fetch", max_age_days=7)

        result: Dict[str, pd.DataFrame] = {}

        if monthly_raw is not None and not monthly_raw.empty:
            money_cols = [c for c in ["M1", "M2"] if c in monthly_raw.columns]
            if money_cols:
                supply_df = monthly_raw[money_cols].copy()
                supply_df = supply_df / 1000.0  # billions → trillions
                supply_df = supply_df.dropna(how="all")
                result["money_supply"] = supply_df

            if "M2 Velocity" in monthly_raw.columns:
                result["velocity"] = monthly_raw[["M2 Velocity"]].dropna(how="all")

            if "USREC" in monthly_raw.columns:
                result["usrec"] = monthly_raw[["USREC"]].dropna(how="all")

        if weekly_raw is not None and not weekly_raw.empty:
            bs_known = ["Total Assets", "Treasuries", "MBS", "Agency Debt", "Loans"]
            bs_cols = [c for c in bs_known if c in weekly_raw.columns]
            if bs_cols:
                bs_df = weekly_raw[bs_cols].copy()
                bs_df = bs_df / 1_000_000.0  # millions → trillions
                if "Total Assets" in bs_df.columns:
                    residual = bs_df["Total Assets"].copy()
                    for comp in ["Treasuries", "MBS", "Agency Debt", "Loans"]:
                        if comp in bs_df.columns:
                            residual = residual - bs_df[comp].fillna(0)
                    bs_df["Other"] = residual.clip(lower=0)
                bs_df = bs_df.dropna(how="all")
                result["balance_sheet"] = bs_df

            if "Reserve Balances" in weekly_raw.columns:
                res_df = weekly_raw[["Reserve Balances"]].copy()
                res_df = res_df / 1_000_000.0  # millions → trillions
                res_df = res_df.dropna(how="all")
                result["reserves"] = res_df

        if effr_raw is not None and not effr_raw.empty:
            effr_cols = [c for c in ["Fed Funds Rate", "Lower Target", "Upper Target"]
                         if c in effr_raw.columns]
            if effr_cols:
                result["effr"] = effr_raw[effr_cols].dropna(how="all")

        if not result:
            return None

        cls._data = result
        return result
