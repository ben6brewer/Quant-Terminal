"""GDP FRED Service — Real/Nominal GDP, growth, components, industrial production, capacity utilization."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional

from app.services.base_fred_service import BaseFredService

if TYPE_CHECKING:
    import pandas as pd

# ─── Series definitions ───────────────────────────────────────────────────────

# Quarterly GDP series
QUARTERLY_SERIES: Dict[str, str] = {
    "Real GDP": "GDPC1",
    "Nominal GDP": "GDP",
    "GDP Growth": "A191RL1Q225SBEA",
    # Real components
    "PCE": "PCECC96",
    "Investment": "GPDIC1",
    "Government": "GCEC1",
    "Exports": "EXPGSC1",
    "Imports": "IMPGSC1",
    # Nominal components
    "Nominal PCE": "PCEC",
    "Nominal Investment": "GPDI",
    "Nominal Government": "GCE",
    "Nominal Exports": "EXPGS",
    "Nominal Imports": "IMPGS",
    "USREC": "USREC",
}

# Monthly production series
PRODUCTION_SERIES: Dict[str, str] = {
    "Industrial Production": "INDPRO",
    "Manufacturing": "IPMAN",
    "Capacity Utilization": "TCU",
}

# Cache paths
_CACHE_DIR = Path.home() / ".quant_terminal" / "cache" / "fred"
_QUARTERLY_CACHE = _CACHE_DIR / "gdp_quarterly.parquet"
_PRODUCTION_CACHE = _CACHE_DIR / "production_monthly.parquet"


class GdpFredService(BaseFredService):
    """
    Fetches GDP and industrial production data from FRED.

    Quarterly group (GDP, components, USREC) — cache freshness: 45 days.
    Monthly group (IP, manufacturing, capacity util) — cache freshness: 7 days.
    """

    _data: Optional[Dict[str, "pd.DataFrame"]] = None
    _last_quarterly_fetch: Optional[float] = None
    _last_production_fetch: Optional[float] = None

    @classmethod
    def fetch_all_data(cls) -> Optional[Dict[str, "pd.DataFrame"]]:
        """
        Fetch all GDP and production data, using cache when current.

        Returns dict with keys:
          "gdp"        — Quarterly DataFrame with Real GDP, Nominal GDP (trillions USD)
          "growth"     — Quarterly DataFrame with GDP Growth (QoQ annualized %)
          "components" — Quarterly DataFrame with PCE, Investment, Government, Exports, Imports (trillions)
          "production" — Monthly DataFrame with Industrial Production index, Manufacturing index
          "capacity"   — Monthly DataFrame with Capacity Utilization (%)
          "usrec"      — DataFrame with USREC (0/1)
        Returns None if API key missing or all fetches fail.
        """
        import pandas as pd

        quarterly_raw = cls._get_group(
            QUARTERLY_SERIES, _QUARTERLY_CACHE, "_last_quarterly_fetch", max_age_days=45
        )
        production_raw = cls._get_group(
            PRODUCTION_SERIES, _PRODUCTION_CACHE, "_last_production_fetch", max_age_days=7
        )

        result: Dict[str, pd.DataFrame] = {}

        if quarterly_raw is not None and not quarterly_raw.empty:
            gdp_cols = [c for c in ["Real GDP", "Nominal GDP"] if c in quarterly_raw.columns]
            if gdp_cols:
                gdp_df = quarterly_raw[gdp_cols].copy()
                gdp_df = gdp_df / 1000.0  # billions -> trillions
                gdp_df = gdp_df.dropna(how="all")
                result["gdp"] = gdp_df

            if "GDP Growth" in quarterly_raw.columns:
                result["growth"] = quarterly_raw[["GDP Growth"]].dropna(how="all")

            comp_cols = [c for c in ["PCE", "Investment", "Government", "Exports", "Imports"]
                         if c in quarterly_raw.columns]
            if comp_cols:
                comp_df = quarterly_raw[comp_cols].copy()
                comp_df = comp_df / 1000.0  # billions -> trillions
                comp_df = comp_df.dropna(how="all")
                result["components"] = comp_df

            nom_comp_cols = [c for c in ["Nominal PCE", "Nominal Investment", "Nominal Government",
                                         "Nominal Exports", "Nominal Imports"]
                             if c in quarterly_raw.columns]
            if nom_comp_cols:
                nom_df = quarterly_raw[nom_comp_cols].copy()
                nom_df = nom_df / 1000.0  # billions -> trillions
                # Rename to match real component names for chart compatibility
                nom_df = nom_df.rename(columns={
                    "Nominal PCE": "PCE",
                    "Nominal Investment": "Investment",
                    "Nominal Government": "Government",
                    "Nominal Exports": "Exports",
                    "Nominal Imports": "Imports",
                })
                nom_df = nom_df.dropna(how="all")
                result["nominal_components"] = nom_df

            if "USREC" in quarterly_raw.columns:
                result["usrec"] = quarterly_raw[["USREC"]].dropna(how="all")

        if production_raw is not None and not production_raw.empty:
            prod_cols = [c for c in ["Industrial Production", "Manufacturing"]
                         if c in production_raw.columns]
            if prod_cols:
                result["production"] = production_raw[prod_cols].dropna(how="all")

            if "Capacity Utilization" in production_raw.columns:
                result["capacity"] = production_raw[["Capacity Utilization"]].dropna(how="all")

        if not result:
            return None

        cls._data = result
        return result

    @classmethod
    def get_latest_stats(cls, data: Dict) -> Optional[Dict]:
        """
        Extract latest readings for toolbar display.

        Returns dict with: real_gdp, gdp_growth, quarter, ip_index, ip_mom, capacity_util
        """
        if not data:
            return None

        result = {}

        gdp_df = data.get("gdp")
        if gdp_df is not None and "Real GDP" in gdp_df.columns:
            s = gdp_df["Real GDP"].dropna()
            if not s.empty:
                result["real_gdp"] = round(float(s.iloc[-1]), 2)

        growth_df = data.get("growth")
        if growth_df is not None and "GDP Growth" in growth_df.columns:
            s = growth_df["GDP Growth"].dropna()
            if not s.empty:
                result["gdp_growth"] = round(float(s.iloc[-1]), 1)
                ts = s.index[-1]
                q = (ts.month - 1) // 3 + 1
                result["quarter"] = f"Q{q} {ts.year}"

        prod_df = data.get("production")
        if prod_df is not None and "Industrial Production" in prod_df.columns:
            s = prod_df["Industrial Production"].dropna()
            if not s.empty:
                result["ip_index"] = round(float(s.iloc[-1]), 1)
                if len(s) >= 2:
                    mom = float(s.iloc[-1]) - float(s.iloc[-2])
                    result["ip_mom"] = round(mom, 2)

        cap_df = data.get("capacity")
        if cap_df is not None and "Capacity Utilization" in cap_df.columns:
            s = cap_df["Capacity Utilization"].dropna()
            if not s.empty:
                result["capacity_util"] = round(float(s.iloc[-1]), 1)

        return result if result else None
