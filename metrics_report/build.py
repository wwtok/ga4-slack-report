"""Assemble reports from Amplitude + Naver data; dry-run output."""
from __future__ import annotations

import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Literal

from metrics_report.amplitude import AmplitudeClient
from metrics_report.config import Settings
from metrics_report.insights import build_insights
from metrics_report.metrics import (
    Delta, NaverSection, Report, delta, naver_share, naver_totals,
    normalize_path, rising_keywords, seo_opportunities, top_by_clicks,
)
from metrics_report.naver import NaverCollectError, fetch_daily_totals, fetch_ranks
from metrics_report.periods import (
    Period, monthly_label, monthly_period, previous_period, weekly_label, weekly_period,
)
from metrics_report.render import render_confluence, render_slack
from metrics_report.store import Store

WEEK_DAYS = 7
MONTH_DAYS = 30
DATA_LAG_DAYS = 1
TOP_N = 10
DAILY_WINDOW = 1
TOTALS_KEEP_DAILY = 30
TOTALS_KEEP_BACKFILL = 90
DRY_RUN_PAGE_URL = "https://example.invalid/dry-run"
UNSAFE_NAME = re.compile(r"[^0-9A-Za-z가-힣._-]")
NO_SIGNUPS = "가입 수 (Signed Up 이벤트 없음)"


def _d(cur: float | None, prev: float | None = None) -> Delta | None:
    return None if cur is None else delta(cur, prev)


def _mean(xs: list[int]) -> float | None:
    return sum(xs) / len(xs) if xs else None


class _Memo:
    """Each distinct Amplitude call runs once per build."""

    def __init__(self, amp: AmplitudeClient) -> None:
        self._amp = amp
        self._cache: dict = {}

    def __getattr__(self, name: str):
        fn = getattr(self._amp, name)

        def call(*args, **kw):
            key = (name, repr(args), repr(kw))
            if key not in self._cache:
                self._cache[key] = fn(*args, **kw)
            return self._cache[key]

        return call


def _amplitude(
    kind: str, p: Period, amp: AmplitudeClient
) -> dict[str, Delta | None]:
    monthly = kind == "monthly"
    interval = MONTH_DAYS if monthly else WEEK_DAYS
    amp = _Memo(amp)
    pp = previous_period(p)
    c, cp = pp, previous_period(pp)  # most recent mature cohort

    def pair(fn):
        return fn(p), fn(pp)

    def both(fn):
        return _d(*pair(fn))

    def pv_per_user(q: Period) -> float | None:
        total, uniq = amp.pageviews(q)
        return total / uniq if uniq else None

    def long_window(q: Period) -> int | None:
        return amp.active_users(q)[0]  # uniques over the whole period (WAU/MAU)

    def dau(q: Period) -> float | None:
        return _mean(amp.active_users(q)[1])

    def share(q: Period) -> float | None:
        return naver_share(amp.users_by_referring_domain(q), long_window(q))

    def revisit(cohort: Period, source=None) -> float | None:
        return amp.next_period_retention(cohort, interval, source)

    dn = amp.day_n_retention(c)
    dau_cur, dau_prev = pair(dau)
    win_cur = long_window(p)
    stickiness = dau_cur / win_cur if monthly and win_cur and dau_cur is not None else None

    return {
        "dau_avg": _d(dau_cur, dau_prev),
        "wau": None if monthly else both(long_window),
        "mau": both(long_window) if monthly else None,
        "new_users": both(amp.new_users),
        "signups": None,
        "pageviews": both(lambda q: amp.pageviews(q)[0]),
        "pv_per_user": both(pv_per_user),
        "sessions": both(amp.sessions),
        "revisit_rate": _d(revisit(c), revisit(cp)),
        "revisit_naver": _d(revisit(c, "naver")),
        "revisit_other": _d(revisit(c, "other")),
        "d1": _d(dn[1]),
        "d7": _d(dn[7]),
        "naver_share": both(share),
        "stickiness": _d(stickiness),
    }


def _totals_deltas(cur: list, prev: list) -> tuple[Delta | None, ...]:
    # no stored days for the period -> unknown (None), not zero
    if not cur:
        return (None, None, None)
    p = naver_totals(prev) if prev else (None, None, None)
    return tuple(delta(c, q) for c, q in zip(naver_totals(cur), p))


