from datetime import date

from metrics_report.metrics import (
    delta,
    naver_share,
    naver_totals,
    normalize_path,
    rising_keywords,
    seo_opportunities,
    top_by_clicks,
)
from metrics_report.store import DailyTotal, RankRow


def test_normalize_path_joins_encoded_url_and_plain_path():
    a = normalize_path("https://www.noo9.kr/politicians/519-%EC%A7%84%EC%84%B1%EC%A4%80/?ref=x")
    b = normalize_path("/politicians/519-진성준")
    assert a == b == "/politicians/519-진성준"


def test_normalize_root():
    assert normalize_path("https://www.noo9.kr/") == "/"


def test_delta_no_previous():
    assert delta(10, None).pct is None and delta(10, 0).pct is None


def test_delta_pct():
    assert delta(150, 100).pct == 50.0


def test_naver_share_sums_both_domains():
    assert naver_share({"m.search.naver.com": 60, "search.naver.com": 18, "www.google.com": 5}, 100) == 0.78


def test_naver_share_zero_users():
    assert naver_share({"search.naver.com": 1}, 0) is None


def test_naver_totals():
    rows = [DailyTotal(date(2026, 1, 1), 100, 5), DailyTotal(date(2026, 1, 2), 100, 15)]
    assert naver_totals(rows) == (200, 20, 0.1)
    assert naver_totals([]) == (0, 0, 0.0)


def test_rising_includes_new_keyword_and_skips_drops():
    cur = [RankRow("keyword", "A", 40, 100, 0.4, None), RankRow("keyword", "B", 5, 50, 0.1, None)]
    prev = [RankRow("keyword", "B", 9, 60, 0.15, None)]
    assert rising_keywords(cur, prev) == [("A", 40)]


def test_seo_opportunities_low_ctr_by_impressions():
    rows = [RankRow("keyword", "X", 18, 37847, 0.0005, None), RankRow("keyword", "Y", 34, 89, 0.38, None),
            RankRow("keyword", "Z", 10, 4346, 0.002, None)]
    assert [r.item for r in seo_opportunities(rows)] == ["X", "Z"]


def test_top_by_clicks_filters_kind():
    rows = [RankRow("keyword", "A", 1, 1, 1.0, None), RankRow("url", "u", 9, 9, 1.0, None),
            RankRow("keyword", "B", 5, 5, 1.0, None)]
    assert [r.item for r in top_by_clicks(rows, "keyword")] == ["B", "A"]
