"""Tests for app.services.live_return_service.LiveReturnService."""

import numpy as np
import pandas as pd
import pytest


class TestLiveReturnService:
    def test_import(self):
        from app.services.live_return_service import LiveReturnService
        assert LiveReturnService is not None

    def test_append_live_return_empty_series(self):
        from app.services.live_return_service import LiveReturnService
        result = LiveReturnService.append_live_return(pd.Series(dtype=float), "AAPL")
        assert isinstance(result, pd.Series)

    def test_append_live_portfolio_return_empty(self):
        from app.services.live_return_service import LiveReturnService
        result = LiveReturnService.append_live_portfolio_return(
            pd.Series(dtype=float), "TestPortfolio"
        )
        assert isinstance(result, pd.Series)
