"""Report period calculation (weekly Sat-Fri, monthly calendar month)."""
from __future__ import annotations

import calendar
from datetime import date, timedelta
from typing import NamedTuple

FRIDAY = 4
WEEK_DAYS = 7


class Period(NamedTuple):
    start: date
    end: date


def weekly_period(run_date: date) -> Period:
    # Most recent Friday strictly before run_date (today's Friday is incomplete)
    back = (run_date.weekday() - FRIDAY) % WEEK_DAYS or WEEK_DAYS
    end = run_date - timedelta(days=back)
    return Period(end - timedelta(days=WEEK_DAYS - 1), end)


def _month(year: int, month: int) -> Period:
    last = calendar.monthrange(year, month)[1]
    return Period(date(year, month, 1), date(year, month, last))


def monthly_period(run_date: date) -> Period:
    prev_end = run_date.replace(day=1) - timedelta(days=1)
    return _month(prev_end.year, prev_end.month)


def _is_month(p: Period) -> bool:
    return p == _month(p.start.year, p.start.month)


def previous_period(p: Period) -> Period:
    if _is_month(p):
        return monthly_period(p.start)
    days = (p.end - p.start).days + 1
    return Period(p.start - timedelta(days=days), p.start - timedelta(days=1))


def weekly_label(p: Period) -> str:
    return f"[주간] {p.start:%Y-%m-%d} ~ {p.end:%m-%d}"


def monthly_label(p: Period) -> str:
    return f"[월간] {p.start:%Y-%m}"
