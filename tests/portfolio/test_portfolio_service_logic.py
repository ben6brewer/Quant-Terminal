"""Characterization: PortfolioService pure business logic (no prices fetched).

Holdings / cash / validation numbers are hand-checked against the ledger in
``_helpers.sample_ledger`` and additionally pinned by goldens.
"""

from __future__ import annotations

import copy
import re
import uuid
from datetime import datetime

import pytest

from golden_utils import assert_golden

from app.ui.modules.portfolio_construction.services.portfolio_service import (
    PortfolioService,
)

from ._helpers import PREFIX, sample_ledger, tx

PS = PortfolioService
PRICES = {"AAPL": 200.0, "SPY": 500.0, "MSFT": None}


def _by_id(ledger, tx_id):
    return next(t for t in ledger if t["id"] == tx_id)


class TestTickerAndTransactionBasics:
    @pytest.mark.parametrize("raw, expected", [
        (" aapl ", "AAPL"),
        ("brk-b", "BRK-B"),
        ("free cash", "FREE CASH"),
        ("", ""),
        (None, ""),
        ("[Custom] _QT_TEST_unknown ", "[Custom] _QT_TEST_unknown"),  # unresolved: stripped raw
        ("  [custom] _qt_test_unknown", "[custom] _qt_test_unknown"),
    ])
    def test_normalize_ticker(self, fresh_home, raw, expected):
        assert PS.normalize_ticker(raw) == expected

    def test_free_cash_constant(self):
        assert PS.FREE_CASH_TICKER == "FREE CASH"

    def test_create_transaction(self, fresh_home):
        t = PS.create_transaction("2024-01-03", " aapl ", "Buy", "10", 185, fees="1.5",
                                  notes="  lot 1 ", sequence=3)
        assert set(t) == {"id", "date", "ticker", "transaction_type", "quantity", "entry_price",
                          "fees", "notes", "sequence"}
        uuid.UUID(t["id"])
        assert {k: v for k, v in t.items() if k != "id"} == {
            "date": "2024-01-03", "ticker": "AAPL", "transaction_type": "Buy", "quantity": 10.0,
            "entry_price": 185.0, "fees": 1.5, "notes": "lot 1", "sequence": 3}
        assert PS.create_transaction("2024-01-03", "SPY", "Sell", 1, 1)["id"] != t["id"]

    @pytest.mark.parametrize("ticker", ["[Custom] _QT_TEST_Series", "  [CUSTOM] _QT_TEST_x"])
    def test_create_transaction_rejects_custom_tickers(self, fresh_home, ticker):
        with pytest.raises(ValueError, match="Custom tickers are returns-only"):
            PS.create_transaction("2024-01-03", ticker, "Buy", 1, 1)

    @pytest.mark.parametrize("override, expected", [
        ({}, (True, "")),
        ({"date": ""}, (False, "Date is required")),
        ({"ticker": "   "}, (False, "Ticker is required")),
        ({"transaction_type": "buy"}, (False, "Transaction type must be 'Buy' or 'Sell'")),
        ({"quantity": 0}, (False, "Quantity must be greater than 0")),
        ({"quantity": "abc"}, (False, "Invalid quantity")),
        ({"quantity": None}, (False, "Invalid quantity")),
        ({"entry_price": 0}, (True, "")),  # gifts allowed
        ({"entry_price": -1}, (False, "Entry price cannot be negative")),
        ({"entry_price": "x"}, (False, "Invalid entry price")),
        ({"fees": -0.01}, (False, "Fees cannot be negative")),
        ({"fees": "x"}, (False, "Invalid fees")),
    ])
    def test_validate_transaction(self, override, expected):
        t = tx("v", "2024-01-03", "AAPL", "Buy", 1, 100.0, 0.0)
        t.update(override)
        assert PS.validate_transaction(t) == expected

    def test_validate_transaction_missing_keys(self):
        assert PS.validate_transaction({}) == (False, "Date is required")
        assert PS.validate_transaction({"date": "2024-01-01", "ticker": "X",
                                        "transaction_type": "Sell"}) == (False, "Quantity must be greater than 0")

    def test_principal_and_cost_basis(self):
        buy = tx("b", "2024-01-03", "AAPL", "Buy", 10, 100.0, 2.0)
        sell = tx("s", "2024-01-04", "AAPL", "Sell", 10, 110.0, 2.0)
        assert PS.calculate_principal(buy) == 1002.0
        assert PS.calculate_principal(sell) == -1098.0
        assert PS.calculate_cost_basis(buy) == 1002.0
        assert PS.calculate_cost_basis(sell) == -1098.0
        # calculate_principal tolerates missing keys (defaults to Buy / 0).
        assert PS.calculate_principal({"quantity": "3", "entry_price": "2"}) == 6.0

    @pytest.mark.parametrize("ticker, kind, expected", [
        ("FREE CASH", "Buy", 0), ("free cash", "Sell", 3), ("AAPL", "Sell", 1), ("AAPL", "Buy", 2),
    ])
    def test_transaction_priority(self, ticker, kind, expected):
        assert PS.get_transaction_priority(ticker, kind) == expected


