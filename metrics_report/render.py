"""Slack Block Kit + Confluence storage XHTML renderers.

All display formats live here (see the fmt_* helpers) so they are easy to change.
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from jinja2 import Environment, FileSystemLoader

from metrics_report.insights import build_insights
from metrics_report.metrics import Delta, Report, normalize_path
from metrics_report.periods import previous_period

PCT = 100
MAN = 10_000
NEW = "신규"
UP, DOWN, FLAT = "▲", "▼", "–"
# fractions shown as percent, change as %p
RATE_KEYS = {"revisit_rate", "revisit_naver", "revisit_other", "d1", "d7", "naver_share", "stickiness"}
WEEKDAYS = "월화수목금토일"
NAVER_FAILED = "네이버 데이터 수집 실패"
SEARCHADVISOR_URL = "https://searchadvisor.naver.com/console/site/report/expose?site={site}"
GENERATED_FMT = "%Y-%m-%d %H:%M KST"

_env = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "templates"),
    autoescape=True,
    trim_blocks=True,
    lstrip_blocks=True,
)


def esc(text: str) -> str:
    # Slack mrkdwn: & first, then < >
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def fmt_count(v: float) -> str:
    return f"{v / MAN:.1f}만" if v >= MAN else f"{v:,.0f}"


def fmt_rate(v: float) -> str:
    return f"{v * PCT:.1f}%"


def _arrow(x: float) -> str:
    return UP if x > 0 else DOWN if x < 0 else FLAT


def chg_count(d: Delta) -> str:
    if d.pct is None:
        return NEW
    return f"{_arrow(d.pct)}{abs(d.pct):.0f}%"


def chg_rate(d: Delta) -> str:
    if d.previous is None:
        return NEW
    pp = (d.current - d.previous) * PCT
    return f"{_arrow(pp)}{abs(pp):.1f}%p"


def fmt_metric(key: str, d: Delta) -> tuple[str, str]:
    # -> (value, change)
    if key in RATE_KEYS:
        return fmt_rate(d.current), chg_rate(d)
    value = f"{d.current:,.1f}" if key == "pv_per_user" else fmt_count(d.current)
    return value, chg_count(d)


def _part(label: str, key: str, d: Delta | None, with_change: bool = True) -> str | None:
    if d is None:
        return None
    value, change = fmt_metric(key, d)
    return f"{label} {value} ({change})" if with_change else f"{label} {value}"


def _slack_lines(r: Report, page_url: str) -> tuple[str, list[str]]:
    monthly = r.kind == "monthly"
    if monthly:
        header = f"📊 누구뽑지 월간 리포트 ({r.period.start:%Y-%m})"
    else:
        header = f"📊 누구뽑지 주간 리포트 ({r.period.start:%m/%d}~{r.period.end:%m/%d})"
    a = r.amplitude
    users = [
        _part("MAU" if monthly else "WAU", "mau" if monthly else "wau", a.get("mau" if monthly else "wau")),
        None if monthly else _part("신규", "new_users", a.get("new_users"), with_change=False),
        _part("재방문율", "revisit_rate", a.get("revisit_rate")),
    ]
    lines = []
    users = [p for p in users if p]
    if users:
        lines.append("👥 " + " · ".join(users))

    n = r.naver
    if n is None:
        lines.append(f"🔍 {NAVER_FAILED}")
    else:
        share = a.get("naver_share")
        search = [
            f"네이버 유입 {fmt_rate(share.current)}" if share else None,
            f"검색 노출 {fmt_count(n.impressions.current)}" if n.impressions else None,
            f"CTR {fmt_rate(n.ctr.current)} ({chg_rate(n.ctr)})" if n.ctr else None,
        ]
        lines.append("🔍 " + " · ".join(p for p in search if p))

    insights = r.insights or build_insights(r)
    lines.append(f"💡 {esc(insights[0])}")
    lines.append(f"👉 전체 리포트: <{page_url}|Confluence>")
    return header, lines


def render_slack(report: Report, page_url: str) -> dict:
    header, lines = _slack_lines(report, page_url)
    return {
        "blocks": [
            {"type": "header", "text": {"type": "plain_text", "text": header}},
            {"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(lines)}},
        ]
    }


SECTIONS = (
    ("사용자", (("WAU", "wau"), ("MAU", "mau"),
              ("신규 사용자", "new_users"), ("로그인 사용자", "signups"))),
    ("참여", (("페이지뷰", "pageviews"), ("사용자당 페이지뷰", "pv_per_user"), ("세션", "sessions"))),
    ("리텐션", (("재방문율", "revisit_rate"), ("네이버 유입 재방문율", "revisit_naver"),
              ("그 외 재방문율", "revisit_other"), ("D1", "d1"), ("D7", "d7"),
              ("DAU/MAU", "stickiness"))),
    ("유입", (("네이버 유입 비중", "naver_share"),)),
)


def _sections(r: Report) -> list[dict]:
    out = []
    for title, metrics in SECTIONS:
        rows = []
        for label, key in metrics:
            d = r.amplitude.get(key)
            if d is not None:
                rows.append((label, *fmt_metric(key, d)))
        out.append({"title": title, "rows": rows})
    return out


def _naver_ctx(r: Report) -> dict | None:
    n = r.naver
    if n is None:
        return None
    w = n.window

    def row(x):
        return {"item": x.item, "clicks": x.clicks, "imp": fmt_count(x.impressions), "ctr": fmt_rate(x.ctr)}

    return {
        "window": f"{w.start:%m-%d} ~ {w.end:%m-%d}",
        "totals": [
            (label, fmt(d.current), chg(d))
            for label, d, fmt, chg in (
                ("노출", n.impressions, fmt_count, chg_count),
                ("클릭", n.clicks, fmt_count, chg_count),
                ("CTR", n.ctr, fmt_rate, chg_rate),
            )
            if d is not None
        ],
        "keywords": [row(x) for x in n.top_keywords],
        "rising": n.rising,
        "seo": [row(x) for x in n.seo],
        "urls": [
            {**row(x) | {"item": normalize_path(x.item), "href": x.item}, "revisit": fmt_rate(rv) if rv is not None else "-"}
            for x, rv in n.top_urls
        ],
    }


def _sources(r: Report) -> dict:
    p, pp = r.period, previous_period(r.period)
    return {
        "amp_project": r.project_id,
        "amp_links": r.amp_links,
        "p": f"{p.start} ~ {p.end}",
        "pp": f"{pp.start} ~ {pp.end}",
        "site": r.site,
        "naver_url": SEARCHADVISOR_URL.format(site=quote(r.site, safe="")),
        "generated_at": r.generated_at.strftime(GENERATED_FMT) if r.generated_at else None,
    }


def render_confluence(report: Report, glossary_url: str | None) -> str:
    return _env.get_template("confluence.html.j2").render(
        label=report.label,
        glossary_url=glossary_url,
        insights=report.insights or build_insights(report),
        sections=_sections(report),
        daily_dau=[(f"{d:%m-%d} ({WEEKDAYS[d.weekday()]})", n) for d, n in report.daily_dau],
        naver=_naver_ctx(report),
        unsupported=report.unsupported,
        src=_sources(report),
    )


def render_glossary(okr_links: dict[str, str]) -> str:
    return _env.get_template("glossary.html.j2").render(okr_links=okr_links)
