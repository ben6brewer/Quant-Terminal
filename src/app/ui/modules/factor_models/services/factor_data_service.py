"""Factor Data Service — downloads and caches FF, Q-factor, and AQR factor data."""

from __future__ import annotations

import logging
import threading
from datetime import datetime, date
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from .model_definitions import FactorModelSpec

if TYPE_CHECKING:
    import pandas as pd

logger = logging.getLogger(__name__)


class FactorDataService:
    """Unified service for downloading / caching all factor datasets.

    Cache layout (``~/.quant_terminal/cache/factors/``):
        ff_daily.parquet / ff_monthly.parquet
        q_daily.parquet  / q_monthly.parquet
        aqr_bab_monthly.parquet / aqr_qmj_monthly.parquet / aqr_hml_devil_monthly.parquet
        {name}_last_update.txt

    Same-day staleness: if timestamp == today, skip download.
    """

    _CACHE_DIR = Path.home() / ".quant_terminal" / "cache" / "factors"
    _lock = threading.Lock()

    # In-memory caches keyed by filename stem (e.g. "ff_daily")
    _memory: dict[str, "pd.DataFrame"] = {}

    # ── Public API ──────────────────────────────────────────────────────────

    @classmethod
    def get_factors(
        cls,
        model_spec: FactorModelSpec,
        frequency: str,
    ) -> tuple["pd.DataFrame", "pd.Series"]:
        """Return (factor_df, rf_series) for the given model and frequency.

        ``factor_df`` has columns matching ``model_spec.factors``.
        ``rf_series`` is the risk-free rate at the same frequency.
        """
        import pandas as pd

        source = model_spec.source

        if source == "ff":
            ff = cls._load_ff(frequency)
            rf = ff["RF"].copy()
            factor_df = ff[[c for c in model_spec.factors if c in ff.columns]].copy()

        elif source == "q":
            q = cls._load_q(frequency)
            # Q-factor datasets don't carry RF — use FF RF
            ff = cls._load_ff(frequency)
            rf = ff["RF"].copy()
            factor_df = q[[c for c in model_spec.factors if c in q.columns]].copy()

        elif source == "mixed":
            ff = cls._load_ff(frequency)
            rf = ff["RF"].copy()

            # Start with FF columns
            parts = [ff]

            # Determine which AQR datasets we need
            needed_aqr = set(model_spec.factors) - set(ff.columns)
            if "BAB" in needed_aqr:
                bab = cls._load_aqr("bab", frequency)
                if bab is not None:
                    parts.append(bab[["BAB"]])
            if "QMJ" in needed_aqr:
                qmj = cls._load_aqr("qmj", frequency)
                if qmj is not None:
                    parts.append(qmj[["QMJ"]])
            if "HML_DEVIL" in needed_aqr:
                hml_d = cls._load_aqr("hml_devil", frequency)
                if hml_d is not None:
                    parts.append(hml_d[["HML_DEVIL"]])

            # Normalize all parts to month-start so FF (1st-of-month)
            # and AQR (end-of-month) indices align correctly.
            if frequency == "monthly":
                for i, p in enumerate(parts):
                    p = p.copy()
                    p.index = p.index.to_period("M").to_timestamp()
                    parts[i] = p
                rf = rf.copy()
                rf.index = rf.index.to_period("M").to_timestamp()

            combined = parts[0]
            for p in parts[1:]:
                combined = combined.join(p, how="inner")

            factor_df = combined[[c for c in model_spec.factors if c in combined.columns]].copy()

        elif source == "custom":
            factor_df, rf = cls._load_custom(model_spec, frequency)

        else:
            raise ValueError(f"Unknown source: {source}")

        # Validate all expected factor columns are present
        missing = [c for c in model_spec.factors if c not in factor_df.columns]
        if missing:
            raise ValueError(
                f"Factor data missing columns {missing} for model {model_spec.name}. "
                "The data source may be unavailable."
            )

        return factor_df, rf

    # ── Custom (mixed-source, user-defined) ────────────────────────────────

    @classmethod
    def _load_custom(
        cls, model_spec: FactorModelSpec, frequency: str
    ) -> tuple["pd.DataFrame", "pd.Series"]:
        """Load factor data for a custom model that may mix FF, Q, and AQR factors."""
        from .custom_model_store import _FF_FACTORS, _Q_FACTORS, _AQR_FACTORS

        factors_set = set(model_spec.factors)

        # Always load FF for Mkt-RF and RF
        ff = cls._load_ff(frequency)
        rf = ff["RF"].copy()
        parts = [ff]

        # Load Q if any Q factors are needed
        needs_q = bool(factors_set & _Q_FACTORS)
        if needs_q:
            q = cls._load_q(frequency)
            parts.append(q)

        # Load AQR datasets if needed (monthly only)
        if "BAB" in factors_set:
            bab = cls._load_aqr("bab", frequency)
            if bab is not None:
                parts.append(bab[["BAB"]])
        if "QMJ" in factors_set:
            qmj = cls._load_aqr("qmj", frequency)
            if qmj is not None:
                parts.append(qmj[["QMJ"]])
        if "HML_DEVIL" in factors_set:
            hml_d = cls._load_aqr("hml_devil", frequency)
            if hml_d is not None:
                parts.append(hml_d[["HML_DEVIL"]])

        # Normalize monthly indices across sources
        has_aqr = bool(factors_set & _AQR_FACTORS)
        if frequency == "monthly" and (has_aqr or needs_q):
            for i, p in enumerate(parts):
                p = p.copy()
                p.index = p.index.to_period("M").to_timestamp()
                parts[i] = p
            rf = rf.copy()
            rf.index = rf.index.to_period("M").to_timestamp()

        # Join all parts
        combined = parts[0]
        for p in parts[1:]:
            combined = combined.join(p, how="inner", rsuffix="_dup")
        # Drop any duplicate columns from join
        combined = combined.loc[:, ~combined.columns.str.endswith("_dup")]

        factor_df = combined[
            [c for c in model_spec.factors if c in combined.columns]
        ].copy()
        return factor_df, rf

    # ── Fama-French ─────────────────────────────────────────────────────────

    @classmethod
    def _load_ff(cls, frequency: str) -> "pd.DataFrame":
        """Load Fama-French 5 + Momentum + RF at the given frequency."""
        if frequency == "monthly":
            return cls._load_or_fetch("ff_monthly", cls._fetch_ff_monthly)
        else:
            daily = cls._load_or_fetch("ff_daily", cls._fetch_ff_daily)
            if frequency == "weekly":
                return cls._resample_daily_to_weekly(daily)
            return daily

    @classmethod
    def _fetch_ff_daily(cls) -> "pd.DataFrame":
        from app.services.ken_french_loader import fetch_ff_dataset

        logger.info("Fetching FF5 daily factors from Ken French...")
        ff5 = fetch_ff_dataset(
            "F-F_Research_Data_5_Factors_2x3_daily", start="1963-01-01"
        )

        logger.info("Fetching Momentum daily factor from Ken French...")
        mom = fetch_ff_dataset(
            "F-F_Momentum_Factor_daily", start="1963-01-01"
        )
        mom = cls._normalize_mom_col(mom)

        factors = ff5.join(mom, how="inner")
        factors = cls._clean_ff(factors)
        logger.info("FF daily: %d rows, %s to %s", len(factors), factors.index.min(), factors.index.max())
        return factors

    @classmethod
    def _fetch_ff_monthly(cls) -> "pd.DataFrame":
        from app.services.ken_french_loader import fetch_ff_dataset

        logger.info("Fetching FF5 monthly factors from Ken French...")
        ff5 = fetch_ff_dataset(
            "F-F_Research_Data_5_Factors_2x3", start="1963-01-01"
        )

        logger.info("Fetching Momentum monthly factor from Ken French...")
        mom = fetch_ff_dataset(
            "F-F_Momentum_Factor", start="1963-01-01"
        )
        mom = cls._normalize_mom_col(mom)

        factors = ff5.join(mom, how="inner")
        factors = cls._clean_ff(factors)
        logger.info("FF monthly: %d rows, %s to %s", len(factors), factors.index.min(), factors.index.max())
        return factors

    @staticmethod
    def _normalize_mom_col(mom: "pd.DataFrame") -> "pd.DataFrame":
        """Rename the momentum column to UMD regardless of original name."""
        import pandas as pd

        if "UMD" in mom.columns:
            return mom[["UMD"]]
        for col in mom.columns:
            if "mom" in col.lower().strip():
                return mom.rename(columns={col: "UMD"})[["UMD"]]
        # Fallback
        mom = pd.DataFrame(index=mom.index)
        mom["UMD"] = 0.0
        return mom

    @staticmethod
    def _clean_ff(df: "pd.DataFrame") -> "pd.DataFrame":
        """Convert FF data from percentages to decimals and ensure DatetimeIndex."""
        import pandas as pd

        for col in df.columns:
            df[col] = df[col] / 100.0

        expected = ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "RF", "UMD"]
        for col in expected:
            if col not in df.columns:
                df[col] = 0.0

        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index.astype(str))
        df.index.name = "Date"

        return df[expected]

    # ── Q-Factor (HXZ) ─────────────────────────────────────────────────────

    @classmethod
    def _load_q(cls, frequency: str) -> "pd.DataFrame":
        if frequency == "monthly":
            return cls._load_or_fetch("q_monthly", cls._fetch_q_monthly)
        else:
            daily = cls._load_or_fetch("q_daily", cls._fetch_q_daily)
            if frequency == "weekly":
                return cls._resample_daily_to_weekly(daily)
            return daily

    @classmethod
    def _fetch_q_daily(cls) -> "pd.DataFrame":
        return cls._fetch_q_csv(
            "http://global-q.org/uploads/1/2/2/6/122679606/q5_factors_daily_2023.csv",
            "daily",
        )

    @classmethod
    def _fetch_q_monthly(cls) -> "pd.DataFrame":
        return cls._fetch_q_csv(
            "http://global-q.org/uploads/1/2/2/6/122679606/q5_factors_monthly_2023.csv",
            "monthly",
        )

    @classmethod
    def _fetch_q_csv(cls, url: str, label: str) -> "pd.DataFrame":
        import pandas as pd

        logger.info("Fetching Q-factor %s data from %s", label, url)
        try:
            df = pd.read_csv(url)
        except Exception as e:
            raise ValueError(f"Failed to download Q-factor {label} data: {e}") from e

        # Build date column
        if "year" in df.columns and "month" in df.columns:
            if "day" in df.columns:
                df["date"] = pd.to_datetime(
                    df[["year", "month", "day"]].rename(
                        columns={"year": "year", "month": "month", "day": "day"}
                    )
                )
            else:
                df["date"] = pd.to_datetime(
                    df["year"].astype(str) + "-" + df["month"].astype(str).str.zfill(2) + "-01"
                )

        df = df.set_index("date")
        df.index = pd.to_datetime(df.index)
        df.index.name = "Date"

        # Standardize column names
        rename = {}
        for col in df.columns:
            col_low = col.strip().lower()
            if col_low in ("r_mkt", "mkt"):
                rename[col] = "R_MKT"
            elif col_low in ("r_me", "me"):
                rename[col] = "R_ME"
            elif col_low in ("r_ia", "ia"):
                rename[col] = "R_IA"
            elif col_low in ("r_roe", "roe"):
                rename[col] = "R_ROE"
            elif col_low in ("r_eg", "eg"):
                rename[col] = "R_EG"
        df = df.rename(columns=rename)

        expected = ["R_MKT", "R_ME", "R_IA", "R_ROE", "R_EG"]
        for col in expected:
            if col not in df.columns:
                df[col] = 0.0

        # Q-factor data is in percentages — convert to decimal
        for col in expected:
            df[col] = df[col] / 100.0

        logger.info("Q-factor %s: %d rows", label, len(df))
        return df[expected]

    # ── AQR ─────────────────────────────────────────────────────────────────

    @classmethod
    def _load_aqr(cls, dataset: str, frequency: str) -> Optional["pd.DataFrame"]:
        """Load an AQR dataset. AQR is monthly-only."""
        if frequency not in ("monthly",):
            return None
        key = f"aqr_{dataset}_monthly"
        fetch_fn = {
            "bab": cls._fetch_aqr_bab,
            "qmj": cls._fetch_aqr_qmj,
            "hml_devil": cls._fetch_aqr_hml_devil,
        }.get(dataset)
        if fetch_fn is None:
            return None
        try:
            return cls._load_or_fetch(key, fetch_fn)
        except Exception as e:
            logger.warning("AQR %s download failed: %s", dataset, e)
            return None

    @classmethod
    def _fetch_aqr_bab(cls) -> "pd.DataFrame":
        return cls._fetch_aqr_excel(
            "https://www.aqr.com/-/media/AQR/Documents/Insights/Data-Sets/Betting-Against-Beta-Equity-Factors-Monthly.xlsx",
            col_name="BAB",
            sheet_pattern="usa",
        )

    @classmethod
    def _fetch_aqr_qmj(cls) -> "pd.DataFrame":
        return cls._fetch_aqr_excel(
            "https://www.aqr.com/-/media/AQR/Documents/Insights/Data-Sets/Quality-Minus-Junk-Factors-Monthly.xlsx",
            col_name="QMJ",
            sheet_pattern="usa",
        )

    @classmethod
    def _fetch_aqr_hml_devil(cls) -> "pd.DataFrame":
        return cls._fetch_aqr_excel(
            "https://www.aqr.com/-/media/AQR/Documents/Insights/Data-Sets/The-Devil-in-HMLs-Details-Factors-Monthly.xlsx",
            col_name="HML_DEVIL",
            sheet_pattern="usa",
        )

    @classmethod
    def _fetch_aqr_excel(cls, url: str, col_name: str, sheet_pattern: str) -> "pd.DataFrame":
        """Download an AQR Excel file, find the USA sheet, and return a single-column DataFrame."""
        import pandas as pd

        logger.info("Fetching AQR %s from %s", col_name, url)
        try:
            xls = pd.ExcelFile(url)
        except Exception as e:
            raise ValueError(f"Failed to download AQR {col_name}: {e}") from e

        # Find the USA sheet (case-insensitive)
        sheet_name = None
        for s in xls.sheet_names:
            if sheet_pattern in s.lower():
                sheet_name = s
                break
        if sheet_name is None:
            # Fallback to first sheet
            sheet_name = xls.sheet_names[0]

        df = pd.read_excel(xls, sheet_name=sheet_name, header=0)

        # Find the date column
        date_col = None
        for c in df.columns:
            if "date" in str(c).lower() or df[c].dtype == "datetime64[ns]":
                date_col = c
                break
        if date_col is None:
            date_col = df.columns[0]

        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df = df.dropna(subset=[date_col])
        df = df.set_index(date_col)
        df.index.name = "Date"

        # Find the data column (usually 2nd column after date, or one named "USA", etc.)
        data_col = None
        for c in df.columns:
            if c != date_col and df[c].dtype in ("float64", "int64", "float32"):
                data_col = c
                break
        if data_col is None:
            data_col = df.columns[0]

        result = pd.DataFrame(index=df.index)
        result[col_name] = pd.to_numeric(df[data_col], errors="coerce")

        # AQR data may be in decimal or percentage — check magnitude
        sample = result[col_name].dropna().abs()
        if len(sample) > 0 and sample.median() > 1.0:
            result[col_name] = result[col_name] / 100.0

        result = result.dropna()
        logger.info("AQR %s: %d rows", col_name, len(result))
        return result

    # ── Cache Infrastructure ────────────────────────────────────────────────

    @classmethod
    def _load_or_fetch(cls, key: str, fetch_fn) -> "pd.DataFrame":
        """Load from memory/disk cache if fresh today, else fetch and cache."""
        with cls._lock:
            if key in cls._memory and cls._is_fresh(key):
                return cls._memory[key]

            if cls._is_fresh(key):
                df = cls._read_parquet(key)
                if df is not None:
                    cls._memory[key] = df
                    return df

            df = fetch_fn()
            cls._write_parquet(key, df)
            cls._save_timestamp(key)
            cls._memory[key] = df
            return df

    @classmethod
    def _is_fresh(cls, key: str) -> bool:
        """Return True if the cache file was updated today."""
        ts_file = cls._CACHE_DIR / f"{key}_last_update.txt"
        if not ts_file.exists():
            return False
        try:
            text = ts_file.read_text().strip()
            last = datetime.fromisoformat(text)
            return last.date() == date.today()
        except (ValueError, IOError):
            return False

    @classmethod
    def _save_timestamp(cls, key: str) -> None:
        cls._ensure_dir()
        ts_file = cls._CACHE_DIR / f"{key}_last_update.txt"
        ts_file.write_text(datetime.now().isoformat())

    @classmethod
    def _read_parquet(cls, key: str) -> Optional["pd.DataFrame"]:
        import pandas as pd

        path = cls._CACHE_DIR / f"{key}.parquet"
        if not path.exists():
            return None
        try:
            return pd.read_parquet(path)
        except Exception as e:
            logger.warning("Failed to read cache %s: %s", key, e)
            return None

    @classmethod
    def _write_parquet(cls, key: str, df: "pd.DataFrame") -> None:
        cls._ensure_dir()
        path = cls._CACHE_DIR / f"{key}.parquet"
        try:
            df.to_parquet(path)
        except Exception as e:
            logger.warning("Failed to write cache %s: %s", key, e)

    @classmethod
    def _ensure_dir(cls) -> None:
        cls._CACHE_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def _resample_daily_to_weekly(cls, daily: "pd.DataFrame") -> "pd.DataFrame":
        """Resample daily factor returns to weekly by summing (approx for small returns)."""
        return daily.resample("W-FRI").sum()

    @classmethod
    def clear_cache(cls) -> None:
        """Clear all factor caches."""
        with cls._lock:
            cls._memory.clear()
            if cls._CACHE_DIR.exists():
                for f in cls._CACHE_DIR.iterdir():
                    f.unlink()
        logger.info("Factor data cache cleared")
