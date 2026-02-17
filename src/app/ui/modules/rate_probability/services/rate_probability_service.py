"""Rate Probability Service - Fed funds futures data, caching, and probability calculations."""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    import pandas as pd

# Month codes for CME fed funds futures
MONTH_CODES = {
    "F": 1, "G": 2, "H": 3, "J": 4, "K": 5, "M": 6,
    "N": 7, "Q": 8, "U": 9, "V": 10, "X": 11, "Z": 12,
}
CODE_TO_MONTH = {v: k for k, v in MONTH_CODES.items()}

RATE_STEP = 0.25  # 25bp buckets
CACHE_DIR = Path.home() / ".quant_terminal" / "cache" / "fed_futures"
_DEBUG = False  # Set True to enable calculation debug logging

# Cache TTLs (seconds)
_FUTURES_TTL = 300       # 5 minutes
_TARGET_RATE_TTL = 3600  # 1 hour
_HISTORICAL_TTL = 900    # 15 minutes


class RateProbabilityService:
    """Fed funds futures data fetching, caching, and probability calculations."""

    # --- In-memory TTL Cache ---
    _futures_cache: Optional[Tuple[datetime, "pd.DataFrame"]] = None
    _target_rate_cache: Optional[Tuple[datetime, Tuple[float, float]]] = None
    _historical_cache: Dict[str, Tuple[datetime, "pd.DataFrame"]] = {}

    @classmethod
    def _cache_valid(cls, entry: Optional[Tuple[datetime, object]], ttl: int) -> bool:
        """Check if a cache entry exists and is within its TTL."""
        if entry is None:
            return False
        cached_at, _ = entry
        return (datetime.now() - cached_at).total_seconds() < ttl

    # --- Contract Ticker Generation ---

    @classmethod
    def _generate_contract_tickers(cls, months_ahead: int = 18) -> List[Tuple[str, int, int]]:
        """Generate (ticker, month, year) tuples for ZQ contracts.

        Returns list of (ticker_string, month_int, year_int).
        E.g., ('ZQH26.CBT', 3, 2026) for March 2026.
        """
        today = date.today()
        contracts = []

        for i in range(months_ahead):
            # Calculate target month
            month = ((today.month - 1 + i) % 12) + 1
            year = today.year + ((today.month - 1 + i) // 12)

            month_code = CODE_TO_MONTH[month]
            year_suffix = str(year)[-2:]  # Last 2 digits
            ticker = f"ZQ{month_code}{year_suffix}.CBT"
            contracts.append((ticker, month, year))

        return contracts

    # --- Data Fetching ---

    @classmethod
    def fetch_futures_prices(cls) -> "pd.DataFrame":
        """Fetch current prices for all relevant ZQ futures contracts from Yahoo Finance.

        Returns DataFrame with columns: contract, month, year, price, implied_rate.
        Uses a 5-minute in-memory cache.
        """
        if cls._cache_valid(cls._futures_cache, _FUTURES_TTL):
            _, cached_df = cls._futures_cache
            return cached_df

        df = cls._fetch_futures_prices_uncached()
        if not df.empty:
            cls._futures_cache = (datetime.now(), df)
        return df

    @classmethod
    def _fetch_futures_prices_uncached(cls) -> "pd.DataFrame":
        """Fetch futures prices from Yahoo Finance (no cache)."""
        import pandas as pd
        from app.services.yahoo_finance_service import YahooFinanceService

        contracts = cls._generate_contract_tickers(months_ahead=18)
        tickers = [c[0] for c in contracts]

        close_data = YahooFinanceService.fetch_batch_short_history(tickers, period="5d")

        if close_data.empty:
            return pd.DataFrame()

        rows = []
        for ticker, month, year in contracts:
            if ticker in close_data.columns:
                col = close_data[ticker].dropna()
                if not col.empty:
                    price = float(col.iloc[-1])
                    if price > 0:
                        implied_rate = 100.0 - price
                        rows.append({
                            "contract": ticker,
                            "month": month,
                            "year": year,
                            "price": round(price, 4),
                            "implied_rate": round(implied_rate, 4),
                        })

        if not rows:
            return pd.DataFrame()

        return pd.DataFrame(rows)

    @classmethod
    def fetch_target_rate(cls) -> Tuple[float, float]:
        """Fetch current DFEDTARU/DFEDTARL from FRED.

        Returns (lower_bound, upper_bound) as percentages (e.g., 4.25, 4.50).
        Uses a 1-hour in-memory cache.
        """
        if cls._cache_valid(cls._target_rate_cache, _TARGET_RATE_TTL):
            _, cached_rate = cls._target_rate_cache
            return cached_rate

        rate = cls._fetch_target_rate_uncached()
        cls._target_rate_cache = (datetime.now(), rate)
        return rate

    @classmethod
    def _fetch_target_rate_uncached(cls) -> Tuple[float, float]:
        """Fetch target rate from FRED (no cache)."""
        from app.services.fred_api_key_service import FredApiKeyService

        api_key = FredApiKeyService.get_api_key()
        if not api_key:
            return (4.25, 4.50)

        try:
            from fredapi import Fred

            fred = Fred(api_key=api_key)

            upper = fred.get_series("DFEDTARU")
            lower = fred.get_series("DFEDTARL")

            if upper is not None and not upper.empty and lower is not None and not lower.empty:
                upper_val = float(upper.dropna().iloc[-1])
                lower_val = float(lower.dropna().iloc[-1])
                return (lower_val, upper_val)

        except Exception:
            pass

        return (4.25, 4.50)

    @classmethod
    def fetch_historical_futures(cls, contract_tickers: List[str], lookback_days: int = 90) -> "pd.DataFrame":
        """Fetch historical daily prices for specified futures contracts.

        Returns DataFrame: index=date, columns=contract tickers, values=prices.
        Uses a 15-minute in-memory cache keyed by (tickers, lookback).
        """
        cache_key = f"{','.join(sorted(contract_tickers))}:{lookback_days}"
        entry = cls._historical_cache.get(cache_key)
        if cls._cache_valid(entry, _HISTORICAL_TTL):
            _, cached_df = entry
            return cached_df

        df = cls._fetch_historical_futures_uncached(contract_tickers, lookback_days)
        if not df.empty:
            cls._historical_cache[cache_key] = (datetime.now(), df)
        return df

    @classmethod
    def _fetch_historical_futures_uncached(cls, contract_tickers: List[str], lookback_days: int = 90) -> "pd.DataFrame":
        """Fetch historical futures prices from Yahoo Finance (no cache)."""
        import pandas as pd
        from app.services.yahoo_finance_service import YahooFinanceService

        if not contract_tickers:
            return pd.DataFrame()

        return YahooFinanceService.fetch_batch_short_history(
            contract_tickers, period=f"{lookback_days}d"
        )

    # --- Probability Calculations ---

    @classmethod
    def _next_month_key(cls, key: Tuple[int, int]) -> Tuple[int, int]:
        """Get (month, year) for the month after the given key."""
        month, year = key
        if month == 12:
            return (1, year + 1)
        return (month + 1, year)

    @classmethod
    def _label_to_midpoint(cls, label: str, buckets: List[Tuple[float, float, str]]) -> float:
        """Convert bucket label to midpoint rate."""
        for low, high, lbl in buckets:
            if lbl == label:
                return (low + high) / 2.0
        return 0.0

    @classmethod
    def calculate_meeting_probabilities(
        cls,
        futures_df: "pd.DataFrame",
        target_rate: Tuple[float, float],
        meetings: List[date],
    ) -> "pd.DataFrame":
        """Calculate probability distribution for each FOMC meeting.

        Returns DataFrame: index=meeting date strings, columns=rate range labels,
        values=probability (0-100).

        Algorithm (CME FedWatch methodology):
        1. For each meeting, find the futures contract for that month
        2. implied_rate = 100 - price (already computed in futures_df)
        3. For the meeting month: unwind the blended monthly average to get
           the post-meeting expected effective rate
        4. Map post-meeting rate to 25bp bucket probabilities using linear
           interpolation between adjacent target rate midpoints
        5. Forward chain: track a full probability distribution over target
           rate midpoints, not just a single point estimate. For each meeting,
           iterate over all possible pre-meeting states and aggregate
           conditional post-meeting probabilities.
        """
        import pandas as pd

        if futures_df.empty or not meetings:
            return pd.DataFrame()

        lower, upper = target_rate
        current_midpoint = (lower + upper) / 2.0

        # Build a lookup: (month, year) -> implied_rate
        rate_lookup: Dict[Tuple[int, int], float] = {}
        for _, row in futures_df.iterrows():
            key = (int(row["month"]), int(row["year"]))
            rate_lookup[key] = float(row["implied_rate"])

        # Determine range of possible rates for column headers
        all_rates = list(rate_lookup.values()) + [current_midpoint]
        min_rate = min(all_rates) - 1.0
        max_rate = max(all_rates) + 1.0

        # Round to nearest 25bp buckets
        min_bucket = (int(min_rate / RATE_STEP) - 1) * RATE_STEP
        max_bucket = (int(max_rate / RATE_STEP) + 2) * RATE_STEP

        # Generate rate bucket labels (e.g., "400-425" for 4.00-4.25%)
        buckets: List[Tuple[float, float, str]] = []
        r = min_bucket
        while r < max_bucket:
            low_bp = int(r * 100)
            high_bp = int((r + RATE_STEP) * 100)
            buckets.append((r, r + RATE_STEP, f"{low_bp}-{high_bp}"))
            r = round(r + RATE_STEP, 4)

        import math

        # Initial EFFR: use prior month's contract (CME methodology).
        # The prior month's contract = actual EFFR for pre-meeting days.
        first_meeting = meetings[0]
        if first_meeting.month > 1:
            prior_key = (first_meeting.month - 1, first_meeting.year)
        else:
            prior_key = (12, first_meeting.year - 1)
        initial_effr = rate_lookup.get(prior_key, current_midpoint)

        # State: probability distribution over target rate midpoints.
        # Initial state is the current target midpoint (discrete bucket).
        # e_pre tracks the continuous expected rate for unwinding.
        state: Dict[float, float] = {current_midpoint: 100.0}
        e_pre = initial_effr

        if _DEBUG:
            print(f"  Initial EFFR: {e_pre:.4f}, state midpoint: {current_midpoint}")

        results = {}

        for meeting in meetings:
            key = (meeting.month, meeting.year)
            if key not in rate_lookup:
                continue

            implied_rate = rate_lookup[key]
            total_days = calendar.monthrange(meeting.year, meeting.month)[1]
            pre_days = meeting.day - 1
            post_days = total_days - pre_days

            # Compute expected post-meeting rate (single-point)
            if post_days <= 7:
                next_key = cls._next_month_key(key)
                e_post = rate_lookup.get(next_key, implied_rate)
            else:
                e_post = (
                    implied_rate * total_days - e_pre * pre_days
                ) / post_days

            # Expected change at this meeting → discrete action probabilities
            change = e_post - e_pre
            lower_steps = math.floor(change / RATE_STEP)
            lower_action = round(lower_steps * RATE_STEP, 4)
            upper_action = round(lower_action + RATE_STEP, 4)
            p_upper = (change - lower_action) / RATE_STEP
            p_lower = 1.0 - p_upper

            # Clamp probabilities to [0, 1] for numerical safety
            p_upper = max(0.0, min(1.0, p_upper))
            p_lower = 1.0 - p_upper

            if _DEBUG:
                print(f"  Meeting {meeting}: implied={implied_rate:.4f}, "
                      f"e_pre={e_pre:.4f}, e_post={e_post:.4f}, "
                      f"change={change*100:.1f}bp")
                print(f"    Actions: {lower_action:+.4f} ({p_lower*100:.1f}%), "
                      f"{upper_action:+.4f} ({p_upper*100:.1f}%)")
                print(f"    State has {len(state)} possible pre-rates")

            # Apply discrete actions to every pre-state
            new_state: Dict[float, float] = {}
            for pre_mid, pre_prob in state.items():
                if pre_prob < 0.01:
                    continue

                # Lower action (e.g. cut 25bp)
                mid_lo = round(pre_mid + lower_action, 4)
                new_state[mid_lo] = new_state.get(mid_lo, 0.0) + pre_prob * p_lower

                # Upper action (e.g. hold)
                mid_hi = round(pre_mid + upper_action, 4)
                new_state[mid_hi] = new_state.get(mid_hi, 0.0) + pre_prob * p_upper

            # Record probabilities for this meeting
            meeting_probs: Dict[str, float] = {}
            for low, high, label in buckets:
                mid = round((low + high) / 2.0, 4)
                meeting_probs[label] = round(new_state.get(mid, 0.0), 1)

            # Normalize to 100% if needed
            total = sum(meeting_probs.values())
            if total > 0 and abs(total - 100.0) > 0.5:
                factor = 100.0 / total
                meeting_probs = {k: round(v * factor, 1) for k, v in meeting_probs.items()}

            if _DEBUG:
                non_zero = {k: v for k, v in meeting_probs.items() if v > 0}
                print(f"    Result: {non_zero} (sum={sum(meeting_probs.values()):.1f})")

            results[meeting.strftime("%b %d, %Y")] = meeting_probs

            # Chain forward
            state = new_state
            e_pre = e_post

        if not results:
            return pd.DataFrame()

        df = pd.DataFrame(results).T
        df.columns.name = "Rate Range"
        df.index.name = "Meeting"

        # Remove columns that are all zeros
        df = df.loc[:, (df != 0).any(axis=0)]

        return df

    @classmethod
    def _rate_to_probabilities(
        cls,
        expected_rate: float,
        buckets: List[Tuple[float, float, str]],
    ) -> Dict[str, float]:
        """CME FedWatch interpolation: linear between adjacent target rate midpoints.

        Each bucket represents a 25bp target range (e.g. 4.25-4.50%).
        Probability is linearly interpolated between the two midpoints that
        bracket the expected rate.

        Returns {rate_range_label: probability} where probabilities sum to 100.
        """
        probs = {label: 0.0 for _, _, label in buckets}

        # Build list of (midpoint, label) for each bucket
        midpoints = [((low + high) / 2.0, label) for low, high, label in buckets]

        # Find which two adjacent midpoints bracket the expected rate
        for i in range(len(midpoints) - 1):
            lower_mid, lower_label = midpoints[i]
            upper_mid, upper_label = midpoints[i + 1]

            if lower_mid <= expected_rate <= upper_mid:
                p_upper = (expected_rate - lower_mid) / RATE_STEP * 100.0
                p_lower = 100.0 - p_upper
                probs[lower_label] = round(p_lower, 1)
                probs[upper_label] = round(p_upper, 1)
                return probs

        # Edge cases: rate outside all midpoints
        if expected_rate < midpoints[0][0]:
            probs[midpoints[0][1]] = 100.0
        else:
            probs[midpoints[-1][1]] = 100.0

        return probs

    @classmethod
    def get_implied_rate_path(
        cls,
        probabilities_df: "pd.DataFrame",
        buckets_info: Optional[List[Tuple[float, float, str]]] = None,
    ) -> List[Tuple[str, float]]:
        """Extract probability-weighted implied rate at each meeting.

        Returns [(meeting_label, weighted_avg_rate), ...]
        """
        if probabilities_df.empty:
            return []

        path = []
        for meeting_label in probabilities_df.index:
            row = probabilities_df.loc[meeting_label]
            # Calculate weighted average rate from column labels
            weighted_rate = 0.0
            total_prob = 0.0
            for col_label in row.index:
                prob = row[col_label]
                if prob > 0:
                    # Parse column label like "425-450" to get midpoint
                    try:
                        parts = col_label.split("-")
                        low_bp = int(parts[0])
                        high_bp = int(parts[1])
                        midpoint = (low_bp + high_bp) / 200.0  # Convert bp to percent
                        weighted_rate += midpoint * prob
                        total_prob += prob
                    except (ValueError, IndexError):
                        continue

            if total_prob > 0:
                weighted_rate /= total_prob
                path.append((meeting_label, round(weighted_rate, 4)))

        return path

    @classmethod
    def calculate_historical_probabilities(
        cls,
        meeting_date: date,
        historical_futures: "pd.DataFrame",
        target_rate: Tuple[float, float],
        meetings: List[date],
    ) -> "pd.DataFrame":
        """Calculate probability evolution for a specific meeting over time.

        Returns DataFrame: index=historical date, columns=outcome labels (e.g. "Cut 25bp"),
        values=probability (0-100).
        """
        import pandas as pd

        if historical_futures.empty:
            return pd.DataFrame()

        lower, upper = target_rate
        current_midpoint = (lower + upper) / 2.0

        # Find meetings up to and including the target meeting
        target_meetings = [m for m in meetings if m <= meeting_date]
        if not target_meetings or meeting_date not in target_meetings:
            if meeting_date not in meetings:
                target_meetings = [meeting_date]
            else:
                target_meetings = meetings[: meetings.index(meeting_date) + 1]

        # Find the contract ticker for the meeting month
        month_code = CODE_TO_MONTH.get(meeting_date.month)
        if not month_code:
            return pd.DataFrame()

        year_suffix = str(meeting_date.year)[-2:]
        target_ticker = f"ZQ{month_code}{year_suffix}.CBT"

        if target_ticker not in historical_futures.columns:
            return pd.DataFrame()

        # Calculate probabilities for each historical date
        results = {}
        contract_prices = historical_futures[target_ticker].dropna()

        # Check for next-month contract (for late-month meetings)
        next_key = cls._next_month_key((meeting_date.month, meeting_date.year))
        next_month_code = CODE_TO_MONTH.get(next_key[0])
        next_year_suffix = str(next_key[1])[-2:]
        next_ticker = f"ZQ{next_month_code}{next_year_suffix}.CBT" if next_month_code else None
        has_next = next_ticker and next_ticker in historical_futures.columns

        total_days = calendar.monthrange(meeting_date.year, meeting_date.month)[1]
        pre_days = meeting_date.day - 1
        post_days = total_days - pre_days
        is_late_month = post_days <= 7

        import math

        for hist_date, price in contract_prices.items():
            implied_rate = 100.0 - float(price)

            # Compute post-meeting rate
            if post_days <= 0 or is_late_month:
                # Late-month: use next month's contract if available
                if has_next:
                    next_price = historical_futures[next_ticker].get(hist_date)
                    if next_price is not None and not math.isnan(float(next_price)):
                        post_rate = 100.0 - float(next_price)
                    else:
                        post_rate = implied_rate
                else:
                    post_rate = implied_rate
            else:
                post_rate = (implied_rate * total_days - current_midpoint * pre_days) / post_days

            # Calculate change from current rate
            change_bp = round((post_rate - current_midpoint) * 100)  # in basis points

            # Classify into outcome buckets
            outcomes = cls._classify_rate_change(change_bp, current_midpoint)
            date_key = hist_date.strftime("%Y-%m-%d") if hasattr(hist_date, "strftime") else str(hist_date)
            results[date_key] = outcomes

        if not results:
            return pd.DataFrame()

        df = pd.DataFrame(results).T
        df.index = pd.to_datetime(df.index)
        df = df.sort_index()

        return df

    @classmethod
    def _classify_rate_change(cls, change_bp: int, current_midpoint: float) -> Dict[str, float]:
        """Classify expected rate change into probability buckets.

        Returns dict like {"Cut 50bp": 30.0, "Cut 25bp": 70.0, "Hold": 0.0, ...}
        """
        # Define standard outcome buckets
        outcomes = {
            "Cut 75bp+": 0.0,
            "Cut 50bp": 0.0,
            "Cut 25bp": 0.0,
            "Hold": 0.0,
            "Hike 25bp": 0.0,
            "Hike 50bp": 0.0,
            "Hike 75bp+": 0.0,
        }

        # Map change to probabilities
        if change_bp <= -62:
            outcomes["Cut 75bp+"] = 100.0
        elif change_bp <= -37:
            # Between -62 and -37: interpolate between Cut 75bp+ and Cut 50bp
            frac = (change_bp + 37) / (-25)
            outcomes["Cut 75bp+"] = round(frac * 100, 1)
            outcomes["Cut 50bp"] = round((1 - frac) * 100, 1)
        elif change_bp <= -12:
            frac = (change_bp + 12) / (-25)
            outcomes["Cut 50bp"] = round(frac * 100, 1)
            outcomes["Cut 25bp"] = round((1 - frac) * 100, 1)
        elif change_bp <= 12:
            frac = (change_bp + 12) / 24
            outcomes["Cut 25bp"] = round((1 - frac) * 100, 1)
            outcomes["Hold"] = round(frac * 100, 1)
        elif change_bp <= 37:
            frac = (change_bp - 12) / 25
            outcomes["Hold"] = round((1 - frac) * 100, 1)
            outcomes["Hike 25bp"] = round(frac * 100, 1)
        elif change_bp <= 62:
            frac = (change_bp - 37) / 25
            outcomes["Hike 25bp"] = round((1 - frac) * 100, 1)
            outcomes["Hike 50bp"] = round(frac * 100, 1)
        else:
            outcomes["Hike 75bp+"] = 100.0

        return outcomes
