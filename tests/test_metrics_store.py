from datetime import date

from metrics_report.periods import Period
from metrics_report.store import DailyTotal, RankRow, Store


def _row(item: str, clicks: int, kind: str = "keyword") -> RankRow:
    return RankRow(kind, item, clicks, clicks * 10, 0.1, 3.5)


def test_ranks_roundtrip_and_overwrite(tmp_path):
    s = Store(tmp_path / "sub" / "m.db")
    snap = date(2026, 10, 30)
    s.save_ranks(snap, 7, [_row("a", 1), _row("b", 2), _row("/x", 3, "url")])
    s.save_ranks(snap, 7, [_row("c", 9)])

    assert s.ranks(snap, 7, "keyword") == [_row("c", 9)]
    assert s.ranks(snap, 7, "url") == []


def test_ranks_none_exposed_rank(tmp_path):
    s = Store(tmp_path / "m.db")
    r = RankRow("url", "/x", 1, 2, 0.5, None)
    s.save_ranks(date(2026, 10, 30), 7, [r])
    assert s.ranks(date(2026, 10, 30), 7, "url") == [r]


def test_daily_totals_upsert_and_range(tmp_path):
    s = Store(tmp_path / "m.db")
    days = [DailyTotal(date(2026, 10, d), d, d) for d in (1, 2, 3, 4)]
    s.save_daily_totals(days)
    s.save_daily_totals([DailyTotal(date(2026, 10, 2), 99, 98)])

    got = s.daily_totals(Period(date(2026, 10, 2), date(2026, 10, 3)))
    assert got == [
        DailyTotal(date(2026, 10, 2), 99, 98),
        DailyTotal(date(2026, 10, 3), 3, 3),
    ]


def test_latest_rank_snapshot(tmp_path):
    s = Store(tmp_path / "m.db")
    assert s.latest_rank_snapshot(7, date(2026, 11, 1)) is None

    for d in (10, 20, 30):
        s.save_ranks(date(2026, 10, d), 7, [_row("a", 1)])
    s.save_ranks(date(2026, 10, 25), 30, [_row("a", 1)])

    assert s.latest_rank_snapshot(7, date(2026, 10, 30)) == date(2026, 10, 20)
    assert s.latest_rank_snapshot(7, date(2026, 11, 1)) == date(2026, 10, 30)
    assert s.latest_rank_snapshot(7, date(2026, 10, 10)) is None


def test_run_done_only_when_ok(tmp_path):
    s = Store(tmp_path / "m.db")
    assert not s.run_done("weekly", "L")

    s.mark_run("weekly", "L", "failed", "boom")
    assert not s.run_done("weekly", "L")

    s.mark_run("weekly", "L", "ok")
    assert s.run_done("weekly", "L")
    assert not s.run_done("monthly", "L")
