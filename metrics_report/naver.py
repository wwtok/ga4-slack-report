"""Naver Search Advisor client (internal API, called through Aside)."""
from __future__ import annotations

import json
import subprocess
from datetime import date, datetime
from pathlib import Path
from typing import Literal
from urllib.parse import quote

from metrics_report.config import Settings
from metrics_report.store import DailyTotal, RankRow

ASIDE_TIMEOUT_SEC = 150
SCRIPT = Path(__file__).with_name("naver_fetch.js")
PERCENT = 100
STDERR_CHARS = 200
DATE_FMT = "%Y%m%d"


class NaverCollectError(Exception):
    pass


class Dated(list):
    """Rows plus the API's meta.latestDate (data freshness)."""

    latest: date | None = None


def _dated(rows: list, payload: dict) -> Dated:
    out = Dated(rows)
    try:
        out.latest = datetime.strptime(payload["meta"]["latestDate"], DATE_FMT).date()
    except (KeyError, TypeError, ValueError) as e:
        raise NaverCollectError(f"unexpected response: no meta.latestDate ({e!r})") from e
    return out


def latest_of(rows, fallback: date) -> date:
    return getattr(rows, "latest", None) or fallback


def _call(settings: Settings, window_days: int, top_n: int) -> dict:
    script = (
        SCRIPT.read_text(encoding="utf-8")
        .replace("{{SITE_ENC}}", quote(settings.naver_site, safe=""))
        .replace("{{SITE_HASH}}", settings.naver_site_hash)
        .replace("{{WINDOW}}", str(window_days))
        .replace("{{TOP_N}}", str(top_n))
    )
    cmd = ["aside", "repl", "--account", settings.aside_account, script]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=ASIDE_TIMEOUT_SEC
        )
    except subprocess.TimeoutExpired as e:
        raise NaverCollectError("aside timeout") from e
    except OSError as e:
        raise NaverCollectError(f"aside failed: {e}") from e

    # aside prints status/timing lines around our JSON; take the last '{' line
    lines = [ln for ln in proc.stdout.splitlines() if ln.startswith("{")]
    if not lines:
        raise NaverCollectError(
            f"no JSON in aside output (returncode={proc.returncode}, "
            f"stderr={(proc.stderr or '')[:STDERR_CHARS]!r})"
        )
    try:
        payload = json.loads(lines[-1])
    except ValueError as e:
        raise NaverCollectError("invalid JSON") from e

    if "error" in payload:
        raise NaverCollectError(payload["error"])
    if payload.get("code") != 0:
        raise NaverCollectError(f"api code {payload.get('code')}: {payload.get('message')}")
    return payload


def _item(payload: dict) -> dict:
    items = payload.get("items") or []
    if not items:
        raise NaverCollectError("empty items")
    return items[0]


def parse_ranks(payload: dict, kind: Literal["keyword", "url"]) -> list[RankRow]:
    key = "querys" if kind == "keyword" else "urls"
    try:
        return [
            RankRow(
                kind=kind,
                item=r["key"],
                clicks=r["clickCount"],
                impressions=r["exposeCount"],
                ctr=r["ctr"] / PERCENT,  # API gives percent
                exposed_rank=r.get("exposedRank"),
            )
            for r in _item(payload)[key]
        ]
    except (KeyError, TypeError, ValueError) as e:
        raise NaverCollectError(f"unexpected response: {e!r}") from e


def parse_daily(payload: dict) -> list[DailyTotal]:
    try:
        rows = [
            DailyTotal(
                day=datetime.strptime(r["date"], DATE_FMT).date(),
                impressions=r["exposeCount"],
                clicks=r["clickCount"],
            )
            for r in _item(payload)["logs"]
        ]
    except (KeyError, TypeError, ValueError) as e:
        raise NaverCollectError(f"unexpected response: {e!r}") from e
    return sorted(rows, key=lambda r: r.day)


def fetch_ranks(
    settings: Settings, window_days: Literal[1, 7, 30, 90], top_n: int = 1000
) -> Dated:
    """Keyword and url rows together (store replaces snapshot as a whole)."""
    payload = _call(settings, window_days, top_n)
    return _dated(parse_ranks(payload, "keyword") + parse_ranks(payload, "url"), payload)


def fetch_daily_totals(
    settings: Settings, window_days: Literal[30, 90]
) -> Dated:
    payload = _call(settings, window_days, 1)
    return _dated(parse_daily(payload), payload)
