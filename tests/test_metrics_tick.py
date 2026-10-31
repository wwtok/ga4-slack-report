from datetime import date, datetime

import pytest

from metrics_report.metrics import Report
from metrics_report.periods import monthly_label, monthly_period, weekly_label, weekly_period
from metrics_report.store import Store
from metrics_report.tick import KST, Deps, tick


def at(y, m, d, h, mi=0):
    return datetime(y, m, d, h, mi, tzinfo=KST)


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "s.db")


class Fake:
    def __init__(self, store, fail_collect=False):
        self.store, self.fail_collect = store, fail_collect
        self.collected, self.published, self.alerts = [], [], []

    def collect(self, d):
        if self.fail_collect:
            raise RuntimeError("naver down")
        self.collected.append(d)

    def build(self, kind, d):
        p = monthly_period(d) if kind == "monthly" else weekly_period(d)
        label = monthly_label(p) if kind == "monthly" else weekly_label(p)
        return Report(kind, p, label, {}, None)

    def publish(self, r):
        self.published.append(r.kind)
        self.store.mark_run("publish", r.label, "ok")
        return "url"

    def deps(self):
        return Deps(self.collect, self.build, self.publish,
                    lambda s, r: self.alerts.append((s, r)))


def run(f, store, now):
    return tick(now, None, store, f.deps())


def test_tick_saturday_runs_weekly_once(store):
    f = Fake(store)
    assert "weekly" in run(f, store, at(2026, 10, 31, 10))
    assert "weekly" not in run(f, store, at(2026, 10, 31, 11))
    assert f.published.count("weekly") == 1


def test_tick_saturday_before_nine_skips_weekly(store):
    f = Fake(store)
    assert "weekly" not in run(f, store, at(2026, 10, 31, 8))


def test_tick_before_noon_skips_collect(store):
    f = Fake(store)
    assert "collect" not in run(f, store, at(2026, 10, 30, 11))
    assert "collect" in run(f, store, at(2026, 10, 30, 12))
    assert "collect" not in run(f, store, at(2026, 10, 30, 13))


def test_tick_first_of_month_runs_monthly(store):
    f = Fake(store)
    assert "monthly" not in run(f, store, at(2026, 11, 1, 8, 30))
    assert "monthly" in run(f, store, at(2026, 11, 1, 9, 30))


def test_tick_failure_alerts_and_continues(store):
    f = Fake(store, fail_collect=True)
    ran = run(f, store, at(2026, 10, 31, 13))
    assert f.alerts == [("collect", "naver down")]
    assert "weekly" in ran and "collect" not in ran


def test_tick_alert_once_per_day(store):
    f = Fake(store, fail_collect=True)
    run(f, store, at(2026, 10, 31, 13))
    run(f, store, at(2026, 10, 31, 14))
    assert len(f.alerts) == 1
    run(f, store, at(2026, 11, 2, 13))
    assert len(f.alerts) == 2