class TestHoldingsAndCash:
    def test_aggregate_holdings_hand_checked(self):
        holdings = PS.calculate_aggregate_holdings(sample_ledger(), PRICES)
        assert [h["ticker"] for h in holdings] == ["SPY", "AAPL", "MSFT"]  # QQQ closed, cash excluded
        spy, aapl, msft = holdings
        assert aapl["total_quantity"] == pytest.approx(60.0)
        # cost 100*185+1 = 18501, sell reduces by (40*190-1) = 7599 -> 10902 / 60
        assert aapl["avg_cost_basis"] == pytest.approx(10902.0 / 60.0)
        assert aapl["market_value"] == pytest.approx(12000.0)
        assert aapl["total_pnl"] == pytest.approx(1098.0)
        assert spy["avg_cost_basis"] == pytest.approx(23501.0 / 50.0)
        assert spy["weight_pct"] == pytest.approx(25000.0 / 37000.0 * 100.0)
        assert aapl["weight_pct"] + spy["weight_pct"] == pytest.approx(100.0)
        assert msft == {"ticker": "MSFT", "total_quantity": 10.0, "avg_cost_basis": 420.0,
                        "current_price": None, "market_value": None, "total_pnl": None,
                        "weight_pct": 0.0}

        totals = PS.calculate_portfolio_totals(holdings)
        assert totals["total_market_value"] == pytest.approx(37000.0)
        assert totals["total_cost_basis"] == pytest.approx(10902.0 + 23501.0 + 4200.0)
        assert totals["total_pnl"] == pytest.approx(2597.0)
        assert totals["total_pnl_pct"] == pytest.approx(2597.0 / 38603.0 * 100.0)

        assert_golden("aggregate_holdings", {"holdings": holdings, "totals": totals}, area="service")

    def test_aggregate_holdings_edge_cases(self):
        assert PS.calculate_aggregate_holdings([], PRICES) == []
        assert PS.calculate_portfolio_totals([]) == {
            "total_market_value": 0.0, "total_cost_basis": 0.0, "total_pnl": 0.0, "total_pnl_pct": 0.0}
        # No prices at all -> every weight stays 0 and order is insertion order.
        h = PS.calculate_aggregate_holdings(sample_ledger(), {})
        assert [x["ticker"] for x in h] == ["AAPL", "SPY", "MSFT"]
        assert all(x["weight_pct"] == 0.0 and x["market_value"] is None for x in h)
        # Ticker grouping is case-sensitive (only FREE CASH is matched case-insensitively).
        mixed = [tx("a", "2024-01-01", "aapl", "Buy", 1, 10.0), tx("b", "2024-01-01", "AAPL", "Buy", 1, 10.0),
                 tx("c", "2024-01-01", "free cash", "Buy", 100, 1.0)]
        assert sorted(x["ticker"] for x in PS.calculate_aggregate_holdings(mixed, {})) == ["AAPL", "aapl"]

    def test_free_cash_summary_and_point_in_time(self):
        ledger = sample_ledger()
        summary = PS.calculate_free_cash_summary(ledger)
        assert summary == {"ticker": "FREE CASH", "quantity": pytest.approx(56686.0),
                           "principal": pytest.approx(56686.0), "market_value": pytest.approx(56686.0)}
        assert PS.calculate_free_cash_at_date(ledger, "2024-01-01") == 0.0
        assert PS.calculate_free_cash_at_date(ledger, "2024-01-02") == 100000.0
        assert PS.calculate_free_cash_at_date(ledger, "2024-03-01") == pytest.approx(52396.5)
        assert PS.calculate_free_cash_at_date(ledger, "2099-12-31") == pytest.approx(56686.0)
        assert PS.calculate_free_cash_at_date(ledger, "2099-12-31", exclude_transaction_id="t07") == \
            pytest.approx(56686.0 + 5010.0)

        assert PS.calculate_position_at_date(ledger, "AAPL", "2024-01-31") == 100.0
        assert PS.calculate_position_at_date(ledger, "aapl", "2024-02-01") == 60.0
        assert PS.calculate_position_at_date(ledger, "AAPL", "2024-12-31", exclude_transaction_id="t04") == 100.0
        assert PS.calculate_position_at_date(ledger, "QQQ", "2024-12-31") == 0.0
        assert PS.calculate_position_at_date(ledger, "_QT_TEST_NONE", "2024-12-31") == 0.0


