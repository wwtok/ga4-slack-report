from datetime import date
from pathlib import Path

import pytest

from metrics_report.build import build_report, write_dry_run
from metrics_report.config import Secrets, Settings
from metrics_report.naver import NaverCollectError
from metrics_report.periods import Period
from metrics_report.store import DailyTotal, RankRow, Store

RUN = date(2026, 11, 2)


class FakeAmp:
    def active_users(self, p):
        return 200, [100, 200]

    def new_users(self, p):
        return 50

    def pageviews(self, p):
        return (1000, 100)

    def sessions(self, p):
        return 300

    def users_by_referring_domain(self, p):
        return {"search.naver.com": 100}

    def next_period_retention(self, c, interval, source=None):
        return 0.1

    def day_n_retention(self, c, days=(1, 7)):
        return {1: 0.2, 7: 0.1}

    def landing_retention_by_path(self, c, paths):
        return {p: 0.3 for p in paths}


@pytest.fixture
def settings(tmp_path):
    return Settings("1", "https://x.kr", "h", "u", "b", "k", None, tmp_path / "data",
                    tmp_path / "out", Secrets("a", "b", "c", "d", "e"))


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "s.db")


def fake_ranks(settings, window_days, top_n=1000):
    return [RankRow("keyword", "kw", 10, 1000, 0.01, 2.0),
            RankRow("url", "https://x.kr/a%20b", 5, 500, 0.01, 2.0)]


def fake_totals(settings, window_days):
    return [DailyTotal(date(2026, 10, 24), 100, 5)]


def failing(*a, **k):
    raise NaverCollectError("boom")


def build(settings, store, ranks=fake_ranks, totals=fake_totals, kind="weekly"):
    return build_report(kind, RUN, settings, store, FakeAmp(), ranks, totals)


def test_weekly_report_period_and_label(settings, store):
    r = build(settings, store)
    assert (r.period.start, r.period.end) == (date(2026, 10, 24), date(2026, 10, 30))
    assert r.label == "[주간] 2026-10-24 ~ 10-30"
    assert r.amplitude["wau"].current == 200
    assert r.amplitude["mau"] is None
    assert r.amplitude["signups"] is None
    assert r.naver.impressions.current == 100


def test_naver_failure_keeps_report(settings, store):
    r = build(settings, store, ranks=failing)
    assert r.naver is None
    assert r.amplitude["dau_avg"].current == 150
    assert "네이버 데이터 수집 실패" in r.insights


def test_first_week_no_previous_snapshot(settings, store):
    r = build(settings, store)
    assert r.naver.rising == [("kw", 10)]
    assert r.naver.prev_urls == []


def test_dry_run_writes_two_files(settings, store):
    d = write_dry_run(build(settings, store), settings)
    assert sorted(p.name for p in d.iterdir()) == ["confluence.html", "slack.json"]
    assert d.parent == settings.out_dir
    assert "/" not in d.name


def test_wau_from_period_total_not_below_new(settings, store):
    r = build(settings, store)
    assert r.amplitude["new_users"].current <= r.amplitude["wau"].current == 200


def test_monthly_branch(settings, store):
    r = build(settings, store, kind="monthly")
    a = r.amplitude
    assert a["wau"] is None and a["mau"].current == 200
    assert a["stickiness"].current == a["dau_avg"].current / a["mau"].current
    assert r.naver.window == Period(date(2026, 10, 3), date(2026, 11, 1))


def test_late_run_naver_window_is_rolling(settings, store):
    r = build(settings, store)
    assert r.naver.window == Period(date(2026, 10, 26), date(2026, 11, 1))


def test_zero_denominators_give_none(settings, store):
    class ZeroAmp(FakeAmp):
        def active_users(self, p):
            return 0, []

        def pageviews(self, p):
            return (0, 0)

    r = build_report("monthly", RUN, settings, store, ZeroAmp(), fake_ranks, fake_totals)
    a = r.amplitude
    assert a["dau_avg"] is None and a["stickiness"] is None
    assert a["pv_per_user"] is None and a["naver_share"] is None


def test_empty_daily_totals_is_none_and_renders(settings, store):
    r = build(settings, store, totals=lambda s, w: [])
    assert r.naver.impressions is None and r.naver.clicks is None and r.naver.ctr is None
    d = write_dry_run(r, settings)
    assert (d / "slack.json").exists()


def test_previous_snapshot_is_latest_earlier(settings, store):
    store.save_ranks(date(2026, 10, 3), 30, [RankRow("url", "https://x.kr/old", 1, 1, 1.0, None)])
    r = build(settings, store, kind="monthly")
    assert [u.item for u in r.naver.prev_urls] == ["https://x.kr/old"]
