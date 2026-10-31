"""Rule-based insight lines (priority order, first N)."""
from __future__ import annotations

from metrics_report.metrics import Report, normalize_path

REVISIT_PP = 5.0  # |Δ revisit_rate| threshold, percentage points
MIN_IMPRESSIONS = 100
NO_INSIGHT = "특이사항 없음"
NAVER_FAILED = "네이버 데이터 수집 실패"
PCT = 100


def _rising(r: Report) -> str | None:
    if not r.naver or not r.naver.rising:
        return None
    kw, n = r.naver.rising[0]
    return f"급상승 키워드: {kw} (+{n} 클릭)"


def _revisit(r: Report) -> str | None:
    d = r.amplitude.get("revisit_rate")
    if d is None or d.previous is None:
        return None
    pp = (d.current - d.previous) * PCT
    if abs(round(pp, 6)) < REVISIT_PP:
        return None
    return f"재방문율 {pp:+.1f}%p"


def _ctr_drop(r: Report) -> str | None:
    if not r.naver or not r.naver.prev_urls:
        return None
    prev = {normalize_path(p.item): p for p in r.naver.prev_urls}
    worst = None
    for row, _ in r.naver.top_urls:
        path = normalize_path(row.item)
        old = prev.get(path)
        if row.impressions < MIN_IMPRESSIONS or old is None:
            continue
        drop = old.ctr - row.ctr
        if drop > 0 and (worst is None or drop > worst[0]):
            worst = (drop, path, old.ctr, row.ctr)
    if worst is None:
        return None
    _, path, old, cur = worst
    return f"CTR 하락: {path} ({old * PCT:.1f}% → {cur * PCT:.1f}%)"


def _naver_failed(r: Report) -> str | None:
    return NAVER_FAILED if r.naver is None else None


def build_insights(report: Report, max_lines: int = 3) -> list[str]:
    rules = (_rising, _revisit, _ctr_drop, _naver_failed)
    lines = [x for x in (rule(report) for rule in rules) if x]
    return lines[:max_lines] or [NO_INSIGHT]
