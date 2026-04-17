"""Direct downloader for Ken French Data Library factor zips.

Replaces ``pandas_datareader.famafrench`` (which broke on pandas 3.x).
Each dataset URL is the canonical Ken French ZIP and contains a single
CSV with a few descriptive header lines, followed by the time-series
table, optionally followed by an annual-aggregates table.

Public entry: :func:`fetch_ff_dataset(dataset_name)` returns a
``pandas.DataFrame`` indexed by ``DatetimeIndex`` with the raw factor
values (still in percent — caller is responsible for /100 if desired).
"""

from __future__ import annotations

import io
import re
import zipfile
from typing import TYPE_CHECKING, Optional
from urllib.request import Request, urlopen

if TYPE_CHECKING:
    import pandas as pd


_BASE_URL = (
    "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
)


def _zip_url(dataset_name: str) -> str:
    """Map a Ken French dataset name to its ``_CSV.zip`` download URL."""
    return f"{_BASE_URL}{dataset_name}_CSV.zip"


def _download_zip_bytes(url: str, timeout: float = 30.0) -> bytes:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=timeout) as resp:  # nosec B310 — fixed Dartmouth host
        return resp.read()


def _extract_single_csv(zip_bytes: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        members = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        if not members:
            raise ValueError("No CSV inside Ken French zip")
        with zf.open(members[0]) as f:
            return f.read().decode("latin-1")


# Date column at start of a row: YYYYMM (6 digits) or YYYYMMDD (8 digits)
_DATA_ROW = re.compile(r"^\s*(\d{6,8})\s*,(.+)$")


def _parse_csv_to_frame(
    csv_text: str, start: Optional[str] = None
) -> "pd.DataFrame":
    """Parse a Ken French CSV string into a DataFrame.

    The CSV typically has a few preamble lines, then a header row whose
    first cell is blank (``,Mkt-RF,SMB,...``), then data rows whose
    first cell is a numeric date (YYYYMM or YYYYMMDD), and optionally an
    annual-aggregates table after a blank line / divider. We capture
    only the first contiguous block of rows whose date matches.
    """
    import pandas as pd

    lines = csv_text.splitlines()

    # Find header row — the first row that begins with a comma (its
    # first column is blank, the rest are factor names).
    header_idx = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(","):
            header_idx = i
            break

    if header_idx is None:
        raise ValueError("Could not locate header row in Ken French CSV")

    header_cells = [c.strip() for c in lines[header_idx].split(",")]
    # Drop the leading empty cell (it corresponds to the date column).
    factor_cols = [c for c in header_cells[1:] if c]

    # Walk forward collecting consecutive data rows.
    date_strs: list[str] = []
    rows: list[list[float]] = []
    for line in lines[header_idx + 1:]:
        stripped = line.strip()
        if not stripped:
            # Blank line marks end of the time-series block.
            if date_strs:
                break
            continue
        m = _DATA_ROW.match(stripped)
        if not m:
            # Non-numeric leading cell → we've hit the annual-aggregates
            # section or a footer. Stop.
            if date_strs:
                break
            continue
        date_str, rest = m.group(1), m.group(2)
        cells = [c.strip() for c in rest.split(",")]
        try:
            values = [float(c) for c in cells[: len(factor_cols)]]
        except ValueError:
            # Malformed row — skip silently.
            continue
        # Pad with NaN if the row is short.
        while len(values) < len(factor_cols):
            values.append(float("nan"))
        date_strs.append(date_str)
        rows.append(values)

    if not date_strs:
        raise ValueError("No data rows parsed from Ken French CSV")

    # Date format: 6 digits → monthly (YYYYMM), 8 digits → daily (YYYYMMDD).
    sample = date_strs[0]
    if len(sample) == 6:
        idx = pd.to_datetime(date_strs, format="%Y%m")
    elif len(sample) == 8:
        idx = pd.to_datetime(date_strs, format="%Y%m%d")
    else:
        idx = pd.to_datetime(date_strs)

    df = pd.DataFrame(rows, index=idx, columns=factor_cols)
    df.index.name = "Date"

    if start is not None:
        df = df.loc[df.index >= pd.Timestamp(start)]

    return df


def fetch_ff_dataset(
    dataset_name: str, start: Optional[str] = None
) -> "pd.DataFrame":
    """Download a Ken French dataset zip and return its primary table.

    Args:
        dataset_name: e.g. ``"F-F_Research_Data_5_Factors_2x3"`` or
            ``"F-F_Momentum_Factor_daily"``. Do NOT include ``_CSV.zip``.
        start: Optional ISO date string to filter the returned frame.

    Returns:
        DataFrame indexed by DatetimeIndex, columns = factor names,
        values in percentage form (Ken French convention). Caller is
        responsible for any /100 scaling.

    Raises:
        ValueError: if the file is empty or unparseable.
        URLError: if the network is unreachable.
    """
    url = _zip_url(dataset_name)
    blob = _download_zip_bytes(url)
    csv_text = _extract_single_csv(blob)
    return _parse_csv_to_frame(csv_text, start=start)
