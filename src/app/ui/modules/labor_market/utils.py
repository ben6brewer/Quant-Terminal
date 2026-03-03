"""Shared utilities for labor market chart modules."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd


def add_recession_bands(plot_item, usrec_series: "pd.Series", date_index: "pd.DatetimeIndex") -> list:
    """Add NBER recession shading to a plot_item. Returns list of added items."""
    import pyqtgraph as pg

    if usrec_series is None or usrec_series.empty or date_index is None or len(date_index) == 0:
        return []

    try:
        aligned = usrec_series.reindex(date_index, method="ffill").fillna(0)
        rec = aligned.values.astype(bool)
    except Exception:
        return []

    bands = []
    n = len(rec)
    i = 0
    while i < n:
        if rec[i]:
            start_idx = i
            while i < n and rec[i]:
                i += 1
            end_idx = i
            region = pg.LinearRegionItem(
                values=[start_idx - 0.5, end_idx - 0.5],
                orientation="vertical",
                movable=False,
                brush=pg.mkBrush(128, 128, 128, 45),
                pen=pg.mkPen(None),
            )
            region.setZValue(-10)
            plot_item.addItem(region)
            bands.append(region)
        else:
            i += 1

    return bands
