import json
from datetime import date

from metrics_report.metrics import Delta, NaverSection, Report
from metrics_report.periods import Period
from metrics_report.render import render_confluence, render_glossary, render_slack
from metrics_report.store import RankRow

P = Period(date(2026, 10, 24), date(2026, 10, 30))
W = Period(date(2026, 10, 2), date(2026, 10, 31))
LINK = "https://wiki/report"


def naver(kw="진성준"):
    d = Delta(98000, 90000, 8.9)
    c = Delta(0.003, 0.004, -25)
    row = RankRow("keyword", kw, 34, 1000, 0.034, 3.2)
    u = RankRow("url", "https://x.com/a%20b/?q=1", 10, 500, 0.02, None)
    return NaverSection(W, d, d, c, [row], [(u, 0.4)], [(kw, 34)], [row])


def report(naver_sec=None, **amp):
    base = {
        "wau": Delta(545, 422, 29.1),
        "new_users": Delta(520, None, None),
        "revisit_rate": Delta(0.06, 0.048, 25.0),
        "naver_share": Delta(0.78, 0.7, 11.0),
    }
    base.update(amp)
    return Report("weekly", P, "[주간] 2026-10-24 ~ 10-30", base, naver_sec, unsupported=["로그인 사용자"])


def slack_text(r):
    return json.dumps(render_slack(r, LINK), ensure_ascii=False)


def test_slack_contains_link_and_lines():
    t = slack_text(report(naver()))
    assert "👥" in t and "🔍" in t and LINK in t
    assert "WAU 545 (▲29%)" in t
    assert "재방문율 6.0% (▲1.2%p)" in t
    assert "검색 노출 9.8만" in t
    assert "CTR 0.3% (▼0.1%p)" in t
    assert "10/24~10/30" in t


def test_slack_skips_none_metric():
    assert "재방문율" not in slack_text(report(naver(), revisit_rate=None))


def test_slack_new_when_no_previous():
    assert "신규 520" in slack_text(report(naver()))
    assert "WAU 545 (신규)" in slack_text(report(naver(), wau=Delta(545, None, None)))


def test_slack_naver_failed():
    assert "네이버 데이터 수집 실패" in slack_text(report(None))


def test_confluence_shows_naver_window_and_failure():
    assert "10-02 ~ 10-31" in render_confluence(report(naver()), None)
    html = render_confluence(report(None), None)
    assert "수집 실패" in html
    assert "로그인 사용자" in html


def test_confluence_escapes_html():
    html = render_confluence(report(naver("<b>")), "https://g")
    assert "&lt;b&gt;" in html and "<b>" not in html
    assert 'href="https://g"' in html
    assert "/a b" in html


def test_glossary_has_okr_links():
    html = render_glossary({"KR 3.1": "https://k/1", "KR 3.1.1": "https://k/2"})
    assert 'href="https://k/1"' in html and "KR 3.1.1" in html
    assert "m.search.naver.com" in html


def test_slack_escapes_keyword():
    n = naver()
    n.rising = [("<!channel>&", 5)]
    t = render_slack(report(n), LINK)["blocks"][1]["text"]["text"]
    assert "&lt;!channel&gt;&amp;" in t and "<!channel>" not in t
    assert f"<{LINK}|Confluence>" in t


def test_ctr_drop_escaped_once_each():
    n = naver()
    n.rising = []
    n.top_urls = [(RankRow("url", "/a<b>", 1, 200, 0.01, None), None)]
    n.prev_urls = [RankRow("url", "/a<b>", 1, 200, 0.03, None)]
    r = report(n)
    t = render_slack(r, LINK)["blocks"][1]["text"]["text"]
    assert "/a&lt;b&gt;" in t and "&amp;lt;" not in t
    from metrics_report.insights import build_insights
    r.insights = build_insights(r)
    html = render_confluence(r, None)
    assert "CTR 하락: /a&lt;b&gt;" in html and "&amp;lt;" not in html


def test_glossary_has_terms():
    html = render_glossary({})
    for term in ("로그인 사용자", "네이버 유입 재방문율", "그 외 재방문율", "네이버 랜딩 재방문율", "급상승 키워드", "SEO 기회 키워드"):
        assert term in html


def test_landing_name_matches():
    assert "네이버 랜딩 재방문율" in render_confluence(report(naver()), None)


def test_confluence_rising_placeholder_when_empty():
    n = naver()
    n.rising = []
    assert "비교 기준 없음" in render_confluence(report(n), None)
    assert "비교 기준 없음" not in render_confluence(report(naver()), None)


def test_monthly_slack_omits_new_weekly_keeps():
    r = report(naver(), mau=Delta(900, 800, 12.5))
    r.kind = "monthly"
    assert "신규" not in slack_text(r)
    assert "신규 520" in slack_text(report(naver()))


def test_confluence_daily_dau_table_replaces_avg_row():
    r = report(naver(), dau_avg=Delta(150, 100, 50.0))
    r.daily_dau = [(date(2026, 10, 24), 111), (date(2026, 10, 25), 222)]
    html = render_confluence(r, None)
    assert "일별 DAU" in html
    assert "<td>10-24 (토)</td><td>111</td>" in html
    assert "<td>10-25 (일)</td><td>222</td>" in html
    assert "DAU (일평균)" not in html


def test_confluence_url_top_is_link():
    html = render_confluence(report(naver()), None)
    assert '<a href="https://x.com/a%20b/?q=1">' in html
    assert ">/a b" in html


def test_confluence_sources_section():
    from datetime import datetime
    from metrics_report.build import KST
    r = report(naver())
    r.project_id, r.site = "854978", "https://www.noo9.kr"
    r.amp_links = {"Amplitude 홈": "https://app.amplitude.com/analytics/delicate-lab-505752/home", "리텐션": "https://amp/r"}
    r.generated_at = datetime(2026, 11, 1, 9, 5, tzinfo=KST)
    html = render_confluence(r, None)
    assert "데이터 출처" in html and "2026-11-01 09:05 KST" in html
    assert "누구뽑지 프로젝트(854978)" in html
    assert "2026-10-24 ~ 2026-10-30 (비교 2026-10-17 ~ 2026-10-23)" in html
    assert 'href="https://app.amplitude.com/analytics/delicate-lab-505752/home"' in html
    assert 'href="https://amp/r">리텐션' in html
    assert "console/site/report/expose?site=https%3A%2F%2Fwww.noo9.kr" in html
    assert "키워드·URL 목록 기간 10-02 ~ 10-31" in html
    assert "bracket retention" in html


def test_confluence_sources_naver_failed():
    html = render_confluence(report(None), None)
    src = html.split("데이터 출처")[1]
    assert "웹 검색 노출/클릭 · 수집 실패" in src.replace("\n", " ").replace("  ", " ")