class TestSequencing:
    @pytest.mark.parametrize("is_cash, kind, expected", [
        (True, "Buy", -1),    # deposit: before everything
        (True, "Sell", 2),    # withdrawal: after everything
        (False, "Sell", -1),  # regular sell: before the (priority 2) buys
        (False, "Buy", 2),    # regular buy: after same/lower priority
    ])
    def test_sequence_for_date_edit(self, is_cash, kind, expected):
        assert PS.get_sequence_for_date_edit(sample_ledger(), "2024-01-03", is_cash, kind) == expected

    def test_sequence_for_empty_day(self):
        assert PS.get_sequence_for_date_edit(sample_ledger(), "2030-01-01", False, "Buy") == 0

    def test_sequence_between_priorities(self):
        day = [tx("d", "2024-05-01", "FREE CASH", "Buy", 10, 1.0, seq=4),
               tx("s", "2024-05-01", "AAPL", "Sell", 1, 1.0, seq=5),
               tx("w", "2024-05-01", "FREE CASH", "Sell", 1, 1.0, seq=9)]
        assert PS.get_sequence_for_date_edit(day, "2024-05-01", False, "Buy") == 6
        assert PS.get_sequence_for_date_edit(day, "2024-05-01", False, "Sell") == 6
        only_withdrawal = [day[2]]
        assert PS.get_sequence_for_date_edit(only_withdrawal, "2024-05-01", False, "Buy") == 8

    def test_resequence_same_day(self):
        day = [tx("w", "2024-05-01", "FREE CASH", "Sell", 1, 1.0, seq=0),
               tx("b", "2024-05-01", "SPY", "Buy", 1, 1.0, seq=1),
               tx("s", "2024-05-01", "AAPL", "Sell", 1, 1.0, seq=2),
               tx("d", "2024-05-01", "FREE CASH", "Buy", 10, 1.0, seq=3),
               tx("x", "2024-05-02", "AAPL", "Buy", 1, 1.0, seq=0)]
        assert PS.resequence_same_day_transactions(day, "2024-05-01") == {"d": 0, "s": 1, "b": 2, "w": 3}
        assert PS.resequence_same_day_transactions(day, "2030-01-01") == {}


