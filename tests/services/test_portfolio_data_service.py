"""Tests for app.services.portfolio_data_service.PortfolioDataService."""

from unittest.mock import MagicMock, patch

import pytest

from app.services.portfolio_data_service import PortfolioDataService, Transaction


class TestTransaction:
    def test_from_dict(self):
        data = {
            "id": "abc123",
            "date": "2024-01-15",
            "ticker": "AAPL",
            "transaction_type": "BUY",
            "quantity": 10,
            "entry_price": 150.0,
            "fees": 0.0,
            "sequence": 1,
        }
        t = Transaction.from_dict(data)
        assert t.ticker == "AAPL"
        assert t.quantity == 10
        assert t.entry_price == 150.0

    def test_from_dict_defaults(self):
        """Missing optional fields should use defaults."""
        data = {
            "id": "abc",
            "date": "2024-01-15",
            "ticker": "MSFT",
            "transaction_type": "BUY",
            "quantity": 5,
            "entry_price": 300.0,
        }
        t = Transaction.from_dict(data)
        assert t.fees == 0.0
        assert t.sequence == 0


class TestPortfolioDataService:
    def test_list_portfolios_returns_list(self, monkeypatch):
        monkeypatch.setattr(
            "app.services.portfolio_data_service.PortfolioPersistence.list_portfolios",
            staticmethod(lambda: ["Portfolio1", "Portfolio2"]),
        )
        result = PortfolioDataService.list_portfolios()
        assert isinstance(result, list)
        assert len(result) == 2

    def test_portfolio_exists(self, monkeypatch):
        monkeypatch.setattr(
            "app.services.portfolio_data_service.PortfolioPersistence.portfolio_exists",
            staticmethod(lambda name: name == "MyPortfolio"),
        )
        assert PortfolioDataService.portfolio_exists("MyPortfolio") is True
        assert PortfolioDataService.portfolio_exists("Nonexistent") is False

    def test_get_tickers(self, monkeypatch):
        mock_portfolio = MagicMock()
        mock_portfolio.tickers = ["AAPL", "MSFT", "GOOGL"]
        monkeypatch.setattr(
            "app.services.portfolio_data_service.PortfolioDataService.get_portfolio",
            classmethod(lambda cls, name: mock_portfolio),
        )
        tickers = PortfolioDataService.get_tickers("TestPortfolio")
        assert tickers == ["AAPL", "MSFT", "GOOGL"]
