"""Characterization: PortfolioPersistence file round-trips (create/save/load/
rename/delete/recent ordering) and the PortfolioDataService read path.

Every test runs in its own ``fresh_home`` and only ever writes ``_QT_TEST_``
portfolio names.
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

import pytest

from app.services.portfolio_data_service import PortfolioDataService
from app.services.returns_data_service import ReturnsDataService
from app.ui.modules.portfolio_construction.services.portfolio_persistence import (
    PortfolioPersistence,
)
from app.ui.modules.portfolio_construction.services.portfolio_service import (
    PortfolioService,
)

from ._helpers import CUSTOM_NAME, PREFIX, sample_ledger

NAME = f"{PREFIX}portfolio"
OTHER = f"{PREFIX}portfolio_renamed"


@pytest.fixture
def pdir(fresh_home):
    """``~/.quant_terminal/portfolios`` inside this test's fresh home.

    The on-disk layout is part of the contract (existing user data lives there):
    one ``<name>.json`` per portfolio plus ``~/.quant_terminal/recent_portfolios.json``.
    """
    return fresh_home / ".quant_terminal" / "portfolios"


def _recent_file():
    return Path.home() / ".quant_terminal" / "recent_portfolios.json"


def _read(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _visit_in_order(*names):
    """record_visit with a gap so the ISO timestamps are strictly increasing."""
    for n in names:
        PortfolioPersistence.record_visit(n)
        time.sleep(0.02)


# ─────────────────────────────────────────────────────────────────────────────
# create / save / load
# ─────────────────────────────────────────────────────────────────────────────


class TestCreateSaveLoad:
    def test_create_new_portfolio_shapes_are_not_persisted(self, pdir):
        tx_p = PortfolioPersistence.create_new_portfolio(NAME)
        assert set(tx_p) == {"name", "created_date", "last_modified", "transactions"}
        assert tx_p["name"] == NAME and tx_p["transactions"] == []
        assert tx_p["created_date"] == tx_p["last_modified"]
        datetime.fromisoformat(tx_p["created_date"])

        w_p = PortfolioPersistence.create_new_portfolio(NAME, "weights")
        assert set(w_p) == {"name", "type", "created_date", "last_modified", "weights"}
        assert w_p["type"] == "weights" and w_p["weights"] == {}

        # Any other type string falls back to a transaction portfolio.
        assert "transactions" in PortfolioPersistence.create_new_portfolio(NAME, "_QT_TEST_bogus")
        assert PortfolioPersistence.portfolio_exists(NAME) is False
        assert PortfolioPersistence.list_portfolios() == []

    def test_list_portfolios_without_directory(self, pdir):
        assert not pdir.exists()
        assert PortfolioPersistence.list_portfolios() == []
        assert PortfolioPersistence.list_portfolios_by_recent() == []
        PortfolioPersistence.initialize()
        assert pdir.is_dir()

    def test_transaction_portfolio_roundtrip(self, pdir):
        p = PortfolioPersistence.create_new_portfolio(NAME)
        p["transactions"] = sample_ledger()
        p["transactions"][1]["notes"] = "café ✓ note"
        created = p["created_date"]

        assert PortfolioPersistence.save_portfolio(p) is True
        path = pdir / f"{NAME}.json"
        assert path.is_file()
        assert PortfolioPersistence.portfolio_exists(NAME) is True
        assert PortfolioPersistence.list_portfolios() == [NAME]

        # save_portfolio stamps last_modified on the dict it was given.
        assert datetime.fromisoformat(p["last_modified"]) >= datetime.fromisoformat(created)
        on_disk = _read(path)
        assert on_disk == p
        # Non-ASCII survives verbatim (ensure_ascii=False).
        assert "café ✓ note" in path.read_text(encoding="utf-8")

        loaded = PortfolioPersistence.load_portfolio(NAME)
        assert loaded == p
        assert [t["id"] for t in loaded["transactions"]] == [f"t0{i}" for i in range(1, 9)]
        assert loaded["created_date"] == created

    def test_weights_portfolio_roundtrip_keeps_custom_keys(self, pdir):
        p = PortfolioPersistence.create_new_portfolio(NAME, "weights")
        p["weights"] = {"AAPL": 0.5, "SPY": 0.3, f"[Custom] {CUSTOM_NAME}": 0.2}
        assert PortfolioPersistence.save_portfolio(p)
        before = (pdir / f"{NAME}.json").read_bytes()

        loaded = PortfolioPersistence.load_portfolio(NAME)
        assert loaded["type"] == "weights"
        assert loaded["weights"] == {"AAPL": 0.5, "SPY": 0.3, f"[Custom] {CUSTOM_NAME}": 0.2}
        assert list(loaded["weights"]) == ["AAPL", "SPY", f"[Custom] {CUSTOM_NAME}"]
        # No migration for weights portfolios -> load does not rewrite the file.
        assert (pdir / f"{NAME}.json").read_bytes() == before

    def test_load_missing_and_corrupt(self, pdir, capsys):
        assert PortfolioPersistence.load_portfolio(f"{PREFIX}missing") is None
        pdir.mkdir(parents=True)
        (pdir / f"{PREFIX}corrupt.json").write_text("{not json", encoding="utf-8")
        assert PortfolioPersistence.load_portfolio(f"{PREFIX}corrupt") is None
        assert f"Error loading portfolio {PREFIX}corrupt" in capsys.readouterr().out
        # A corrupt file is still listed (list is a pure glob).
        assert PortfolioPersistence.list_portfolios() == [f"{PREFIX}corrupt"]

    def test_load_migrates_missing_sequence_and_autosaves(self, pdir):
        """Legacy files without ``sequence`` get the array position and are re-saved."""
        pdir.mkdir(parents=True)
        legacy = {
            "name": NAME,
            "created_date": "2024-01-01T00:00:00",
            "last_modified": "2024-01-01T00:00:00",
            "transactions": [
                {"id": "a", "date": "2024-01-02", "ticker": "FREE CASH", "transaction_type": "Buy",
                 "quantity": 1000.0, "entry_price": 1.0, "fees": 0.0},
                {"id": "b", "date": "2024-01-03", "ticker": "AAPL", "transaction_type": "Buy",
                 "quantity": 1.0, "entry_price": 100.0, "fees": 0.0, "sequence": 7},
                {"id": "c", "date": "2024-01-03", "ticker": "SPY", "transaction_type": "Buy",
                 "quantity": 1.0, "entry_price": 100.0, "fees": 0.0},
            ],
        }
        path = pdir / f"{NAME}.json"
        path.write_text(json.dumps(legacy), encoding="utf-8")

        loaded = PortfolioPersistence.load_portfolio(NAME)
        assert [t["sequence"] for t in loaded["transactions"]] == [0, 7, 2]
        assert loaded["last_modified"] != "2024-01-01T00:00:00"
        on_disk = _read(path)
        assert [t["sequence"] for t in on_disk["transactions"]] == [0, 7, 2]
        assert on_disk["created_date"] == "2024-01-01T00:00:00"
        assert on_disk["last_modified"] == loaded["last_modified"]

        # Already-migrated files are not re-saved on the next load.
        before = path.read_bytes()
        assert PortfolioPersistence.load_portfolio(NAME) == loaded
        assert path.read_bytes() == before

    def test_names_with_spaces_and_unicode(self, pdir):
        name = f"{PREFIX}My Portfolio é"
        assert PortfolioPersistence.save_portfolio(PortfolioPersistence.create_new_portfolio(name))
        assert (pdir / f"{name}.json").is_file()
        assert PortfolioPersistence.list_portfolios() == [name]
        assert PortfolioPersistence.load_portfolio(name)["name"] == name

    def test_save_invalidates_returns_cache(self, pdir, monkeypatch):
        """Saving a portfolio drops its ReturnsDataService memory + parquet cache."""
        monkeypatch.setattr(ReturnsDataService, "_memory_cache", {NAME: "stale", OTHER: "keep"})
        cache_file = pdir.parent / "cache" / "returns" / f"{NAME}_returns.parquet"
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_bytes(b"stale parquet")

        assert PortfolioPersistence.save_portfolio(PortfolioPersistence.create_new_portfolio(NAME))
        assert NAME not in ReturnsDataService._memory_cache
        assert ReturnsDataService._memory_cache == {OTHER: "keep"}
        assert not cache_file.exists()


# ─────────────────────────────────────────────────────────────────────────────
# rename / delete / clear
# ─────────────────────────────────────────────────────────────────────────────


class TestRenameDelete:
    def _save(self, name, ledger=True):
        p = PortfolioPersistence.create_new_portfolio(name)
        if ledger:
            p["transactions"] = sample_ledger()
        assert PortfolioPersistence.save_portfolio(p)
        return p

    def test_rename_moves_file_and_recent_entry(self, pdir):
        original = self._save(NAME)
        _visit_in_order(NAME)
        recent_before = _read(_recent_file())

        assert PortfolioPersistence.rename_portfolio(NAME, OTHER) is True
        assert not (pdir / f"{NAME}.json").exists()
        renamed = PortfolioPersistence.load_portfolio(OTHER)
        assert renamed["name"] == OTHER
        assert renamed["transactions"] == original["transactions"]
        assert renamed["created_date"] == original["created_date"]
        assert datetime.fromisoformat(renamed["last_modified"]) >= datetime.fromisoformat(
            original["last_modified"])
        assert PortfolioPersistence.list_portfolios() == [OTHER]

        recent_after = _read(_recent_file())
        assert recent_after == {OTHER: recent_before[NAME]}

    def test_rename_edge_cases(self, pdir):
        self._save(NAME)
        self._save(OTHER, ledger=False)
        a_before = (pdir / f"{NAME}.json").read_bytes()
        b_before = (pdir / f"{OTHER}.json").read_bytes()

        assert PortfolioPersistence.rename_portfolio(NAME, NAME) is True  # no-op
        assert PortfolioPersistence.rename_portfolio(NAME, OTHER) is False  # target exists
        assert PortfolioPersistence.rename_portfolio(f"{PREFIX}missing", f"{PREFIX}x") is False
        assert (pdir / f"{NAME}.json").read_bytes() == a_before
        assert (pdir / f"{OTHER}.json").read_bytes() == b_before
        assert not (pdir / f"{PREFIX}x.json").exists()

    def test_delete_keeps_recent_entry_until_removed(self, pdir):
        self._save(NAME)
        self._save(OTHER)
        _visit_in_order(NAME, OTHER)

        assert PortfolioPersistence.delete_portfolio(NAME) is True
        assert not (pdir / f"{NAME}.json").exists()
        assert PortfolioPersistence.delete_portfolio(NAME) is False
        assert PortfolioPersistence.load_portfolio(NAME) is None
        # delete_portfolio does not touch recent visits ...
        assert set(_read(_recent_file())) == {NAME, OTHER}
        # ... but the recent listing is driven by the files that exist.
        assert PortfolioPersistence.list_portfolios_by_recent() == [OTHER]
        PortfolioPersistence.remove_from_recent(NAME)
        assert set(_read(_recent_file())) == {OTHER}
        PortfolioPersistence.remove_from_recent(f"{PREFIX}never_visited")  # no-op
        assert set(_read(_recent_file())) == {OTHER}

    def test_clear_all(self, pdir):
        self._save(NAME)
        self._save(OTHER)
        _visit_in_order(NAME)
        (pdir / f"{PREFIX}notes.txt").write_text("not a portfolio", encoding="utf-8")

        PortfolioPersistence.clear_all()
        assert PortfolioPersistence.list_portfolios() == []
        assert not _recent_file().exists()
        # Only *.json files are removed.
        assert (pdir / f"{PREFIX}notes.txt").exists()
        PortfolioPersistence.clear_all()  # idempotent


# ─────────────────────────────────────────────────────────────────────────────
# recent ordering
# ─────────────────────────────────────────────────────────────────────────────


class TestRecentOrdering:
    NAMES = [f"{PREFIX}charlie", f"{PREFIX}Bravo", f"{PREFIX}alpha", f"{PREFIX}delta"]

    def _create_all(self):
        for n in self.NAMES:
            assert PortfolioPersistence.save_portfolio(PortfolioPersistence.create_new_portfolio(n))

    def test_unvisited_sorted_case_insensitively(self, pdir):
        self._create_all()
        assert PortfolioPersistence.list_portfolios_by_recent() == [
            f"{PREFIX}alpha", f"{PREFIX}Bravo", f"{PREFIX}charlie", f"{PREFIX}delta"]
        assert PortfolioDataService.list_portfolios_by_recent() == PortfolioPersistence.list_portfolios_by_recent()

    def test_visited_first_most_recent_first(self, pdir):
        self._create_all()
        _visit_in_order(f"{PREFIX}delta", f"{PREFIX}Bravo")
        assert PortfolioPersistence.list_portfolios_by_recent() == [
            f"{PREFIX}Bravo", f"{PREFIX}delta", f"{PREFIX}alpha", f"{PREFIX}charlie"]
        _visit_in_order(f"{PREFIX}delta")
        assert PortfolioPersistence.list_portfolios_by_recent()[:2] == [f"{PREFIX}delta", f"{PREFIX}Bravo"]

        recent = _read(_recent_file())
        assert set(recent) == {f"{PREFIX}delta", f"{PREFIX}Bravo"}
        for ts in recent.values():
            datetime.fromisoformat(ts)

    def test_invalid_timestamp_and_unknown_entries(self, pdir):
        self._create_all()
        _visit_in_order(f"{PREFIX}charlie")
        recent = _read(_recent_file())
        recent[f"{PREFIX}alpha"] = "not-a-timestamp"
        recent[f"{PREFIX}ghost"] = "2020-01-01T00:00:00"  # no such portfolio file
        _recent_file().write_text(json.dumps(recent), encoding="utf-8")

        # Invalid timestamps rank with the unvisited (alphabetical) group; ghosts are ignored.
        assert PortfolioPersistence.list_portfolios_by_recent() == [
            f"{PREFIX}charlie", f"{PREFIX}alpha", f"{PREFIX}Bravo", f"{PREFIX}delta"]

    def test_corrupt_recent_file_is_ignored_and_rewritten(self, pdir):
        self._create_all()
        _recent_file().parent.mkdir(parents=True, exist_ok=True)
        _recent_file().write_text("[broken", encoding="utf-8")
        assert PortfolioPersistence.list_portfolios_by_recent()[0] == f"{PREFIX}alpha"
        PortfolioPersistence.record_visit(f"{PREFIX}delta")
        assert set(_read(_recent_file())) == {f"{PREFIX}delta"}


# ─────────────────────────────────────────────────────────────────────────────
# PortfolioService transactions -> persistence -> PortfolioDataService read path
# ─────────────────────────────────────────────────────────────────────────────


class TestServiceRoundtrip:
    def test_created_transactions_roundtrip_through_data_service(self, pdir):
        p = PortfolioPersistence.create_new_portfolio(NAME)
        p["transactions"] = [
            PortfolioService.create_transaction("2024-01-02", "free cash", "Buy", 10000, 1.0),
            PortfolioService.create_transaction("2024-01-03", " aapl ", "Buy", 10, 185.5, fees=1,
                                                notes="  first lot  ", sequence=0),
            PortfolioService.create_transaction("2024-01-03", "spy", "Buy", "5", "470", sequence=1),
            PortfolioService.create_transaction("2024-02-01", "AAPL", "Sell", 4, 190.0, sequence=0),
        ]
        assert PortfolioPersistence.save_portfolio(p)

        raw = PortfolioPersistence.load_portfolio(NAME)
        assert [t["ticker"] for t in raw["transactions"]] == ["FREE CASH", "AAPL", "SPY", "AAPL"]
        assert raw["transactions"][1]["notes"] == "first lot"
        assert raw["transactions"][2]["quantity"] == 5.0 and raw["transactions"][2]["entry_price"] == 470.0
        assert len({t["id"] for t in raw["transactions"]}) == 4

        data = PortfolioDataService.get_portfolio(NAME)
        assert data.name == NAME
        assert data.created_date == p["created_date"]
        assert len(data.transactions) == 4
        assert sorted(PortfolioDataService.get_tickers(NAME)) == ["AAPL", "SPY"]
        assert PortfolioDataService.is_weights_portfolio(NAME) is False
        assert PortfolioDataService.get_weights(NAME) is None
        assert PortfolioDataService.portfolio_exists(NAME) is True
        assert PortfolioDataService.list_portfolios() == [NAME]

        holdings = PortfolioDataService.get_holdings(NAME, {"AAPL": 200.0, "SPY": 500.0})
        by_ticker = {h.ticker: h for h in holdings}
        assert set(by_ticker) == {"AAPL", "SPY"}
        assert by_ticker["AAPL"].quantity == pytest.approx(6.0)
        assert by_ticker["AAPL"].market_value == pytest.approx(1200.0)
        assert by_ticker["AAPL"].weight + by_ticker["SPY"].weight == pytest.approx(1.0)

    def test_weights_portfolio_through_data_service(self, pdir):
        p = PortfolioPersistence.create_new_portfolio(NAME, "weights")
        p["weights"] = {"AAPL": 0.6, "SPY": 0.4}
        assert PortfolioPersistence.save_portfolio(p)
        assert PortfolioDataService.is_weights_portfolio(NAME) is True
        assert PortfolioDataService.get_weights(NAME) == {"AAPL": 0.6, "SPY": 0.4}
        assert PortfolioDataService.get_tickers(NAME) == ["AAPL", "SPY"]
        holdings = PortfolioDataService.get_holdings(NAME, {"AAPL": 1.0})
        assert [(h.ticker, h.weight, h.current_price, h.quantity) for h in holdings] == [
            ("AAPL", 0.6, 1.0, 0), ("SPY", 0.4, None, 0)]
        assert PortfolioDataService.get_portfolio(NAME).transactions == []

    def test_missing_portfolio_through_data_service(self, pdir):
        missing = f"{PREFIX}missing"
        assert PortfolioDataService.get_portfolio(missing) is None
        assert PortfolioDataService.get_transactions(missing) == []
        assert PortfolioDataService.get_holdings(missing) == []
        assert PortfolioDataService.get_tickers(missing) == []
        assert PortfolioDataService.is_weights_portfolio(missing) is False
