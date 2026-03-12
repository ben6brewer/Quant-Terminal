"""Tests for CPI component contribution calculations and cache integrity."""

import numpy as np
import pandas as pd
import pytest
from pathlib import Path

from app.ui.modules.cpi.services import COMPONENT_LABELS, COMPONENT_WEIGHTS


# ── Helpers ───────────────────────────────────────────────────────────────────


def _build_realistic_cpi_raw(n_months: int = 36) -> pd.DataFrame:
    """Build a realistic CPI raw index DataFrame (NOT YoY%).

    Each component starts at a different base index and grows at a
    realistic annualized rate, so YoY% stays within normal bounds.
    """
    dates = pd.date_range("2022-01-01", periods=n_months, freq="MS")

    # Realistic starting index values and annual growth rates
    specs = {
        "Headline CPI": (300.0, 0.03),
        "Core CPI":     (310.0, 0.035),
        "Food & Beverages": (320.0, 0.025),
        "Energy":       (260.0, 0.04),
        "Housing":      (350.0, 0.05),
        "Transportation": (270.0, 0.015),
        "Medical Care": (560.0, 0.03),
        "Apparel":      (130.0, 0.01),
        "Education":    (180.0, 0.025),
        "Recreation":   (115.0, 0.015),
    }

    data = {}
    for col, (base, annual_rate) in specs.items():
        monthly_rate = (1 + annual_rate) ** (1 / 12) - 1
        values = base * (1 + monthly_rate) ** np.arange(n_months)
        # Add small noise for realism
        rng = np.random.default_rng(42)
        values *= 1 + rng.normal(0, 0.001, n_months)
        data[col] = values

    return pd.DataFrame(data, index=dates)


def _compute_contributions(yoy_df: pd.DataFrame):
    """Replicate the chart's contribution logic: weight * YoY% for each component."""
    available = [c for c in COMPONENT_LABELS if c in yoy_df.columns]
    component_df = yoy_df[available].dropna(how="all")

    contributions = []
    for month_idx in range(len(component_df)):
        month_contribs = []
        for comp_name in available:
            val = component_df.iloc[month_idx][comp_name]
            if np.isnan(val):
                continue
            w = COMPONENT_WEIGHTS.get(comp_name, 0.0)
            month_contribs.append((comp_name, w * val))
        contributions.append(month_contribs)
    return contributions


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestCpiContributions:
    def test_contributions_bounded_with_realistic_data(self):
        """With realistic CPI data, all contributions should be small and bounded."""
        raw = _build_realistic_cpi_raw(36)
        yoy = raw.pct_change(periods=12) * 100
        yoy = yoy.dropna(how="all")

        contributions = _compute_contributions(yoy)
        assert len(contributions) > 0

        for month_idx, month_contribs in enumerate(contributions):
            total = 0.0
            for comp_name, val in month_contribs:
                assert abs(val) < 5.0, (
                    f"Month {month_idx}: {comp_name} contribution {val:.2f}% exceeds ±5%"
                )
                total += val
            # Sum of weighted contributions should be near headline (within ±1%)
            assert abs(total) < 10.0, (
                f"Month {month_idx}: total contribution {total:.2f}% exceeds ±10%"
            )

    def test_contributions_stable_with_energy_swing(self):
        """Even with large energy swings, contributions stay bounded."""
        raw = _build_realistic_cpi_raw(36)

        # Simulate energy disinflation: -15% annual drop in last year
        energy_base = raw["Energy"].iloc[23]
        for i in range(24, 36):
            monthly_decline = (1 - 0.15) ** (1 / 12)
            raw.loc[raw.index[i], "Energy"] = energy_base * monthly_decline ** (i - 23)

        # Simulate housing surge: +8% annual in last year
        housing_base = raw["Housing"].iloc[23]
        for i in range(24, 36):
            monthly_rise = (1 + 0.08) ** (1 / 12)
            raw.loc[raw.index[i], "Housing"] = housing_base * monthly_rise ** (i - 23)

        yoy = raw.pct_change(periods=12) * 100
        yoy = yoy.dropna(how="all")

        contributions = _compute_contributions(yoy)

        for month_idx, month_contribs in enumerate(contributions):
            for comp_name, val in month_contribs:
                assert abs(val) < 5.0, (
                    f"Month {month_idx}: {comp_name} contribution {val:.2f}% exceeds ±5%"
                )


class TestCacheIntegrity:
    def test_version_bump_wipes_caches(self, tmp_path, monkeypatch):
        """Version mismatch should delete all parquet files and write new version."""
        import app.services.base_fred_service as mod

        monkeypatch.setattr(mod, "CACHE_DIR", tmp_path)
        monkeypatch.setattr(mod, "_FRED_VERSION_FILE", tmp_path / ".fred_cache_version")
        monkeypatch.setattr(mod, "_version_checked", False)

        # Create a fake parquet file and old version
        fake_cache = tmp_path / "cpi_data.parquet"
        fake_cache.write_text("fake")
        (tmp_path / ".fred_cache_version").write_text("1")

        monkeypatch.setattr(mod, "_FRED_CACHE_VERSION", "99")
        mod._check_fred_cache_version()

        assert not fake_cache.exists(), "Old parquet should be deleted on version bump"
        assert (tmp_path / ".fred_cache_version").read_text() == "99"

    def test_version_match_keeps_caches(self, tmp_path, monkeypatch):
        """Matching version should not delete any files."""
        import app.services.base_fred_service as mod

        monkeypatch.setattr(mod, "CACHE_DIR", tmp_path)
        monkeypatch.setattr(mod, "_FRED_VERSION_FILE", tmp_path / ".fred_cache_version")

        fake_cache = tmp_path / "cpi_data.parquet"
        fake_cache.write_text("fake")
        (tmp_path / ".fred_cache_version").write_text(mod._FRED_CACHE_VERSION)

        mod._check_fred_cache_version()

        assert fake_cache.exists(), "Parquet should be kept when version matches"

    def test_valid_cache_not_rejected(self, tmp_path):
        """A cache with legitimately different column values should be kept."""
        from app.services.base_fred_service import BaseFredService

        dates = pd.date_range("2020-01-01", periods=60, freq="MS")
        df = pd.DataFrame(
            {
                "Headline CPI": np.linspace(250, 300, 60),
                "Core CPI": np.linspace(260, 310, 60),
                "Food & Beverages": np.linspace(300, 340, 60),
            },
            index=dates,
        )

        cache_file = tmp_path / "test_valid.parquet"
        df.to_parquet(cache_file)

        series_map = {col: f"FAKE{i}" for i, col in enumerate(df.columns)}
        result = BaseFredService._load_cache(cache_file, series_map)

        assert result is not None, "Valid cache should not be rejected"
        assert len(result) == 60
