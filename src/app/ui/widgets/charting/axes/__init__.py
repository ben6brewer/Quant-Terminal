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


# Monkeypatch pg.WidgetGroup.autoAdd to guard against QWidgetItem objects that
# lack a children() method in certain PySide6 versions (e.g. 6.10+).  Without
# this, PlotItem.__init__ can crash with AttributeError during addPlot().
from pyqtgraph.WidgetGroup import WidgetGroup as _WG

_orig_autoAdd = _WG.autoAdd


def _safe_autoAdd(self, obj):
    if not hasattr(obj, 'children'):
        return
    _orig_autoAdd(self, obj)


_WG.autoAdd = _safe_autoAdd


def _patch_axis_item():
    """No-op — patches are applied at import time above. Exists as an import target."""
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
