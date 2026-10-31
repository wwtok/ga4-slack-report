from datetime import date

from metrics_report.insights import build_insights
from metrics_report.metrics import Delta, NaverSection, Report
from metrics_report.periods import Period
from metrics_report.store import RankRow

P = Period(date(2026, 10, 24), date(2026, 10, 30))


def url(item, imp, ctr):
    return RankRow("url", item, int(imp * ctr), imp, ctr, None)


def naver(rising=(), top_urls=(), prev_urls=()):
    d = Delta(1, 1, 0)
    return NaverSection(P, d, d, d, [], [(u, None) for u in top_urls], list(rising), [], list(prev_urls))


def report(naver_sec=None, revisit=None):
    amp = {"revisit_rate": Delta(*revisit) if revisit else None}
    return Report("weekly", P, "l", amp, naver_sec)


def test_rising_first():
    r = report(naver([("진성준", 34)]))
    assert build_insights(r) == ["급상승 키워드: 진성준 (+34 클릭)"]


def test_revisit_change_threshold():
    assert build_insights(report(naver(), (0.349, 0.30, None))) == ["특이사항 없음"]
    assert build_insights(report(naver(), (0.35, 0.30, None))) == ["재방문율 +5.0%p"]
    assert build_insights(report(naver(), (0.25, 0.30, None))) == ["재방문율 -5.0%p"]


def test_ctr_drop():
    n = naver(
        top_urls=[url("https://x.com/a%20b/", 200, 0.01), url("/c", 50, 0.0)],
        prev_urls=[url("/a b", 200, 0.03), url("/c", 50, 0.5)],
    )
    assert build_insights(report(n)) == ["CTR 하락: /a b (3.0% → 1.0%)"]


def test_naver_failed_line():
    assert build_insights(report(None)) == ["네이버 데이터 수집 실패"]


def test_no_insight_fallback():
    assert build_insights(report(naver())) == ["특이사항 없음"]


def test_max_three():
    n = naver([("k", 5)], [url("/a", 200, 0.01)], [url("/a", 200, 0.03)])
    lines = build_insights(report(n, (0.5, 0.3, None)))
    assert len(lines) == 3
    assert lines[0].startswith("급상승")
    assert build_insights(report(n, (0.5, 0.3, None)), max_lines=2)[1].startswith("재방문율")
