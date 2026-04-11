from datetime import date

from ga4_report.ga4_client import compute_date_ranges


def test_daily_ranges():
    current, previous = compute_date_ranges("daily", "previous_period", 1, None, ref_date=date(2026, 4, 11))
    assert current == (date(2026, 4, 10), date(2026, 4, 10))
    assert previous == (date(2026, 4, 9), date(2026, 4, 9))


def test_weekly_ranges():
    current, previous = compute_date_ranges("weekly", "previous_period", 1, None, ref_date=date(2026, 4, 11))
    assert current == (date(2026, 4, 4), date(2026, 4, 10))
    assert previous == (date(2026, 3, 28), date(2026, 4, 3))


def test_same_period_last_week():
    current, previous = compute_date_ranges("daily", "same_period_last_week", 1, None, ref_date=date(2026, 4, 11))
    assert current == (date(2026, 4, 10), date(2026, 4, 10))
    assert previous == (date(2026, 4, 3), date(2026, 4, 3))


def test_biweekly_ranges():
    current, previous = compute_date_ranges("biweekly", "previous_period", 1, None, ref_date=date(2026, 4, 11))
    assert current == (date(2026, 3, 28), date(2026, 4, 10))
    assert previous == (date(2026, 3, 14), date(2026, 3, 27))


def test_monthly_ranges():
    current, previous = compute_date_ranges("monthly", "previous_period", 1, None, ref_date=date(2026, 4, 11))
    assert current == (date(2026, 3, 12), date(2026, 4, 10))
    assert previous == (date(2026, 2, 10), date(2026, 3, 11))
