import base64
import json
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from metrics_report.amplitude import (
    AmplitudeClient,
    parse_grouped,
    parse_bracket,
    parse_retention,
)
from metrics_report.periods import Period

FIX = Path(__file__).parent / "fixtures"
P = Period(date(2026, 1, 1), date(2026, 1, 7))


def _load(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


class FakeOpener:
    def __init__(self, payload):
        self.payload = payload
        self.reqs = []

    def __call__(self, req, timeout=None):
        self.reqs.append(req)
        outer = self

        class Resp:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return json.dumps(outer.payload).encode()

        return Resp()


def _q(req):
    return {k: v[0] for k, v in parse_qs(urlparse(req.full_url).query).items()}


def test_parse_retention():
    p = _load("amplitude_retention.json")
    assert parse_retention(p, 1) == 0.25
    assert parse_retention(p, 9) is None
    p["data"]["series"][0]["combined"][2]["outof"] = 0
    assert parse_retention(p, 1) is None


def test_parse_grouped():
    assert parse_grouped(_load("amplitude_segmentation.json")) == {
        "m.search.naver.com": 7,
        "(none)": 5,
        "www.example.com": 2,
    }


def test_client_sends_basic_auth_and_localhost_filter():
    op = FakeOpener(_load("amplitude_segmentation.json"))
    c = AmplitudeClient("k", "s", opener=op)
    assert c.pageviews(P) == (7, 7)

    req = op.reqs[0]
    token = base64.b64encode(b"k:s").decode()
    assert req.get_header("Authorization") == f"Basic {token}"
    q = _q(req)
    assert q["start"] == "20260101" and q["end"] == "20260107"
    assert "localhost" in q["e"] and "is not" in q["e"]


def _uniques_payload(total, daily):
    return {"data": {"seriesCollapsed": [[{"setId": "", "value": total}]], "series": [daily]}}


def test_active_users_uses_uniques():
    op = FakeOpener(_uniques_payload(729, [54, 61]))
    assert AmplitudeClient("k", "s", opener=op).active_users(P) == (729, [54, 61])
    q = _q(op.reqs[0])
    assert q["m"] == "uniques" and q["i"] == "1"
    assert '"_active"' in q["e"] and "localhost" in q["e"]


def test_new_users_uses_uniques():
    op = FakeOpener(_uniques_payload(725, [1]))
    assert AmplitudeClient("k", "s", opener=op).new_users(P) == 725
    assert '"_new"' in _q(op.reqs[0])["e"]


def test_next_period_retention_naver_segment():
    bracket = {"data": {"series": [{"combined": [
        {"count": 40, "outof": 40, "incomplete": False},
        {"count": 10, "outof": 40, "incomplete": False},
    ]}]}}
    op = FakeOpener(bracket)
    c = AmplitudeClient("k", "s", opener=op)
    assert c.next_period_retention(P, 7, source="naver") == 0.25
    q = _q(op.reqs[0])
    assert q["rm"] == "bracket" and q["rb"] == "[[1, 7]]"
    seg = json.loads(q["s"])
    assert seg[0]["prop"] == "gp:initial_referring_domain"
    assert seg[0]["op"] == "is"
    assert "search.naver.com" in seg[0]["values"]
    assert q["i"] == "1"


def test_day_n_retention_and_landing():
    op = FakeOpener(_load("amplitude_retention.json"))
    c = AmplitudeClient("k", "s", opener=op)
    assert c.day_n_retention(P, (1,)) == {1: 0.25}
    op.payload = {"data": {"series": [{"combined": [
        {"count": 4, "outof": 4, "incomplete": False},
        {"count": 1, "outof": 4, "incomplete": False},
    ]}]}}
    assert c.landing_retention_by_path(P, ["/a"]) == {"/a": 0.25}
    q = _q(op.reqs[-1])
    assert q["rm"] == "bracket" and q["rb"] == "[[1, 7]]" and q["i"] == "1"
    q = _q(op.reqs[-1])
    assert "/a" in q["se"] and "naver" in q["se"]


def test_parse_bracket():
    cell = {"count": 3, "outof": 488, "incomplete": False}
    p = {"data": {"series": [{"combined": [{**cell, "count": 488}, cell]}]}}
    assert parse_bracket(p) == 3 / 488
    cell["incomplete"] = True
    assert parse_bracket(p) is None
    cell.update(incomplete=False, outof=0)
    assert parse_bracket(p) is None


def test_parse_retention_incomplete_is_none():
    p = _load("amplitude_retention.json")
    p["data"]["series"][0]["combined"][2]["incomplete"] = True
    assert parse_retention(p, 1) is None
