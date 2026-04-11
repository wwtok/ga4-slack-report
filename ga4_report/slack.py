"""Slack message delivery via Webhook or OAuth."""

from __future__ import annotations

import json
import urllib.request
from typing import Optional

from slack_sdk import WebClient


def send_webhook(url: str, blocks: list[dict]) -> None:
    """Send Slack message via Incoming Webhook."""
    payload = json.dumps({"blocks": blocks}).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        if resp.status != 200:
            raise RuntimeError(f"Slack webhook failed: {resp.status}")


def send_oauth(token: str, channel_id: str, blocks: list[dict]) -> None:
    """Send Slack message via OAuth token using chat.postMessage."""
    client = WebClient(token=token)
    client.chat_postMessage(channel=channel_id, blocks=blocks)


def send_report(
    *,
    method: str,
    blocks: list[dict],
    webhook_url: Optional[str] = None,
    token: Optional[str] = None,
    channel_id: Optional[str] = None,
) -> None:
    """Dispatch to the appropriate Slack send method."""
    if method == "webhook":
        assert webhook_url, "webhook_url is required for webhook method"
        send_webhook(webhook_url, blocks)
    elif method == "oauth":
        assert token, "token is required for oauth method"
        assert channel_id, "channel_id is required for oauth method"
        send_oauth(token, channel_id, blocks)
    else:
        raise ValueError(f"Unknown slack method: {method}")
