from datetime import date

from metrics_report.periods import Period, weekly_period, previous_period, monthly_period, weekly_label, monthly_label


def test_weekly_on_saturday():
    assert weekly_period(date(2026, 10, 31)) == Period(date(2026, 10, 24), date(2026, 10, 30))


def test_weekly_late_run_keeps_same_week():
    assert weekly_period(date(2026, 11, 2)) == Period(date(2026, 10, 24), date(2026, 10, 30))


def test_weekly_on_friday_uses_previous_week():
    assert weekly_period(date(2026, 11, 6)) == Period(date(2026, 10, 24), date(2026, 10, 30))


def test_previous_weekly():
    assert previous_period(Period(date(2026, 10, 24), date(2026, 10, 30))) == Period(date(2026, 10, 17), date(2026, 10, 23))


def test_monthly_and_previous():
    m = monthly_period(date(2026, 11, 1))
    assert m == Period(date(2026, 10, 1), date(2026, 10, 31))
    assert previous_period(m) == Period(date(2026, 9, 1), date(2026, 9, 30))


def test_monthly_february():
    assert monthly_period(date(2027, 3, 1)) == Period(date(2027, 2, 1), date(2027, 2, 28))


def test_labels():
    assert weekly_label(Period(date(2026, 10, 24), date(2026, 10, 30))) == "[주간] 2026-10-24 ~ 10-30"
    assert monthly_label(Period(date(2026, 10, 1), date(2026, 10, 31))) == "[월간] 2026-10"
