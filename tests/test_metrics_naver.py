import json
import subprocess
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from metrics_report import naver
from metrics_report.naver import NaverCollectError, parse_daily, parse_ranks
from metrics_report.store import DailyTotal

FIX = Path(__file__).parent / "fixtures"
SETTINGS = SimpleNamespace(
    naver_site="https://www.example.test", naver_site_hash="h", aside_account="u7"
)


def _load(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def _run_returning(stdout):
    def run(cmd, **kw):
        return subprocess.CompletedProcess(cmd, 0, stdout=stdout, stderr="")

    return run


def test_parse_ranks_keyword():
    rows = parse_ranks(_load("naver_rank.json"), "keyword")
    assert [r.item for r in rows] == ["테스트키워드A", "테스트키워드B"]
    assert rows[0].ctr == 0.2 and rows[0].clicks == 20 and rows[0].impressions == 100
    assert rows[0].exposed_rank == 1.4 and rows[1].exposed_rank is None


def test_parse_ranks_url():
    rows = parse_ranks(_load("naver_rank.json"), "url")
    assert len(rows) == 1 and rows[0].kind == "url"
    assert rows[0].item == "https://www.example.test/a"


def test_parse_daily():
    assert parse_daily(_load("naver_daily.json")) == [
        DailyTotal(date(2026, 1, 1), 80, 3),
        DailyTotal(date(2026, 1, 2), 90, 4),
    ]


def test_fetch_ranks_both_kinds_and_script(monkeypatch):
    seen = {}

    def run(cmd, **kw):
        seen["cmd"], seen["kw"] = cmd, kw
        out = "✔︎ Opened a new tab\n" + json.dumps(_load("naver_rank.json")) + "\n\x1b[2m12ms\x1b[0m\n"
        return subprocess.CompletedProcess(cmd, 0, stdout=out, stderr="")

    monkeypatch.setattr(naver.subprocess, "run", run)
    rows = naver.fetch_ranks(SETTINGS, 7, 50)
    assert {r.kind for r in rows} == {"keyword", "url"} and len(rows) == 3
    assert seen["cmd"][:4] == ["aside", "repl", "--account", "u7"]
    assert seen["kw"]["timeout"] == 150
    script = seen["cmd"][4]
    assert "{{" not in script and "topN=50" in script and "period=7" in script


def test_fetch_daily(monkeypatch):
    monkeypatch.setattr(
        naver.subprocess, "run", _run_returning(json.dumps(_load("naver_daily.json")))
    )
    assert len(naver.fetch_daily_totals(SETTINGS, 30)) == 2


def test_fetch_raises_on_not_logged_in(monkeypatch):
    monkeypatch.setattr(
        naver.subprocess, "run", _run_returning('{"error":"not_logged_in"}\n')
    )
    with pytest.raises(NaverCollectError):
        naver.fetch_ranks(SETTINGS, 7)


def test_fetch_raises_on_api_code(monkeypatch):
    monkeypatch.setattr(
        naver.subprocess, "run", _run_returning('{"code":151,"message":"FAIL"}')
    )
    with pytest.raises(NaverCollectError):
        naver.fetch_ranks(SETTINGS, 7)


def test_fetch_raises_on_timeout(monkeypatch):
    def run(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, 150)

    monkeypatch.setattr(naver.subprocess, "run", run)
    with pytest.raises(NaverCollectError):
        naver.fetch_ranks(SETTINGS, 7)


def test_fetch_raises_on_non_json(monkeypatch):
    monkeypatch.setattr(naver.subprocess, "run", _run_returning("hello\n"))
    with pytest.raises(NaverCollectError):
        naver.fetch_ranks(SETTINGS, 7)


def test_no_json_error_has_returncode_and_stderr(monkeypatch):
    def run(cmd, **kw):
        return subprocess.CompletedProcess(cmd, 3, stdout="", stderr="boom" + "x" * 300)

    monkeypatch.setattr(naver.subprocess, "run", run)
    with pytest.raises(NaverCollectError) as e:
        naver.fetch_ranks(SETTINGS, 7)
    msg = str(e.value)
    assert "returncode=3" in msg and "boomx" in msg and "x" * 200 not in msg


def test_fetch_raises_with_js_error_message(monkeypatch):
    monkeypatch.setattr(
        naver.subprocess, "run", _run_returning('{"error":"Error: net down"}')
    )
    with pytest.raises(NaverCollectError, match="net down"):
        naver.fetch_ranks(SETTINGS, 7)


def test_fetch_exposes_latest_date(monkeypatch):
    monkeypatch.setattr(
        naver.subprocess, "run", _run_returning(json.dumps(_load("naver_rank.json")))
    )
    assert naver.fetch_ranks(SETTINGS, 7).latest == date(2026, 1, 2)
    monkeypatch.setattr(
        naver.subprocess, "run", _run_returning(json.dumps(_load("naver_daily.json")))
    )
    assert naver.fetch_daily_totals(SETTINGS, 30).latest == date(2026, 1, 2)


def test_malformed_payload_is_collect_error():
    with pytest.raises(NaverCollectError, match="unexpected response"):
        parse_ranks({"items": [{"querys": [{"key": "a"}]}]}, "keyword")
    with pytest.raises(NaverCollectError, match="unexpected response"):
        parse_daily({"items": [{"logs": [{"date": "bad", "exposeCount": 1, "clickCount": 1}]}]})


def test_missing_latest_date_is_collect_error(monkeypatch):
    p = _load("naver_rank.json")
    del p["meta"]
    monkeypatch.setattr(naver.subprocess, "run", _run_returning(json.dumps(p)))
    with pytest.raises(NaverCollectError, match="unexpected response"):
        naver.fetch_ranks(SETTINGS, 7)
