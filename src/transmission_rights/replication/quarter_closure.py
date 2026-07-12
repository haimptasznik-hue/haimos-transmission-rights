"""Quarter closure helpers for persistent closed-quarter filtering.

These helpers make the pipeline treat a quarter as usable only after its
calendar end date has passed. That keeps partial quarters out of validation
and backtests until they close.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable, List, Optional


@dataclass(frozen=True)
class QuarterWindow:
    quarter: str
    start_date: date
    end_date: date


def parse_quarter(quarter: str) -> tuple[int, int]:
    if not quarter.startswith("C") or "Q" not in quarter:
        raise ValueError(f"Invalid quarter format: {quarter}")
    year_str, q_str = quarter[1:].split("Q", 1)
    year = int(year_str)
    quarter_no = int(q_str)
    if quarter_no < 1 or quarter_no > 4:
        raise ValueError(f"Invalid quarter number: {quarter}")
    return year, quarter_no


def quarter_window(quarter: str) -> QuarterWindow:
    year, quarter_no = parse_quarter(quarter)
    start_month = 1 + (quarter_no - 1) * 3
    start_date = date(year, start_month, 1)
    if quarter_no == 1:
        end_date = date(year, 3, 31)
    elif quarter_no == 2:
        end_date = date(year, 6, 30)
    elif quarter_no == 3:
        end_date = date(year, 9, 30)
    else:
        end_date = date(year, 12, 31)
    return QuarterWindow(quarter=quarter, start_date=start_date, end_date=end_date)


def is_quarter_closed(
    quarter: str,
    as_of: Optional[date] = None,
    close_grace_days: int = 0,
) -> bool:
    """Return True once the calendar quarter has ended (plus optional grace)."""
    as_of = as_of or date.today()
    window = quarter_window(quarter)
    return as_of > date.fromordinal(window.end_date.toordinal() + close_grace_days)


def closed_quarters(
    quarters: Iterable[str],
    as_of: Optional[date] = None,
    close_grace_days: int = 0,
) -> List[str]:
    """Filter quarters down to those that are fully closed."""
    as_of = as_of or date.today()
    return sorted(
        [q for q in quarters if is_quarter_closed(q, as_of=as_of, close_grace_days=close_grace_days)]
    )


def open_quarters(
    quarters: Iterable[str],
    as_of: Optional[date] = None,
    close_grace_days: int = 0,
) -> List[str]:
    as_of = as_of or date.today()
    return sorted(
        [q for q in quarters if not is_quarter_closed(q, as_of=as_of, close_grace_days=close_grace_days)]
    )