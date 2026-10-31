"""Confluence REST v1 client and report publishing."""
from __future__ import annotations

import base64
import json
import urllib.parse
import urllib.request

from ga4_report.slack import send_webhook
from metrics_report.config import Settings, SlackTarget, webhook
from metrics_report.metrics import Report
from metrics_report.render import render_confluence, render_glossary, render_slack
from metrics_report.store import STATUS_OK, Store

ROOT_TITLE = "📊 지표 리포트"
WEEKLY_TITLE = "주간"
MONTHLY_TITLE = "월간"
JOB_PUBLISH = "publish"
STATUS_FAILED = "failed"


class ConfluenceClient:
    def __init__(self, base_url: str, email: str, api_token: str,
                 opener=urllib.request.urlopen) -> None:
        self._base = base_url.rstrip("/")
        self._opener = opener
        cred = base64.b64encode(f"{email}:{api_token}".encode()).decode()
        self._headers = {"Authorization": f"Basic {cred}", "Content-Type": "application/json"}

    def _call(self, req: urllib.request.Request) -> dict:
        with self._opener(req) as resp:
            return json.loads(resp.read())

    @staticmethod
    def _url(page: dict, base: dict | None = None) -> str:
        # list responses carry `base` at top level, single-page responses per page
        return (base or page)["_links"]["base"] + page["_links"]["webui"]

    def _find(self, space_key: str, title: str) -> tuple[str, str] | None:
        qs = urllib.parse.urlencode({"spaceKey": space_key, "title": title, "expand": ""})
        req = urllib.request.Request(f"{self._base}/rest/api/content?{qs}", headers=self._headers)
        resp = self._call(req)
        results = resp["results"]
        return (results[0]["id"], self._url(results[0], resp)) if results else None

    def find_page(self, space_key: str, title: str) -> str | None:
        found = self._find(space_key, title)
        return found[1] if found else None

    def create_page(
        self, space_key: str, title: str, body_storage: str, parent_id: str | None
    ) -> tuple[str, str]:
        payload = {
            "type": "page",
            "title": title,
            "space": {"key": space_key},
            "body": {"storage": {"value": body_storage, "representation": "storage"}},
        }
        if parent_id:
            payload["ancestors"] = [{"id": parent_id}]
        req = urllib.request.Request(
            f"{self._base}/rest/api/content",
            data=json.dumps(payload).encode(),
            headers=self._headers,
            method="POST",
        )
        page = self._call(req)
        return page["id"], self._url(page)

    def _ensure(self, space_key: str, title: str, body: str, parent_id: str | None) -> str:
        found = self._find(space_key, title)
        return found[0] if found else self.create_page(space_key, title, body, parent_id)[0]

    def ensure_parents(
        self, space_key: str, root_parent_id: str | None, glossary_html: str
    ) -> dict[str, str]:
        root = self._ensure(space_key, ROOT_TITLE, glossary_html, root_parent_id)
        return {
            "root": root,
            "weekly": self._ensure(space_key, WEEKLY_TITLE, "", root),
            "monthly": self._ensure(space_key, MONTHLY_TITLE, "", root),
        }

    def page_url(self, page_id: str) -> str:
        return f"{self._base}/pages/viewpage.action?pageId={page_id}"


def publish(
    report: Report, settings: Settings, store: Store, conf: ConfluenceClient,
    target: SlackTarget = SlackTarget.PROD, send=send_webhook,
) -> str:
    """Create the page (if missing) then post to Slack; idempotent per label."""
    label = report.label
    space = settings.confluence_space_key
    if store.run_done(JOB_PUBLISH, label):
        return conf.find_page(space, label) or ""

    try:
        url = conf.find_page(space, label)
        if url is None:
            ids = conf.ensure_parents(
                space, settings.confluence_parent_page_id, render_glossary(settings.okr_links)
            )
            body = render_confluence(report, glossary_url=conf.page_url(ids["root"]))
            _, url = conf.create_page(space, label, body, ids[report.kind])
        send(webhook(settings, target), render_slack(report, url)["blocks"])
    except Exception as e:
        store.mark_run(JOB_PUBLISH, label, STATUS_FAILED, str(e))
        raise
    store.mark_run(JOB_PUBLISH, label, STATUS_OK)
    return url


def alert(settings: Settings, step: str, reason: str,
          target: SlackTarget = SlackTarget.PROD, send=send_webhook) -> None:
    text = f"⚠️ {step} 실패: {reason}"
    block = {"type": "section", "text": {"type": "mrkdwn", "text": text}}
    send(webhook(settings, target), [block])
