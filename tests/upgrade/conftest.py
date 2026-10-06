"""Fixtures for the legacy-home upgrade tests (``tests/upgrade/``).

* ``legacy_expected`` - parsed ``tests/fixtures/legacy_home_v0_2/expected.json``
  (what the v0.2 user chose; written by ``make_legacy_home_v0_2.py``).
* ``legacy_home``     - a per-test ``fresh_home`` holding a COPY of the v0.2
  ``.quant_terminal`` tree, with the class-level in-memory state of every
  store under test reset, so the current code really loads from disk.
  Yields the ``<home>/.quant_terminal`` path.
* ``upgrade_golden``  - ``golden_utils.assert_golden`` bound to area
  ``legacy_home_v0_2`` whose files live in this slice's own directory
  (``tests/upgrade/goldens/legacy_home_v0_2/``).  ``--update-goldens`` works
  as usual.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

UPGRADE_DIR = Path(__file__).resolve().parent
FIXTURE_DIR = UPGRADE_DIR.parent / "fixtures" / "legacy_home_v0_2"
LEGACY_TREE = FIXTURE_DIR / ".quant_terminal"
EXPECTED_FILE = FIXTURE_DIR / "expected.json"
GOLDENS_DIR = UPGRADE_DIR / "goldens"
GOLDEN_AREA = "legacy_home_v0_2"


def load_expected() -> dict:
    return json.loads(EXPECTED_FILE.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def legacy_expected() -> dict:
    return load_expected()


def _reset_in_memory_state(monkeypatch) -> None:
    """Forget whatever earlier tests left in class/module level caches."""
    from app.services import base_fred_service, market_data
    from app.services.favorites_service import FavoritesService
    from app.services.preferences_service import PreferencesService
    from app.ui.modules.chart.services.indicator_service import IndicatorService
    from app.ui.modules.housing.services.housing_fred_service import HousingFredService
    from app.ui.modules.recession.services.recession_fred_service import RecessionFredService
    from app.ui.modules.risk_analytics.services.sector_override_service import SectorOverrideService
    from app.ui.modules.unemployment_age.services.unemployment_age_service import UnemploymentAgeService

    monkeypatch.setattr(FavoritesService, "_favorites", set())
    monkeypatch.setattr(PreferencesService, "_preferences", {})
    monkeypatch.setattr(SectorOverrideService, "_overrides", None)

    monkeypatch.setattr(IndicatorService, "_initialized", False)
    for attr in ("OVERLAY_INDICATORS", "OSCILLATOR_INDICATORS", "ALL_INDICATORS",
                 "CUSTOM_INDICATOR_CLASSES", "PLUGIN_APPEARANCE_OVERRIDES"):
        monkeypatch.setattr(IndicatorService, attr, {})

    monkeypatch.setattr(market_data, "_memory_cache", {})
    monkeypatch.setattr(market_data, "_live_bar_cache", {})

    monkeypatch.setattr(base_fred_service, "_version_checked", False)
    monkeypatch.setattr(HousingFredService, "_last_housing_fetch", None)
    monkeypatch.setattr(RecessionFredService, "_last_monthly_fetch", None)
    monkeypatch.setattr(UnemploymentAgeService, "_last_group_0_fetch", None, raising=False)


@pytest.fixture
def legacy_home(fresh_home, monkeypatch) -> Path:
    """``<fresh home>/.quant_terminal`` populated from the v0.2 fixture."""
    target = fresh_home / ".quant_terminal"
    shutil.copytree(LEGACY_TREE, target)
    _reset_in_memory_state(monkeypatch)
    yield target


@pytest.fixture
def upgrade_golden():
    """``assert_golden(name, data, **kw)`` for area ``legacy_home_v0_2`` (goldens in tests/upgrade/)."""
    import golden_utils

    def check(name: str, data, **kwargs) -> None:
        golden_utils.assert_golden(name, data, area=GOLDEN_AREA, goldens_dir=GOLDENS_DIR, **kwargs)

    return check
