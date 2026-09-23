"""Fixtures for the FRED data-layer characterization tests (P0.T1).

``fred_env`` = ``fresh_home`` (a per-test home, so every FRED parquet cache
and the ``.fred_cache_version`` file land in a throw-away directory) +
``fake_fred`` (offline FakeFred) + the one-time cache-version check re-armed.

``probe_service`` builds a brand-new ``BaseFredService`` subclass per test so
class-level cooldown timestamps never leak between tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest


@dataclass
class FredEnv:
    home: Path
    ctl: object  # fixtures.fake_fred.FakeFredController

    @property
    def cache_dir(self) -> Path:
        import app.services.base_fred_service as base

        return base.CACHE_DIR

    @property
    def version_file(self) -> Path:
        import app.services.base_fred_service as base

        return base._FRED_VERSION_FILE

    def cache_file(self, name: str) -> Path:
        return self.cache_dir / name

    def write_current_version(self) -> None:
        """Mark the cache dir as current, so the version check will not wipe seeded files."""
        import app.services.base_fred_service as base

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.version_file.write_text(base._FRED_CACHE_VERSION)


@pytest.fixture
def fred_env(fresh_home, fake_fred, monkeypatch) -> FredEnv:
    import app.services.base_fred_service as base

    # Re-arm the one-time version check so it runs against the fresh home.
    monkeypatch.setattr(base, "_version_checked", False)
    env = FredEnv(home=fresh_home, ctl=fake_fred)
    assert env.cache_dir.is_relative_to(fresh_home), env.cache_dir
    return env


@pytest.fixture
def probe_service():
    """Factory: ``probe_service(groups=None, **attrs)`` -> fresh BaseFredService subclass."""
    from app.services.base_fred_service import BaseFredService

    made = []

    def make(groups=None, **attrs):
        ns = {"GROUPS": list(groups or []), "__module__": __name__, **attrs}
        cls = type(f"_QT_TEST_ProbeFredService{len(made)}", (BaseFredService,), ns)
        made.append(cls)
        return cls

    yield make
    made.clear()
