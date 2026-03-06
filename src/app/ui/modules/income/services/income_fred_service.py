"""Income FRED Service — Personal income, savings, and wage growth from FRED."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional

from app.services.base_fred_service import BaseFredService

if TYPE_CHECKING:
    import pandas as pd

INCOME_SERIES: Dict[str, str] = {
    "Personal Income": "PI",
    "Disposable Income": "DSPI",
    "PCE Level": "PCE",
    "Real Personal Income": "RPI",
    "Real Disposable Income": "DSPIC96",
    "Real PCE Level": "PCEC96",
    "Savings Rate": "PSAVERT",
    "Avg Hourly Earnings": "CES0500000003",
    "ECI Wages": "ECIWAG",
    "USREC": "USREC",
}

_CACHE_DIR = Path.home() / ".quant_terminal" / "cache" / "fred"
_INCOME_CACHE = _CACHE_DIR / "income_monthly.parquet"


class IncomeFredService(BaseFredService):
    """Fetches personal income, savings, and wage data from FRED."""

    _data: Optional[Dict[str, "pd.DataFrame"]] = None
    _last_income_fetch: Optional[float] = None

    @classmethod
    def fetch_all_data(cls) -> Optional[Dict[str, "pd.DataFrame"]]:
        import pandas as pd

        raw = cls._get_group(
            INCOME_SERIES, _INCOME_CACHE, "_last_income_fetch", max_age_days=7
        )
        if raw is None or raw.empty:
            return None

        result: Dict[str, pd.DataFrame] = {}

        # Income levels (billions → trillions)
        income_cols = [c for c in ["Personal Income", "Disposable Income", "PCE Level"]
                       if c in raw.columns]
        if income_cols:
            df = raw[income_cols].dropna(how="all").copy()
            for col in df.columns:
                df[col] = df[col] / 1000.0
            result["income"] = df

        # Real income levels (billions → trillions)
        real_cols = [c for c in ["Real Personal Income", "Real Disposable Income", "Real PCE Level"]
                     if c in raw.columns]
        if real_cols:
            rdf = raw[real_cols].dropna(how="all").copy()
            for col in rdf.columns:
                rdf[col] = rdf[col] / 1000.0
            result["real_income"] = rdf

        # Savings rate (already %)
        if "Savings Rate" in raw.columns:
            result["savings"] = raw[["Savings Rate"]].dropna(how="all")

        # Wages — raw levels + YoY%
        wage_cols = [c for c in ["Avg Hourly Earnings", "ECI Wages"] if c in raw.columns]
        if wage_cols:
            wage_df = raw[wage_cols].dropna(how="all")
            # Raw levels (no unit conversion)
            result["wages_raw"] = wage_df.copy()
            # YoY%
            yoy_frames = {}
            if "Avg Hourly Earnings" in wage_df.columns:
                ahe = wage_df["Avg Hourly Earnings"].dropna()
                ahe_yoy = ahe.pct_change(periods=12) * 100
                yoy_frames["AHE YoY%"] = ahe_yoy
            if "ECI Wages" in wage_df.columns:
                eci = wage_df["ECI Wages"].dropna()
                eci_yoy = eci.pct_change(periods=4) * 100  # Quarterly
                yoy_frames["ECI YoY%"] = eci_yoy
            if yoy_frames:
                result["wages"] = pd.DataFrame(yoy_frames).dropna(how="all")

        if "USREC" in raw.columns:
            result["usrec"] = raw[["USREC"]].dropna(how="all")

        if not result:
            return None

        cls._data = result
        return result

    @classmethod
    def get_latest_stats(cls, data: Dict) -> Optional[Dict]:
        if not data:
            return None
        result = {}

        savings_df = data.get("savings")
        if savings_df is not None and "Savings Rate" in savings_df.columns:
            s = savings_df["Savings Rate"].dropna()
            if not s.empty:
                result["savings_rate"] = float(s.iloc[-1])

        income_df = data.get("income")
        if income_df is not None and "Personal Income" in income_df.columns:
            s = income_df["Personal Income"].dropna()
            if not s.empty:
                result["personal_income"] = float(s.iloc[-1])

        wages_df = data.get("wages")
        if wages_df is not None:
            if "AHE YoY%" in wages_df.columns:
                s = wages_df["AHE YoY%"].dropna()
                if not s.empty:
                    result["ahe_yoy"] = float(s.iloc[-1])
            if "ECI YoY%" in wages_df.columns:
                s = wages_df["ECI YoY%"].dropna()
                if not s.empty:
                    result["eci_yoy"] = float(s.iloc[-1])

        wages_raw_df = data.get("wages_raw")
        if wages_raw_df is not None and "Avg Hourly Earnings" in wages_raw_df.columns:
            s = wages_raw_df["Avg Hourly Earnings"].dropna()
            if not s.empty:
                result["ahe_raw"] = float(s.iloc[-1])

        return result if result else None
