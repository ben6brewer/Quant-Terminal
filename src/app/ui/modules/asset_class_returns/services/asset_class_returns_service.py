"""Asset Class Returns Service - Computes annual returns quilt chart data."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd

# Asset class definitions: (label, ticker, RGB color)
ASSET_CLASSES = [
    ("Large Cap", "SPY", (55, 95, 190)),
    ("Mid Cap", "MDY", (160, 55, 170)),
    ("Small Cap", "SPSM", (210, 75, 75)),
    ("Int'l Stocks", "EFA", (50, 155, 60)),
    ("Emerg. Mkts", "EEM", (195, 135, 30)),
    ("REITs", "VNQ", (80, 170, 210)),
    ("Bonds", "AGG", (140, 140, 150)),
    ("TIPS", "TIP", (175, 115, 75)),
    ("Commodities", "DJP", (190, 155, 55)),
    ("Cash", "BIL", (145, 155, 95)),
    ("Bitcoin", "BTC-USD", (235, 150, 40)),
]

EQUAL_WEIGHT_COLOR = (115, 115, 125)


def _ticker_to_color(ticker: str) -> tuple:
    """Hash-based deterministic color. SHA-256 -> HSV hue, fixed S=0.65/V=0.75 -> RGB."""
    import hashlib
    import colorsys

    h = int(hashlib.sha256(ticker.encode()).hexdigest()[:8], 16)
    hue = (h % 360) / 360.0
    r, g, b = colorsys.hsv_to_rgb(hue, 0.65, 0.75)
    return (int(r * 255), int(g * 255), int(b * 255))


class AssetClassReturnsService:
    """Stateless service for computing asset class annual returns."""

    @staticmethod
    def compute_annual_returns(cagr_years=None) -> dict:
        """Compute ranked annual returns for all asset classes.

        Args:
            cagr_years: If set, compute trailing CAGR over this many years.

        Returns:
            Dict with keys: years, data, cagr, asset_count.
        """
        import numpy as np
        import pandas as pd

        from app.services.market_data import fetch_price_history_batch

        tickers = [t for _, t, _ in ASSET_CLASSES]
        batch = fetch_price_history_batch(tickers)

        # Build annual returns per asset
        asset_annual = {}  # label -> {year: return}
        asset_cagr = {}    # label -> cagr
        label_color = {}   # label -> color

        for label, ticker, color in ASSET_CLASSES:
            label_color[label] = color
            df = batch.get(ticker)
            if df is None or df.empty or "Close" not in df.columns:
                asset_annual[label] = {}
                asset_cagr[label] = None
                continue

            close = df["Close"]
            if not isinstance(close.index, pd.DatetimeIndex):
                close.index = pd.to_datetime(close.index)

            annual, cagr = AssetClassReturnsService._compute_ticker_returns(close, cagr_years)
            asset_annual[label] = annual
            asset_cagr[label] = cagr

        # Collect all years across all assets
        all_years = set()
        for annual in asset_annual.values():
            all_years.update(annual.keys())
        if not all_years:
            return {"years": [], "data": {}, "cagr": [], "asset_count": 0}

        years = sorted(all_years)

        # Compute equal-weight returns per year
        ew_annual = {}
        for year in years:
            returns_this_year = []
            for label in asset_annual:
                r = asset_annual[label].get(year)
                if r is not None and not np.isnan(r):
                    returns_this_year.append(r)
            if returns_this_year:
                # Geometric mean: ((1+r1)*(1+r2)*...*(1+rn))^(1/n) - 1
                product = 1.0
                for r in returns_this_year:
                    product *= (1 + r)
                ew_annual[year] = product ** (1.0 / len(returns_this_year)) - 1
            else:
                ew_annual[year] = np.nan

        # Equal-weight CAGR: compound EW annual returns geometrically
        if cagr_years is not None:
            import math
            n_years = math.ceil(cagr_years)
            ew_years_for_cagr = years[-n_years:] if len(years) > n_years else years
        else:
            ew_years_for_cagr = years
        ew_values = [ew_annual[y] for y in ew_years_for_cagr if not np.isnan(ew_annual.get(y, np.nan))]
        if len(ew_values) >= 1:
            product = 1.0
            for r in ew_values:
                product *= (1 + r)
            ew_cagr = product ** (1.0 / len(ew_values)) - 1
        else:
            ew_cagr = None

        # Build ranked data per year
        data = {}
        all_labels = [label for label, _, _ in ASSET_CLASSES] + ["Equal Wt."]
        all_colors = {**label_color, "Equal Wt.": EQUAL_WEIGHT_COLOR}

        for year in years:
            entries = []
            for label in all_labels:
                if label == "Equal Wt.":
                    r = ew_annual.get(year, np.nan)
                else:
                    r = asset_annual.get(label, {}).get(year)
                    if r is None:
                        r = np.nan

                # Resolve ticker for this entry
                if label == "Equal Wt.":
                    ticker = "Equal Wt."
                else:
                    ticker = next(
                        (t for lbl, t, _ in ASSET_CLASSES if lbl == label), label
                    )

                entries.append({
                    "label": label,
                    "ticker": ticker,
                    "return": r,
                    "color": all_colors[label],
                })

            # Sort: valid returns descending, NaN at bottom
            valid = [e for e in entries if not np.isnan(e["return"])]
            invalid = [e for e in entries if np.isnan(e["return"])]
            valid.sort(key=lambda e: e["return"], reverse=True)
            data[year] = valid + invalid

        # Build ranked CAGR
        cagr_entries = []
        for label in all_labels:
            if label == "Equal Wt.":
                c = ew_cagr
            else:
                c = asset_cagr.get(label)

            if label == "Equal Wt.":
                ticker = "Equal Wt."
            else:
                ticker = next(
                    (t for lbl, t, _ in ASSET_CLASSES if lbl == label), label
                )

            cagr_entries.append({
                "label": label,
                "ticker": ticker,
                "cagr": c if c is not None else np.nan,
                "color": all_colors[label],
            })

        valid_cagr = [e for e in cagr_entries if not np.isnan(e["cagr"])]
        invalid_cagr = [e for e in cagr_entries if np.isnan(e["cagr"])]
        valid_cagr.sort(key=lambda e: e["cagr"], reverse=True)

        return {
            "years": years,
            "data": data,
            "cagr": valid_cagr + invalid_cagr,
            "asset_count": len(all_labels),
        }

    @staticmethod
    def compute_custom_returns(tickers: list, cagr_years=None) -> dict:
        """Compute ranked annual returns for user-defined tickers.

        Args:
            tickers: List of ticker symbols.
            cagr_years: If set, compute trailing CAGR over this many years.

        Returns:
            Dict with keys: years, data, cagr, asset_count.
        """
        import numpy as np
        import pandas as pd

        from app.services.market_data import fetch_price_history_batch

        if not tickers:
            return {"years": [], "data": {}, "cagr": [], "asset_count": 0}

        batch = fetch_price_history_batch(tickers)

        asset_annual = {}  # ticker -> {year: return}
        asset_cagr = {}    # ticker -> cagr
        ticker_color = {}  # ticker -> color

        for ticker in tickers:
            ticker_color[ticker] = _ticker_to_color(ticker)
            df = batch.get(ticker)
            if df is None or df.empty or "Close" not in df.columns:
                asset_annual[ticker] = {}
                asset_cagr[ticker] = None
                continue

            close = df["Close"]
            if not isinstance(close.index, pd.DatetimeIndex):
                close.index = pd.to_datetime(close.index)

            annual, cagr = AssetClassReturnsService._compute_ticker_returns(close, cagr_years)
            asset_annual[ticker] = annual
            asset_cagr[ticker] = cagr

        # Collect all years
        all_years = set()
        for annual in asset_annual.values():
            all_years.update(annual.keys())
        if not all_years:
            return {"years": [], "data": {}, "cagr": [], "asset_count": 0}

        years = sorted(all_years)

        # Equal-weight returns per year
        ew_annual = {}
        for year in years:
            returns_this_year = []
            for ticker in tickers:
                r = asset_annual[ticker].get(year)
                if r is not None and not np.isnan(r):
                    returns_this_year.append(r)
            if returns_this_year:
                product = 1.0
                for r in returns_this_year:
                    product *= (1 + r)
                ew_annual[year] = product ** (1.0 / len(returns_this_year)) - 1
            else:
                ew_annual[year] = np.nan

        # Equal-weight CAGR
        if cagr_years is not None:
            import math
            n_years = math.ceil(cagr_years)
            ew_years_for_cagr = years[-n_years:] if len(years) > n_years else years
        else:
            ew_years_for_cagr = years
        ew_values = [ew_annual[y] for y in ew_years_for_cagr if not np.isnan(ew_annual.get(y, np.nan))]
        if len(ew_values) >= 1:
            product = 1.0
            for r in ew_values:
                product *= (1 + r)
            ew_cagr = product ** (1.0 / len(ew_values)) - 1
        else:
            ew_cagr = None

        # Build ranked data per year
        data = {}
        all_labels = list(tickers) + ["Equal Wt."]
        all_colors = {**ticker_color, "Equal Wt.": EQUAL_WEIGHT_COLOR}

        for year in years:
            entries = []
            for label in all_labels:
                if label == "Equal Wt.":
                    r = ew_annual.get(year, np.nan)
                else:
                    r = asset_annual.get(label, {}).get(year)
                    if r is None:
                        r = np.nan

                entries.append({
                    "label": label,
                    "ticker": label,
                    "return": r,
                    "color": all_colors[label],
                })

            valid = [e for e in entries if not np.isnan(e["return"])]
            invalid = [e for e in entries if np.isnan(e["return"])]
            valid.sort(key=lambda e: e["return"], reverse=True)
            data[year] = valid + invalid

        # Build ranked CAGR
        cagr_entries = []
        for label in all_labels:
            if label == "Equal Wt.":
                c = ew_cagr
            else:
                c = asset_cagr.get(label)

            cagr_entries.append({
                "label": label,
                "ticker": label,
                "cagr": c if c is not None else np.nan,
                "color": all_colors[label],
            })

        valid_cagr = [e for e in cagr_entries if not np.isnan(e["cagr"])]
        invalid_cagr = [e for e in cagr_entries if np.isnan(e["cagr"])]
        valid_cagr.sort(key=lambda e: e["cagr"], reverse=True)

        return {
            "years": years,
            "data": data,
            "cagr": valid_cagr + invalid_cagr,
            "asset_count": len(all_labels),
        }

    @staticmethod
    def _compute_ticker_returns(close: "pd.Series", cagr_years=None) -> tuple:
        """Compute annual returns and CAGR for a close price series.

        Args:
            close: Price series with DatetimeIndex.
            cagr_years: If set, compute trailing CAGR over this many years.
                        None = full history CAGR.

        Returns:
            (dict of year->return, cagr float or None)
        """
        import numpy as np
        import pandas as pd

        # Resample to year-end
        yearly_close = close.resample("YE").last().dropna()
        annual_returns = yearly_close.pct_change().dropna()

        result = {}
        for dt, ret in annual_returns.items():
            result[dt.year] = ret

        # Check if current year needs YTD
        now = pd.Timestamp.now()
        current_year = now.year
        if current_year not in result and len(close) > 0:
            # Find the last close of the prior year
            prior_year_data = close[close.index.year == current_year - 1]
            current_year_data = close[close.index.year == current_year]
            if not prior_year_data.empty and not current_year_data.empty:
                prior_end = prior_year_data.iloc[-1]
                latest = current_year_data.iloc[-1]
                if prior_end != 0:
                    result[current_year] = latest / prior_end - 1

        # CAGR
        cagr = None
        if len(close) >= 2:
            if cagr_years is not None:
                # Trailing CAGR over lookback period
                lookback_days = int(cagr_years * 365.25)
                lookback_start = close.index[-1] - pd.Timedelta(days=lookback_days)
                trimmed = close[close.index >= lookback_start]
                # Fall back to full history if not enough data
                if len(trimmed) < 2 or trimmed.index[0] == close.index[0]:
                    trimmed = close
            else:
                trimmed = close

            first_val = trimmed.iloc[0]
            last_val = trimmed.iloc[-1]
            if first_val > 0:
                total_days = (trimmed.index[-1] - trimmed.index[0]).days
                if total_days > 0:
                    years = total_days / 365.25
                    cagr = (last_val / first_val) ** (1.0 / years) - 1

        return result, cagr
