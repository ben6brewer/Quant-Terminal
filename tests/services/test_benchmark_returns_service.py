"""Tests for app.services.benchmark_returns_service.BenchmarkReturnsService."""

import pytest

from app.services.benchmark_returns_service import BenchmarkReturnsService


class TestCachePaths:
    def test_etf_cache_dir(self):
        path = BenchmarkReturnsService._get_etf_cache_dir("IWV")
        assert "IWV" in str(path)

    def test_ticker_cache_path(self):
        path = BenchmarkReturnsService._get_ticker_cache_path("IWV", "AAPL")
        assert "IWV" in str(path)
        assert "AAPL" in str(path)
        assert str(path).endswith(".parquet")

    def test_sanitizes_slashes(self):
        path = BenchmarkReturnsService._get_ticker_cache_path("IWV", "BRK/B")
        assert "/" not in path.name or "BRK_B" in str(path)


class TestIsCacheCurrent:
    def test_none_df(self):
        assert BenchmarkReturnsService._is_cache_current(None) is False

    def test_empty_df(self):
        import pandas as pd

        assert BenchmarkReturnsService._is_cache_current(pd.DataFrame()) is False


class TestCacheInfo:
    def test_nonexistent(self, tmp_path, monkeypatch):
        monkeypatch.setattr(BenchmarkReturnsService, "_CACHE_DIR", tmp_path / "benchmark")
        info = BenchmarkReturnsService.get_cache_info("NONEXISTENT")
        assert info["exists"] is False
        assert info["num_tickers"] == 0


class TestClearCache:
    def test_clear_all_no_error(self, tmp_path, monkeypatch):
        monkeypatch.setattr(BenchmarkReturnsService, "_CACHE_DIR", tmp_path / "benchmark")
        BenchmarkReturnsService._memory_cache.clear()
        BenchmarkReturnsService.clear_cache()  # Should not raise

    def test_clear_specific(self, tmp_path, monkeypatch):
        monkeypatch.setattr(BenchmarkReturnsService, "_CACHE_DIR", tmp_path / "benchmark")
        BenchmarkReturnsService._memory_cache.clear()
        BenchmarkReturnsService.clear_cache("IWV")
