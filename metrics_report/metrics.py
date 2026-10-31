"""Pure metric computations and the report model (no I/O)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, NamedTuple
from urllib.parse import unquote, urlsplit

from metrics_report.periods import Period
from metrics_report.store import DailyTotal, RankRow

NAVER_DOMAINS = ("m.search.naver.com", "search.naver.com")
PCT = 100


class Delta(NamedTuple):
    current: float
    previous: float | None
    pct: float | None


def delta(current: float, previous: float | None) -> Delta:
    if not previous:
        return Delta(current, previous, None)
    return Delta(current, previous, (current - previous) / previous * PCT)


def normalize_path(url_or_path: str) -> str:
    # Drops scheme/domain/query/fragment, decodes %XX, strips trailing "/" (except root)
    path = unquote(urlsplit(url_or_path).path)
    return path.rstrip("/") or "/"


def naver_share(by_domain: dict[str, int], active_users: int) -> float | None:
    if not active_users:
        return None
    return sum(by_domain.get(d, 0) for d in NAVER_DOMAINS) / active_users


def naver_totals(rows: list[DailyTotal]) -> tuple[int, int, float]:
    imp = sum(r.impressions for r in rows)
    clicks = sum(r.clicks for r in rows)
    return imp, clicks, clicks / imp if imp else 0.0


def rising_keywords(current: list[RankRow], previous: list[RankRow], n: int = 5) -> list[tuple[str, int]]:
    prev = {r.item: r.clicks for r in previous}
    gains = [(r.item, r.clicks - prev.get(r.item, 0)) for r in current]
    gains = [g for g in gains if g[1] > 0]
    return sorted(gains, key=lambda g: g[1], reverse=True)[:n]


def seo_opportunities(rows: list[RankRow], n: int = 5, max_ctr: float = 0.01) -> list[RankRow]:
    low = [r for r in rows if r.ctr < max_ctr]
    return sorted(low, key=lambda r: r.impressions, reverse=True)[:n]


def top_by_clicks(rows: list[RankRow], kind: str, n: int = 10) -> list[RankRow]:
    same = [r for r in rows if r.kind == kind]
    return sorted(same, key=lambda r: r.clicks, reverse=True)[:n]


@dataclass
class NaverSection:
    window: Period
    impressions: Delta
    clicks: Delta
    ctr: Delta
    top_keywords: list[RankRow]
    top_urls: list[tuple[RankRow, float | None]]
    rising: list[tuple[str, int]]
    seo: list[RankRow]
    prev_urls: list[RankRow] = field(default_factory=list)


@dataclass
class Report:
    kind: Literal["weekly", "monthly"]
    period: Period
    label: str
    # keys: dau_avg, wau, mau, new_users, signups, pageviews, pv_per_user, sessions,
    # revisit_rate, revisit_naver, revisit_other, d1, d7, naver_share, stickiness
    amplitude: dict[str, Delta | None]
    naver: NaverSection | None
    insights: list[str] = field(default_factory=list)
    unsupported: list[str] = field(default_factory=list)
