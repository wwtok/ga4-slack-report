"""metrics.yaml + env secrets loader."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Mapping, Optional

import yaml

ENV_AMPLITUDE_API_KEY = "AMPLITUDE_API_KEY"
ENV_AMPLITUDE_SECRET_KEY = "AMPLITUDE_SECRET_KEY"
ENV_CONFLUENCE_EMAIL = "CONFLUENCE_EMAIL"
ENV_CONFLUENCE_API_TOKEN = "CONFLUENCE_API_TOKEN"
ENV_SLACK_WEBHOOK_URL = "SLACK_WEBHOOK_URL"


@dataclass
class Secrets:
    amplitude_api_key: str
    amplitude_secret_key: str
    confluence_email: str
    confluence_api_token: str
    slack_webhook_url: str


@dataclass
class Settings:
    amplitude_project_id: str
    naver_site: str
    naver_site_hash: str
    aside_account: str
    confluence_base_url: str
    confluence_space_key: str
    confluence_parent_page_id: Optional[str]
    data_dir: Path
    out_dir: Path
    secrets: Secrets
    okr_links: Dict[str, str] = field(default_factory=dict)


def _require(env: Mapping[str, str], name: str) -> str:
    value = env.get(name)
    if not value:
        raise ValueError(f"{name} is not set")
    return value


def _secrets(env: Mapping[str, str]) -> Secrets:
    return Secrets(
        amplitude_api_key=_require(env, ENV_AMPLITUDE_API_KEY),
        amplitude_secret_key=_require(env, ENV_AMPLITUDE_SECRET_KEY),
        confluence_email=_require(env, ENV_CONFLUENCE_EMAIL),
        confluence_api_token=_require(env, ENV_CONFLUENCE_API_TOKEN),
        slack_webhook_url=_require(env, ENV_SLACK_WEBHOOK_URL),
    )


def load_settings(path: str = "metrics.yaml", env: Mapping[str, str] = os.environ) -> Settings:
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    parent = raw.get("confluence_parent_page_id")
    return Settings(
        amplitude_project_id=str(raw["amplitude_project_id"]),
        naver_site=raw["naver_site"],
        naver_site_hash=raw["naver_site_hash"],
        aside_account=raw["aside_account"],
        confluence_base_url=raw["confluence_base_url"],
        confluence_space_key=raw["confluence_space_key"],
        confluence_parent_page_id=None if parent is None else str(parent),
        data_dir=Path(raw["data_dir"]),
        out_dir=Path(raw["out_dir"]),
        okr_links=dict(raw.get("okr_links") or {}),
        secrets=_secrets(env),
    )