class TestSafeguards:
    @pytest.mark.parametrize("new_tx, expected", [
        (tx("n1", "2024-04-03", "SPY", "Buy", 1000, 500.0),
         (False, "Cannot complete this purchase. You would need $500,000.00 but only have "
                 "$56,686.00 available on 2024-04-03.")),
        (tx("n2", "2024-02-02", "AAPL", "Sell", 70, 190.0),
         (False, "Cannot sell 70.0000 shares of AAPL. You only have 60.0000 shares available on 2024-02-02.")),
        (tx("n3", "2024-04-03", "FREE CASH", "Sell", 60000, 1.0),
         (False, "Cannot withdraw $60,000.00. Only $56,686.00 is available on 2024-04-03.")),
        (tx("n4", "2024-04-03", "MSFT", "Buy", 10, 100.0), (True, "")),
        (tx("n5", "2024-04-03", "FREE CASH", "Buy", 1, 1.0), (True, "")),
        (tx("n6", "2023-12-29", "AAPL", "Buy", 1, 1.0),
         (False, "Cannot complete this purchase. You would need $1.00 but only have $0.00 available on 2023-12-29.")),
    ])
    def test_new_transaction(self, new_tx, expected):
        assert PS.validate_transaction_safeguards(sample_ledger(), new_tx, is_new=True) == expected

    def test_edit_deposit_forward_breaks_chain(self):
        ledger = sample_ledger()
        edited = dict(_by_id(ledger, "t01"), date="2024-02-15")
        ok, msg = PS.validate_transaction_safeguards(ledger, edited, is_new=False, original_date="2024-01-02")
        assert (ok, msg) == (False, "This change would cause insufficient cash for AAPL purchase on "
                                    "2024-01-03.\nAvailable: $0.00, Needed: $18,501.00")

    def test_edit_deposit_backward_skips_chain(self):
        ledger = sample_ledger()
        edited = dict(_by_id(ledger, "t01"), date="2023-12-29", quantity=1.0)
        # Moving a deposit earlier is always allowed, even if the smaller amount breaks later buys.
        assert PS.validate_transaction_safeguards(ledger, edited, is_new=False,
                                                  original_date="2024-01-02") == (True, "")
        # Without original_date the chain is validated and fails.
        ok, msg = PS.validate_transaction_safeguards(ledger, edited, is_new=False)
        assert not ok and msg.startswith("This change would cause insufficient cash for AAPL purchase on 2024-01-03")

    def test_edit_sell_quantity_above_position(self):
        ledger = sample_ledger()
        edited = dict(_by_id(ledger, "t04"), quantity=120.0)
        assert PS.validate_transaction_safeguards(ledger, edited, is_new=False, original_date="2024-02-01") == (
            False, "Cannot sell 120.0000 shares of AAPL. You only have 100.0000 shares available on 2024-02-01.")

    def test_edit_buy_quantity_breaks_later_sell(self):
        ledger = sample_ledger()
        edited = dict(_by_id(ledger, "t02"), quantity=30.0)
        assert PS.validate_transaction_safeguards(ledger, edited, is_new=False, original_date="2024-01-03") == (
            False, "This change would cause insufficient shares for AAPL sale on 2024-02-01.\n"
                   "Available: 30.0000, Needed: 40.0000")

    def test_edit_withdrawal_chain(self):
        ledger = sample_ledger()
        edited = dict(_by_id(ledger, "t07"), date="2024-01-02", quantity=100000.0)
        ok, msg = PS.validate_transaction_safeguards(ledger, edited, is_new=False, original_date="2024-04-01")
        assert not ok
        assert msg == "Cannot withdraw $100,000.00. Only $100,000.00 is available on 2024-01-02."

    def test_chain_validation_direct(self):
        ledger = sample_ledger()
        assert PS.validate_transaction_chain(ledger, _by_id(ledger, "t08")) == (True, "")
        assert PS.validate_transaction_chain(ledger, dict(_by_id(ledger, "t01"), quantity=1.0),
                                             skip_validation=True) == (True, "")
        # validation_start_date: failures before it are ignored.
        edited = dict(_by_id(ledger, "t01"), date="2024-02-15")
        assert PS.validate_transaction_chain(ledger, edited, validation_start_date="2024-02-15") == (True, "")

    def test_deletion(self):
        ledger = sample_ledger()
        ok, msg = PS.validate_transaction_deletion(ledger, _by_id(ledger, "t01"))
        assert not ok
        assert msg == ("Cannot delete this deposit. It would cause insufficient cash for AAPL purchase on "
                       "2024-01-03.\n\nAvailable: $0.00, Needed: $18,501.00\n\n"
                       "Please delete or modify transactions that depend on this cash first.")
        ok, msg = PS.validate_transaction_deletion(ledger, _by_id(ledger, "t02"))
        assert not ok
        assert msg.startswith("Cannot delete this transaction. It would cause insufficient shares for AAPL "
                              "sale on 2024-02-01.\n\nAvailable: 0.0000, Needed: 40.0000")
        assert PS.validate_transaction_deletion(ledger, _by_id(ledger, "t08")) == (True, "")
        assert PS.validate_transaction_deletion(ledger, _by_id(ledger, "t07")) == (True, "")
        assert PS.validate_transaction_deletion([ledger[0]], ledger[0]) == (True, "")


