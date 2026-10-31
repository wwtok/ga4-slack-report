import base64
import json
from datetime import date

import pytest

from metrics_report.config import Secrets, Settings, SlackTarget
from metrics_report.confluence import ConfluenceClient, alert, publish
from metrics_report.metrics import Report
from metrics_report.periods import Period
from metrics_report.store import Store

BASE = "https://x.atlassian.net/wiki"


class Resp:
    def __init__(self, data):
        self._d = json.dumps(data).encode()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass

    def read(self):
        return self._d


class FakeOpener:
    """Pages keyed by title; records requests."""

    def __init__(self, pages=None):
        self.pages = dict(pages or {})
        self.reqs = []
        self.timeouts = []

    def __call__(self, req, timeout=None):
        self.timeouts.append(timeout)
        self.reqs.append(req)
        links = lambda i: {"base": BASE, "webui": f"/spaces/S/pages/{i}"}
        list_links = lambda i: {"webui": f"/spaces/S/pages/{i}"}
        if req.get_method() == "POST":
            body = json.loads(req.data)
            pid = str(100 + len(self.pages))
            self.pages[body["title"]] = pid
            return Resp({"id": pid, "_links": links(pid)})
        title = req.full_url.split("title=")[1].split("&")[0]
        from urllib.parse import unquote_plus
        pid = self.pages.get(unquote_plus(title))
        res = [{"id": pid, "_links": list_links(pid)}] if pid else []
        return Resp({"results": res, "_links": {"base": BASE}})

    def posts(self):
        return [json.loads(r.data) for r in self.reqs if r.get_method() == "POST"]


def _client(op):
    return ConfluenceClient(BASE, "e@x.com", "tok", op)


def test_find_page_none_and_found():
    assert _client(FakeOpener()).find_page("S", "t") is None
    url = _client(FakeOpener({"t": "5"})).find_page("S", "t")
    assert url == f"{BASE}/spaces/S/pages/5"


def test_create_page_payload():
    op = FakeOpener()
    pid, url = _client(op).create_page("S", "제목", "<p>x</p>", "9")
    body = op.posts()[0]
    assert body["space"] == {"key": "S"}
    assert body["title"] == "제목"
    assert body["body"]["storage"] == {"value": "<p>x</p>", "representation": "storage"}
    assert body["ancestors"] == [{"id": "9"}]
    auth = op.reqs[0].get_header("Authorization")
    assert auth == "Basic " + base64.b64encode(b"e@x.com:tok").decode()
    assert url.endswith(f"/pages/{pid}")


def test_create_page_without_parent_has_no_ancestors():
    op = FakeOpener()
    _client(op).create_page("S", "t", "b", None)
    assert "ancestors" not in op.posts()[0]


def test_ensure_parents_creates_missing_only():
    op = FakeOpener({"📊 지표 리포트": "1"})
    ids = _client(op).ensure_parents("S", None, "<p>g</p>")
    assert ids["root"] == "1"
    assert [p["title"] for p in op.posts()] == ["📊 주간 리포트", "📊 월간 리포트"]
    assert all(p["ancestors"] == [{"id": "1"}] for p in op.posts())


# --- publish ---

@pytest.fixture
def settings(tmp_path):
    return Settings("1", "https://x.kr", "h", "u", BASE, "S", "P", tmp_path / "d",
                    tmp_path / "o", Secrets("a", "b", "c", "d", "prod", "test"),
                    confluence_test_space_key="TS", confluence_test_parent_page_id="TP")


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "s.db")


def _report():
    return Report("weekly", Period(date(2026, 10, 24), date(2026, 10, 30)),
                  "[주간] 2026-10-24 ~ 10-30", {}, None)


def test_publish_idempotent(settings, store):
    op, sent = FakeOpener(), []
    send = lambda url, blocks: sent.append((url, blocks))
    c = _client(op)
    publish(_report(), settings, store, c, SlackTarget.TEST, send)
    n_posts = len(op.posts())
    publish(_report(), settings, store, c, SlackTarget.TEST, send)
    assert len(op.posts()) == n_posts
    assert len(sent) == 1
    assert sent[0][0] == "test"
    assert [p["title"] for p in op.posts()][-1] == "[주간] 2026-10-24 ~ 10-30"


def test_publish_existing_page_skips_create(settings, store):
    op, sent = FakeOpener({"[주간] 2026-10-24 ~ 10-30": "7"}), []
    publish(_report(), settings, store, _client(op), SlackTarget.TEST,
            lambda u, b: sent.append(u))
    assert op.posts() == []
    assert len(sent) == 1


def test_publish_failure_marks_failed_and_retries(settings, store):
    op = FakeOpener()

    def boom(u, b):
        raise RuntimeError("slack down")

    with pytest.raises(RuntimeError):
        publish(_report(), settings, store, _client(op), SlackTarget.TEST, boom)
    assert not store.run_done("publish", _report().label)
    pages = len(op.posts())
    sent = []
    publish(_report(), settings, store, _client(op), SlackTarget.TEST, lambda u, b: sent.append(u))
    assert len(sent) == 1
    assert len(op.posts()) == pages  # page not recreated


def test_alert_text_and_missing_webhook(settings):
    sent = []
    alert(settings, "collect", "boom", SlackTarget.TEST, lambda u, b: sent.append((u, b)))
    assert "⚠️ collect 실패: boom" in json.dumps(sent[0][1], ensure_ascii=False)
    settings.secrets.slack_test_webhook_url = ""
    with pytest.raises(ValueError, match="SLACK_TEST_WEBHOOK_URL is not set"):
        alert(settings, "x", "y", SlackTarget.TEST, lambda u, b: None)


def test_requests_use_timeout():
    op = FakeOpener()
    c = _client(op)
    c.find_page("S", "t")
    c.create_page("S", "t", "b", None)
    assert op.timeouts == [60, 60]


def _spaces(op):
    return [json.loads(r.data)["space"]["key"] for r in op.reqs if r.get_method() == "POST"]


def test_test_target_uses_test_space_and_parent(settings, store):
    op = FakeOpener()
    publish(_report(), settings, store, _client(op), SlackTarget.TEST, lambda u, b: None)
    assert set(_spaces(op)) == {"TS"}
    assert op.posts()[0]["ancestors"] == [{"id": "TP"}]  # root under test parent


def test_prod_target_uses_prod_space_and_parent(settings, store):
    op = FakeOpener()
    publish(_report(), settings, store, _client(op), SlackTarget.PROD, lambda u, b: None)
    assert set(_spaces(op)) == {"S"}
    assert op.posts()[0]["ancestors"] == [{"id": "P"}]


def test_alert_escapes_reason(settings):
    sent = []
    alert(settings, "x", "<b>&", SlackTarget.TEST, lambda u, b: sent.append(b))
    assert "&lt;b&gt;&amp;" in json.dumps(sent[0])


def test_alert_prefers_test_webhook(settings):
    sent = []
    alert(settings, "x", "y", SlackTarget.PROD, lambda u, b: sent.append(u))
    assert sent == ["test"]
    settings.secrets.slack_test_webhook_url = ""
    alert(settings, "x", "y", SlackTarget.PROD, lambda u, b: sent.append(u))
    assert sent[-1] == "prod"
