"""Chart axis components - draggable axes with custom formatting."""

import pyqtgraph as pg

# Monkeypatch pg.AxisItem.generateDrawSpecs to guard against NoneType tick
# positions. pyqtgraph crashes with TypeError when tickPositions contain None
# (happens during init/clear when the view range is undefined). This patch
# runs once at import time and protects ALL AxisItem instances globally.
_orig_generateDrawSpecs = pg.AxisItem.generateDrawSpecs


def _safe_generateDrawSpecs(self, p):
    try:
        return _orig_generateDrawSpecs(self, p)
    except (TypeError, ValueError):
        return None


pg.AxisItem.generateDrawSpecs = _safe_generateDrawSpecs


def _patch_axis_item():
    """No-op — patch is applied at import time above. Exists as an import target."""
    pass


from .draggable_axis import DraggableAxisItem
from .price_axis import DraggablePriceAxisItem
from .date_index_axis import DraggableIndexDateAxisItem
from .percentage_axis import DraggablePercentageAxisItem
from .trading_day_axis import DraggableTradingDayAxisItem
from .volume_axis import VolumeAxisItem

__all__ = [
    'DraggableAxisItem',
    'DraggablePriceAxisItem',
    'DraggableIndexDateAxisItem',
    'DraggablePercentageAxisItem',
    'DraggableTradingDayAxisItem',
    'VolumeAxisItem',
    '_patch_axis_item',
]