class TestImportHelpers:
    def test_generate_imported_transactions(self, fresh_home):
        src = sample_ledger()
        src[1]["ticker"] = "aapl"
        out = PS.generate_imported_transactions(src, include_fees=False)
        assert len(out) == len(src)
        assert all(set(t) == {"id", "date", "ticker", "transaction_type", "quantity", "entry_price", "fees"}
                   for t in out)  # notes/sequence are dropped
        assert {t["id"] for t in out}.isdisjoint({t["id"] for t in src})
        assert [t["ticker"] for t in out][:2] == ["FREE CASH", "AAPL"]
        assert all(t["fees"] == 0.0 for t in out)
        with_fees = PS.generate_imported_transactions(src, include_fees=True)
        assert [t["fees"] for t in with_fees] == [t["fees"] for t in src]
        assert [(t["date"], t["quantity"], t["entry_price"]) for t in with_fees] == [
            (t["date"], t["quantity"], t["entry_price"]) for t in src]

    def test_process_flat_import(self, fresh_home):
        today_before = datetime.now().strftime("%Y-%m-%d")
        out = PS.process_flat_import(sample_ledger(), include_fees=True)
        today_after = datetime.now().strftime("%Y-%m-%d")
        assert all(t["date"] in (today_before, today_after) for t in out)
        assert all(re.fullmatch(r"[0-9a-f-]{36}", t["id"]) for t in out)
        stable = [{k: v for k, v in t.items() if k not in ("id", "date")} for t in out]
        assert stable == [
            {"ticker": "FREE CASH", "transaction_type": "Buy", "quantity": 95000.0, "entry_price": 1.0, "fees": 10.0},
            {"ticker": "AAPL", "transaction_type": "Buy", "quantity": 60.0, "entry_price": 185.0, "fees": 2.0},
            {"ticker": "SPY", "transaction_type": "Buy", "quantity": 50.0, "entry_price": 470.0, "fees": 1.0},
            {"ticker": "QQQ", "transaction_type": "Sell", "quantity": 0.0, "entry_price": 440.0, "fees": 1.0},
            {"ticker": "MSFT", "transaction_type": "Buy", "quantity": 10.0, "entry_price": 420.0, "fees": 0},
        ]
        skipped = PS.process_flat_import(sample_ledger(), include_fees=False, skip_zero_positions=True)
        assert [t["ticker"] for t in skipped] == ["FREE CASH", "AAPL", "SPY", "MSFT"]
        assert all(t["fees"] == 0 for t in skipped)

    def test_process_flat_import_net_short_and_sell_only(self, fresh_home):
        ledger = [tx("a", "2024-01-01", "_qt_test_x", "Sell", 5, 10.0),
                  tx("b", "2024-01-02", f"{PREFIX}X", "Buy", 2, 12.0)]
        out = PS.process_flat_import(copy.deepcopy(ledger), include_fees=False)
        assert [(t["ticker"], t["transaction_type"], t["quantity"], t["entry_price"]) for t in out] == [
            (f"{PREFIX}X", "Sell", 3.0, 12.0)]
        sell_only = PS.process_flat_import([ledger[0]], include_fees=False)
        assert [(t["transaction_type"], t["quantity"], t["entry_price"]) for t in sell_only] == [("Sell", 5.0, 0)]
