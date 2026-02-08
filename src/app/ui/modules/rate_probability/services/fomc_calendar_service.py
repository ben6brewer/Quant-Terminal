"""FOMC Calendar Service - Meeting date management with scraping + hardcoded fallback."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Dict, List, Optional


class FomcCalendarService:
    """FOMC meeting date management - scrape from Fed website with hardcoded fallback."""

    # Hardcoded fallback dates (decision day = last day of each 2-day meeting)
    FALLBACK_DATES: Dict[int, List[date]] = {
        2025: [
            date(2025, 1, 29), date(2025, 3, 19), date(2025, 5, 7),
            date(2025, 6, 18), date(2025, 7, 30), date(2025, 9, 17),
            date(2025, 10, 29), date(2025, 12, 10),
        ],
        2026: [
            date(2026, 1, 28), date(2026, 3, 18), date(2026, 4, 29),
            date(2026, 6, 17), date(2026, 7, 29), date(2026, 9, 16),
            date(2026, 10, 28), date(2026, 12, 9),
        ],
        2027: [
            date(2027, 1, 27), date(2027, 3, 17), date(2027, 4, 28),
            date(2027, 6, 9), date(2027, 7, 28), date(2027, 9, 15),
            date(2027, 10, 27), date(2027, 12, 8),
        ],
    }

    _scraped_dates: Optional[Dict[int, List[date]]] = None

    @classmethod
    def get_upcoming_meetings(cls, count: int = 12) -> List[date]:
        """Return next `count` FOMC meeting dates from today."""
        today = date.today()
        all_dates = cls.get_all_meetings()
        upcoming = [d for d in all_dates if d > today]
        return upcoming[:count]

    @classmethod
    def get_all_meetings(cls) -> List[date]:
        """Return all known meeting dates (past + future), sorted."""
        dates_dict = cls._get_dates_dict()
        all_dates = []
        for year_dates in dates_dict.values():
            all_dates.extend(year_dates)
        return sorted(all_dates)

    @classmethod
    def get_next_meeting(cls) -> Optional[date]:
        """Return the next upcoming FOMC meeting date."""
        upcoming = cls.get_upcoming_meetings(count=1)
        return upcoming[0] if upcoming else None

    @classmethod
    def days_until_next_meeting(cls) -> Optional[int]:
        """Days until next FOMC meeting."""
        next_mtg = cls.get_next_meeting()
        if next_mtg is None:
            return None
        return (next_mtg - date.today()).days

    @classmethod
    def _get_dates_dict(cls) -> Dict[int, List[date]]:
        """Get meeting dates, trying scrape first then fallback."""
        if cls._scraped_dates is not None:
            return cls._scraped_dates

        scraped = cls._scrape_from_fed()
        if scraped:
            cls._scraped_dates = scraped
            return scraped

        return cls.FALLBACK_DATES

    @classmethod
    def _scrape_from_fed(cls) -> Optional[Dict[int, List[date]]]:
        """Scrape FOMC meeting dates from the Federal Reserve website."""
        try:
            import urllib.request

            url = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                html = resp.read().decode("utf-8", errors="replace")

            # Parse meeting dates from the HTML
            # The page contains entries like "January 28-29" or "March 18-19*"
            # grouped by year panels
            dates_dict: Dict[int, List[date]] = {}

            # Find year sections
            year_pattern = re.compile(r'class="panel-heading"[^>]*>\s*(\d{4})\s*<')
            # Find meeting date entries - various formats
            # "January 28-29" or "January 28-29*" (asterisk for SEP meetings)
            date_pattern = re.compile(
                r'(\w+)\s+(\d{1,2})(?:\s*-\s*(\d{1,2}))?\*?'
            )

            month_map = {
                "january": 1, "february": 2, "march": 3, "april": 4,
                "may": 5, "june": 6, "july": 7, "august": 8,
                "september": 9, "october": 10, "november": 11, "december": 12,
            }

            # Split by year panels
            year_sections = re.split(r'class="panel-heading"', html)

            for section in year_sections[1:]:  # Skip before first panel
                year_match = re.search(r'>\s*(\d{4})\s*<', section)
                if not year_match:
                    continue
                year = int(year_match.group(1))

                # Find meeting row entries
                meeting_rows = re.findall(
                    r'class="fomc-meeting__date"[^>]*>(.*?)</span>',
                    section, re.DOTALL
                )

                year_dates = []
                for row in meeting_rows:
                    row_clean = re.sub(r'<[^>]+>', ' ', row).strip()
                    row_clean = row_clean.replace('*', '').strip()

                    for match in date_pattern.finditer(row_clean):
                        month_name = match.group(1).lower()
                        if month_name not in month_map:
                            continue
                        month = month_map[month_name]
                        # Use last day of meeting (decision day)
                        day_end = match.group(3) or match.group(2)
                        try:
                            meeting_date = date(year, month, int(day_end))
                            year_dates.append(meeting_date)
                        except ValueError:
                            continue

                if year_dates:
                    dates_dict[year] = sorted(year_dates)

            if dates_dict:
                return dates_dict

        except Exception:
            pass

        return None
