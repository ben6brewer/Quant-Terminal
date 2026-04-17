"""Custom data service: persistence and lookup for user-imported return series.

Imported tickers are stored under ``~/.quant_terminal/custom_data/`` and
referenced from other modules via the prefix ``[Custom] {name}``.

Storage lives outside ``~/.quant_terminal/cache/`` so it survives the
data-source cache reset performed by ``market_data._check_data_source_version``.
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional

from app.core.paths import user_data_dir

if TYPE_CHECKING:
    import pandas as pd


CUSTOM_PREFIX = "[Custom] "

ASSET_CLASSES: List[str] = [
    "Equity",
    "Fixed Income",
    "Real Estate",
    "Commodities",
    "Alternatives",
    "Cash",
    "Other",
]

ALLOWED_FREQUENCIES: List[str] = ["daily", "weekly", "monthly", "yearly"]

_FREQ_RANK = {"daily": 0, "weekly": 1, "monthly": 2, "yearly": 3}

# Map all known interval aliases used elsewhere in the app to canonical names.
_INTERVAL_TO_FREQ = {
    "daily": "daily", "1d": "daily", "d": "daily",
    "weekly": "weekly", "1wk": "weekly", "w": "weekly",
    "monthly": "monthly", "1mo": "monthly", "m": "monthly", "me": "monthly",
    "yearly": "yearly", "1y": "yearly", "y": "yearly", "ye": "yearly",
}

_RESAMPLE_RULE = {"weekly": "W", "monthly": "ME", "yearly": "YE"}

_WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
}

_lock = threading.Lock()


@dataclass
class CustomImportMeta:
    name: str
    asset_class: str
    frequency: str
    start_date: str
    end_date: str
    row_count: int
    imported_at: str
    source_filename: str


# ── Paths ────────────────────────────────────────────────────────────────────

def _root_dir() -> Path:
    return user_data_dir() / "custom_data"


def _series_dir() -> Path:
    return _root_dir() / "series"


def _metadata_path() -> Path:
    return _root_dir() / "metadata.json"


def _ensure_dirs() -> None:
    _series_dir().mkdir(parents=True, exist_ok=True)


def _safe_name(name: str) -> str:
    safe = name.replace("/", "_").replace("\\", "_")
    if safe.upper() in _WINDOWS_RESERVED:
        safe = f"_{safe}_"
    return safe


def _series_path(name: str) -> Path:
    return _series_dir() / f"{_safe_name(name)}.parquet"


# ── Metadata I/O ─────────────────────────────────────────────────────────────

def _read_metadata() -> Dict[str, dict]:
    path = _metadata_path()
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            blob = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(blob, dict):
        return {}
    imports = blob.get("imports", {})
    return imports if isinstance(imports, dict) else {}


def _write_metadata(imports: Dict[str, dict]) -> None:
    _ensure_dirs()
    path = _metadata_path()
    tmp = path.with_suffix(path.suffix + ".tmp")
    blob = {"version": 1, "imports": imports}
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(blob, f, indent=2)
    os.replace(tmp, path)


# ── Prefix utilities ─────────────────────────────────────────────────────────

def is_custom_ticker(ticker: str) -> bool:
    """Case-insensitive check for the [Custom] prefix on the raw input."""
    if not ticker:
        return False
    stripped = ticker.lstrip()
    return stripped.lower().startswith(CUSTOM_PREFIX.lower())


def parse_custom_ticker(ticker: str) -> Optional[str]:
    """Strip the prefix, then resolve case-insensitively against metadata.

    Returns the canonical (case-preserved) stored name, or None if no
    matching import exists.
    """
    if not is_custom_ticker(ticker):
        return None
    raw = ticker.lstrip()[len(CUSTOM_PREFIX):].strip()
    if not raw:
        return None
    with _lock:
        imports = _read_metadata()
    target = raw.lower()
    for key in imports.keys():
        if key.lower() == target:
            return key
    return None


def format_custom_ticker(name: str) -> str:
    return f"{CUSTOM_PREFIX}{name}"


# ── CRUD ─────────────────────────────────────────────────────────────────────

def list_custom_tickers() -> List[CustomImportMeta]:
    with _lock:
        imports = _read_metadata()
    out: List[CustomImportMeta] = []
    for entry in imports.values():
        try:
            out.append(CustomImportMeta(**entry))
        except TypeError:
            continue
    out.sort(key=lambda m: m.name.lower())
    return out


def get_metadata(name: str) -> Optional[CustomImportMeta]:
    with _lock:
        imports = _read_metadata()
    target = name.lower()
    for key, entry in imports.items():
        if key.lower() == target:
            try:
                return CustomImportMeta(**entry)
            except TypeError:
                return None
    return None


def save_custom_import(
    name: str,
    returns: "pd.Series",
    frequency: str,
    asset_class: str,
    source_filename: str,
) -> CustomImportMeta:
    """Persist a clean returns series. Overwrites any existing import with the
    same (case-insensitive) name."""
    import pandas as pd

    if frequency not in ALLOWED_FREQUENCIES:
        raise ValueError(
            f"frequency must be one of {ALLOWED_FREQUENCIES}, got {frequency!r}"
        )
    if asset_class not in ASSET_CLASSES:
        raise ValueError(
            f"asset_class must be one of {ASSET_CLASSES}, got {asset_class!r}"
        )
    if returns.empty:
        raise ValueError("Cannot save an empty returns series.")

    _ensure_dirs()

    # Normalize series for storage.
    s = returns.copy()
    s.index = pd.DatetimeIndex(s.index).tz_localize(None).normalize()
    s = s.sort_index()
    s = s[~s.index.duplicated(keep="last")]
    s.name = "returns"

    df = s.to_frame()
    df.index.name = "date"

    with _lock:
        imports = _read_metadata()

        # Case-insensitive dedup: if an existing key matches, drop it so the
        # new (case-preserved) name takes its place.
        target = name.lower()
        old_keys = [k for k in imports.keys() if k.lower() == target]
        for k in old_keys:
            imports.pop(k, None)
            old_path = _series_path(k)
            if old_path.exists() and _series_path(name) != old_path:
                try:
                    old_path.unlink()
                except OSError:
                    pass

        df.to_parquet(_series_path(name))

        meta = CustomImportMeta(
            name=name,
            asset_class=asset_class,
            frequency=frequency,
            start_date=s.index.min().strftime("%Y-%m-%d"),
            end_date=s.index.max().strftime("%Y-%m-%d"),
            row_count=int(len(s)),
            imported_at=datetime.now().replace(microsecond=0).isoformat(),
            source_filename=source_filename,
        )
        imports[name] = asdict(meta)
        _write_metadata(imports)

    return meta


def delete_custom_import(name: str) -> bool:
    with _lock:
        imports = _read_metadata()
        target = name.lower()
        match_keys = [k for k in imports.keys() if k.lower() == target]
        if not match_keys:
            return False
        for k in match_keys:
            imports.pop(k, None)
            path = _series_path(k)
            if path.exists():
                try:
                    path.unlink()
                except OSError:
                    pass
        _write_metadata(imports)
    return True


# ── Reads ────────────────────────────────────────────────────────────────────

def _load_series(name: str) -> "pd.Series":
    import pandas as pd

    path = _series_path(name)
    if not path.exists():
        raise ValueError(f"Custom ticker '{name}' has no stored data.")
    df = pd.read_parquet(path)
    if "returns" not in df.columns:
        raise ValueError(f"Custom ticker '{name}' parquet is malformed.")
    s = df["returns"].astype(float)
    s.index = pd.DatetimeIndex(s.index).tz_localize(None).normalize()
    s = s.sort_index()
    s.name = "returns"
    return s


def _validate_and_resample(
    returns: "pd.Series",
    name: str,
    stored_freq: str,
    requested_interval: str,
) -> "pd.Series":
    req_key = (requested_interval or "daily").strip().lower()
    req = _INTERVAL_TO_FREQ.get(req_key, "daily")
    if _FREQ_RANK[req] < _FREQ_RANK[stored_freq]:
        raise ValueError(
            f"Custom ticker '{name}' was imported at {stored_freq} frequency; "
            f"cannot serve {req} data (which is finer). "
            f"Reimport at {req} or finer to use this interval."
        )
    if req == stored_freq:
        return returns
    rule = _RESAMPLE_RULE[req]
    return returns.resample(rule).apply(lambda r: (1 + r).prod() - 1).dropna()


def get_custom_returns(name: str, interval: str = "daily") -> "pd.Series":
    """Returns Series of decimal returns at the requested interval.

    Raises ValueError if the ticker doesn't exist or interval is finer than
    the stored frequency.
    """
    meta = get_metadata(name)
    if meta is None:
        raise ValueError(f"Unknown custom ticker: {name!r}")
    s = _load_series(name)
    s = _validate_and_resample(s, name, meta.frequency, interval)
    s.name = format_custom_ticker(name)
    return s


def custom_end_dates(tickers: List[str]) -> Dict[str, str]:
    """Return ``{ticker: meta.end_date}`` (ISO date string) for every
    ``[Custom]`` ticker in ``tickers`` whose import resolves.

    Non-custom or unknown tickers are not included in the result. Use the
    minimum of the values to find the latest date where all custom
    constituents have data.
    """
    out: Dict[str, str] = {}
    for t in tickers:
        if not is_custom_ticker(t):
            continue
        name = parse_custom_ticker(t)
        if name is None:
            continue
        meta = get_metadata(name)
        if meta is None:
            continue
        out[t] = meta.end_date
    return out


def coarsest_custom_frequency(tickers: List[str]) -> Optional[str]:
    """Return the coarsest native frequency among any [Custom] tickers in
    ``tickers``, or None if there are no resolvable custom tickers.

    Uses ``_FREQ_RANK`` to compare; ties prefer the first encountered.
    """
    coarsest_rank = -1
    coarsest_freq: Optional[str] = None
    for t in tickers:
        if not is_custom_ticker(t):
            continue
        name = parse_custom_ticker(t)
        if name is None:
            continue
        meta = get_metadata(name)
        if meta is None:
            continue
        rank = _FREQ_RANK.get(meta.frequency, 0)
        if rank > coarsest_rank:
            coarsest_rank = rank
            coarsest_freq = meta.frequency
    return coarsest_freq


def get_custom_prices(name: str, interval: str = "daily") -> "pd.DataFrame":
    """Synthesize an OHLCV DataFrame from cumulative returns starting at 100.

    Open == High == Low == Close. Volume is 0. Index is tz-naive
    DatetimeIndex matching the (possibly resampled) returns.
    """
    import pandas as pd

    returns = get_custom_returns(name, interval=interval)
    if returns.empty:
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])

    close = 100.0 * (1.0 + returns).cumprod()
    df = pd.DataFrame(
        {
            "Open": close.values,
            "High": close.values,
            "Low": close.values,
            "Close": close.values,
            "Volume": 0,
        },
        index=close.index,
    )
    df.index.name = None
    return df