def _naver_section(
    kind: str, p: Period, run_date: date, settings: Settings, store: Store,
    amp: AmplitudeClient, naver_fetch, totals_fetch,
) -> NaverSection:
    days = MONTH_DAYS if kind == "monthly" else WEEK_DAYS
    snap = run_date - timedelta(days=DATA_LAG_DAYS)
    rows = naver_fetch(settings, days)
    store.save_ranks(snap, days, rows)
    store.save_daily_totals(totals_fetch(settings, TOTALS_KEEP_BACKFILL))

    # previous snapshot: latest strictly earlier one of the same window
    prev_snap = store.latest_rank_snapshot(days, before=snap)
    prev = (
        [r for k in ("keyword", "url") for r in store.ranks(prev_snap, days, k)]
        if prev_snap else []
    )

    pp = previous_period(p)
    cur_rows, prev_rows = store.daily_totals(p), store.daily_totals(pp)
    totals = _totals_deltas(cur_rows, prev_rows)

    c = pp
    top = top_by_clicks(rows, "url", TOP_N)
    landing = amp.landing_retention_by_path(c, [normalize_path(u.item) for u in top])
    kw = [r for r in rows if r.kind == "keyword"]
    prev_kw = [r for r in prev if r.kind == "keyword"]

    return NaverSection(
        window=Period(snap - timedelta(days=days - 1), snap),
        impressions=totals[0],
        clicks=totals[1],
        ctr=totals[2],
        top_keywords=top_by_clicks(rows, "keyword", TOP_N),
        top_urls=[(u, landing.get(normalize_path(u.item))) for u in top],
        rising=rising_keywords(kw, prev_kw) if prev else [],  # no baseline -> hide
        seo=seo_opportunities(kw),
        prev_urls=[r for r in prev if r.kind == "url"],
    )


def build_report(
    kind: Literal["weekly", "monthly"],
    run_date: date,
    settings: Settings,
    store: Store,
    amp: AmplitudeClient,
    naver_fetch=fetch_ranks,
    naver_totals_fetch=fetch_daily_totals,
) -> Report:
    amp = _Memo(amp)  # shared with _amplitude so daily uniques are fetched once
    monthly = kind == "monthly"
    p = monthly_period(run_date) if monthly else weekly_period(run_date)
    report = Report(
        kind=kind,
        period=p,
        label=monthly_label(p) if monthly else weekly_label(p),
        amplitude=_amplitude(kind, p, amp),
        naver=None,
        unsupported=[NO_SIGNUPS],
    )
    days = (p.start + timedelta(days=i) for i in range((p.end - p.start).days + 1))
    report.daily_dau = list(zip(days, amp.active_users(p)[1]))
    try:
        report.naver = _naver_section(
            kind, p, run_date, settings, store, amp, naver_fetch, naver_totals_fetch
        )
    except NaverCollectError as e:
        print(f"naver collect failed: {e}", file=sys.stderr)  # insights add NAVER_FAILED

    report.insights = build_insights(report)
    return report


def collect_daily(settings: Settings, store: Store, today: date) -> None:
    snap = today - timedelta(days=DATA_LAG_DAYS)
    store.save_ranks(snap, DAILY_WINDOW, fetch_ranks(settings, DAILY_WINDOW))
    store.save_daily_totals(fetch_daily_totals(settings, TOTALS_KEEP_DAILY))


def backfill(settings: Settings, store: Store, today: date) -> None:
    snap = today - timedelta(days=DATA_LAG_DAYS)
    store.save_ranks(snap, TOTALS_KEEP_BACKFILL, fetch_ranks(settings, TOTALS_KEEP_BACKFILL))
    store.save_daily_totals(fetch_daily_totals(settings, TOTALS_KEEP_BACKFILL))


def write_dry_run(report: Report, settings: Settings) -> Path:
    out = settings.out_dir / UNSAFE_NAME.sub("_", report.label)
    out.mkdir(parents=True, exist_ok=True)
    slack = render_slack(report, page_url=DRY_RUN_PAGE_URL)
    (out / "slack.json").write_text(json.dumps(slack, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "confluence.html").write_text(
        render_confluence(report, glossary_url=None), encoding="utf-8"
    )
    return out
