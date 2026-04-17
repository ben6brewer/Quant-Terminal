"""Parser for user-supplied returns files (CSV / XLSX).

Contract: file has exactly two columns named "Date" and "Value" (case
insensitive; date column is identified by name containing "date" or "time").
Values are decimal returns (Excel "%" cells are decimal under the hood). A
trailing "%" on string values is auto-stripped and divided by 100 as a
forgiving safety net.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd


SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls"}


def parse_returns_file(file_path: str) -> "pd.Series":
    """Read a CSV/XLSX file of returns into a clean pandas Series.

    Returns:
        A float Series indexed by tz-naive normalized DatetimeIndex,
        sorted ascending, with no NaN or duplicate dates. Series name is
        ``"returns"``.

    Raises:
        ValueError: with a user-facing message on any validation failure.
    """
    import pandas as pd

    path = Path(file_path)
    if not path.exists():
        raise ValueError(f"File not found: {file_path}")

    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type {ext!r}. Use one of: "
            f"{sorted(SUPPORTED_EXTENSIONS)}"
        )

    try:
        if ext == ".csv":
            df = pd.read_csv(path)
        else:
            df = pd.read_excel(path)
    except Exception as e:
        raise ValueError(f"Could not read file: {e}") from e

    if df.shape[1] != 2:
        raise ValueError(
            f"File must have exactly two columns (Date and Value). "
            f"Found {df.shape[1]} columns: {list(df.columns)}"
        )

    # Identify the date column by name; fall back to the first column.
    date_col = None
    for col in df.columns:
        if any(k in str(col).lower() for k in ("date", "time")):
            date_col = col
            break
    if date_col is None:
        date_col = df.columns[0]
    value_col = [c for c in df.columns if c != date_col][0]

    # Drop rows that are entirely empty (common with trailing blank rows).
    df = df.dropna(how="all")

    if len(df) < 2:
        raise ValueError(
            "Need at least two rows of data; found "
            f"{len(df)} after removing blank rows."
        )

    # Parse dates strictly.
    try:
        dates = pd.to_datetime(df[date_col], errors="raise")
    except Exception as e:
        raise ValueError(
            f"Could not parse dates in column {date_col!r}: {e}"
        ) from e

    # Parse values; tolerate trailing percent signs as a safety net.
    raw_values = df[value_col]
    if raw_values.dtype == object:
        parsed: list[float] = []
        first_bad: tuple[int, object] | None = None
        for i, v in enumerate(raw_values.tolist()):
            if v is None:
                parsed.append(float("nan"))
                continue
            if isinstance(v, str):
                s = v.strip()
                divisor = 1.0
                if s.endswith("%"):
                    s = s[:-1].strip()
                    divisor = 100.0
                try:
                    parsed.append(float(s) / divisor)
                except ValueError:
                    parsed.append(float("nan"))
                    if first_bad is None:
                        first_bad = (i, v)
            else:
                try:
                    parsed.append(float(v))
                except (TypeError, ValueError):
                    parsed.append(float("nan"))
                    if first_bad is None:
                        first_bad = (i, v)
        values = pd.Series(parsed, index=raw_values.index, dtype="float64")
        if first_bad is not None:
            i, v = first_bad
            raise ValueError(
                f"Non-numeric value found in column {value_col!r} "
                f"at row {i + 2}: {v!r}"
            )
    else:
        try:
            values = raw_values.astype("float64")
        except (TypeError, ValueError) as e:
            raise ValueError(
                f"Could not convert column {value_col!r} to numeric: {e}"
            ) from e

    # Build the series with a clean index.
    idx = pd.DatetimeIndex(dates).tz_localize(None).normalize()
    series = pd.Series(values.values, index=idx, name="returns")

    # Reject NaN values.
    nan_mask = series.isna()
    if nan_mask.any():
        n = int(nan_mask.sum())
        first = series[nan_mask].index[0].strftime("%Y-%m-%d")
        raise ValueError(
            f"Found {n} blank/NaN value(s); first at {first}. "
            f"Remove or fill before importing."
        )

    # Reject duplicate dates loudly.
    if series.index.has_duplicates:
        dups = series.index[series.index.duplicated()].unique()
        sample = ", ".join(d.strftime("%Y-%m-%d") for d in dups[:5])
        more = "..." if len(dups) > 5 else ""
        raise ValueError(f"Duplicate dates found: {sample}{more}")

    series = series.sort_index()

    if len(series) < 2:
        raise ValueError("Need at least two valid rows after parsing.")

    return series
