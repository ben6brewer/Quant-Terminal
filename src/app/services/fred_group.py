"""FredGroup / FredOutput — Declarative config for FRED service data groups."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class FredOutput:
    """Describes one output DataFrame to extract from a fetched group."""

    key: str                              # Result dict key, e.g. "energy"
    columns: List[str]                    # Columns to include from the fetched group
    unit_scale: Optional[float] = None    # Multiply values (e.g. 1/1_000_000)


@dataclass
class FredGroup:
    """Describes one cache group of FRED series to fetch together."""

    series: Dict[str, str]                # {friendly_name: FRED_series_id}
    cache_file: str                       # Filename under ~/.quant_terminal/cache/fred/
    max_age_days: int = 45
    outputs: List[FredOutput] = field(default_factory=list)
