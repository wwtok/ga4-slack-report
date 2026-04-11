"""YAML configuration loader with validation."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Mapping, Optional

import yaml

VALID_PERIODS = ("daily", "weekly", "biweekly", "monthly", "custom")
VALID_COMPARES = ("previous_period", "same_period_last_week", "custom")
VALID_SLACK_METHODS = ("webhook", "oauth")
VALID_MULTI_SITE_MODES = ("separate", "combined")


@dataclass
class CustomSchedule:
    current_days: int = 7
    previous_days: int = 7


@dataclass
class ScheduleConfig:
    period: str = "daily"
    compare: str = "previous_period"
    data_delay_days: int = 1
    custom: Optional[CustomSchedule] = None


@dataclass
class PropertyConfig:
    name: str = ""
    property_id: str = ""


@dataclass
class GoogleConfig:
    credentials_env: str = ""

    def resolve_credentials(self, env: Mapping[str, str]) -> str:
        return env.get(self.credentials_env, "")


@dataclass
class SlackConfig:
    method: str = "webhook"
    webhook_url_env: str = ""
    token_env: str = ""
    channel_id: str = ""

    def resolve_webhook_url(self, env: Mapping[str, str]) -> str:
        return env.get(self.webhook_url_env, "")

    def resolve_token(self, env: Mapping[str, str]) -> str:
        return env.get(self.token_env, "")


@dataclass
class SectionsConfig:
    summary: bool = True
    traffic_sources: bool = True
    top_pages: bool = True
    top_devices: bool = False


@dataclass
class ReportConfig:
    sections: SectionsConfig = field(default_factory=SectionsConfig)
    top_n: int = 10
    multi_site_mode: str = "separate"
    custom_template: Optional[str] = None


@dataclass
class AppConfig:
    schedule: ScheduleConfig = field(default_factory=ScheduleConfig)
    properties: List[PropertyConfig] = field(default_factory=list)
    google: GoogleConfig = field(default_factory=GoogleConfig)
    slack: SlackConfig = field(default_factory=SlackConfig)
    report: ReportConfig = field(default_factory=ReportConfig)


def load_config(path: str) -> AppConfig:
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    cfg = _parse_config(raw)
    _validate(cfg)
    return cfg


def load_config_from_env() -> AppConfig:
    return AppConfig(
        properties=[
            PropertyConfig(
                name=os.environ.get("PROJECT_NAME", "My Site"),
                property_id=os.environ.get("GA4_PROPERTY_ID", ""),
            )
        ],
        google=GoogleConfig(credentials_env="GOOGLE_SERVICE_ACCOUNT_JSON"),
        slack=SlackConfig(method="webhook", webhook_url_env="SLACK_WEBHOOK_URL"),
    )


def _parse_config(raw: dict) -> AppConfig:
    schedule_raw = raw.get("schedule", {})
    custom_raw = schedule_raw.get("custom")
    custom = CustomSchedule(**custom_raw) if custom_raw else None
    schedule = ScheduleConfig(
        period=schedule_raw.get("period", "daily"),
        compare=schedule_raw.get("compare", "previous_period"),
        data_delay_days=schedule_raw.get("data_delay_days", 1),
        custom=custom,
    )
    properties_raw = raw.get("properties", [])
    properties = [
        PropertyConfig(
            name=p.get("name", ""),
            property_id=str(p.get("property_id", "")),
        )
        for p in properties_raw
    ]
    google_raw = raw.get("google", {})
    google = GoogleConfig(credentials_env=google_raw.get("credentials_env", ""))
    slack_raw = raw.get("slack", {})
    slack = SlackConfig(
        method=slack_raw.get("method", "webhook"),
        webhook_url_env=slack_raw.get("webhook_url_env", ""),
        token_env=slack_raw.get("token_env", ""),
        channel_id=str(slack_raw.get("channel_id", "")),
    )
    report_raw = raw.get("report", {})
    sections_raw = report_raw.get("sections", {})
    sections = SectionsConfig(
        summary=sections_raw.get("summary", True),
        traffic_sources=sections_raw.get("traffic_sources", True),
        top_pages=sections_raw.get("top_pages", True),
        top_devices=sections_raw.get("top_devices", False),
    )
    report = ReportConfig(
        sections=sections,
        top_n=report_raw.get("top_n", 10),
        multi_site_mode=report_raw.get("multi_site_mode", "separate"),
        custom_template=report_raw.get("custom_template"),
    )
    return AppConfig(schedule=schedule, properties=properties, google=google, slack=slack, report=report)


def _validate(cfg: AppConfig) -> None:
    if cfg.schedule.period not in VALID_PERIODS:
        raise ValueError(
            f"Invalid schedule.period '{cfg.schedule.period}'. Must be one of: {', '.join(VALID_PERIODS)}"
        )
    if cfg.schedule.compare not in VALID_COMPARES:
        raise ValueError(
            f"Invalid schedule.compare '{cfg.schedule.compare}'. Must be one of: {', '.join(VALID_COMPARES)}"
        )
    if cfg.schedule.period == "custom" and cfg.schedule.custom is None:
        raise ValueError("schedule.period is 'custom' but schedule.custom block is missing.")
    if cfg.schedule.compare == "custom" and cfg.schedule.custom is None:
        raise ValueError("schedule.compare is 'custom' but schedule.custom block is missing.")
    if not cfg.properties:
        raise ValueError("At least one property must be configured in properties[].")
    if cfg.slack.method not in VALID_SLACK_METHODS:
        raise ValueError(
            f"Invalid slack.method '{cfg.slack.method}'. Must be one of: {', '.join(VALID_SLACK_METHODS)}"
        )
    if cfg.slack.method == "oauth" and not cfg.slack.channel_id:
        raise ValueError("slack.channel_id is required when slack.method is 'oauth'.")
    if cfg.report.multi_site_mode not in VALID_MULTI_SITE_MODES:
        raise ValueError(
            f"Invalid report.multi_site_mode '{cfg.report.multi_site_mode}'. Must be one of: {', '.join(VALID_MULTI_SITE_MODES)}"
        )
