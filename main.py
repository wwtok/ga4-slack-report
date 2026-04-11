"""GA4 Slack Report — entrypoint."""
from __future__ import annotations

import os
import sys
from dataclasses import asdict

from ga4_report.config import load_config, load_config_from_env
from ga4_report.ga4_client import build_client
from ga4_report.renderer import render_report
from ga4_report.report import collect_property_data
from ga4_report.slack import send_report


def run(config_path: str | None = None) -> None:
    if config_path and os.path.isfile(config_path):
        cfg = load_config(config_path)
    else:
        cfg = load_config_from_env()
    creds_json = cfg.google.resolve_credentials(os.environ)
    if not creds_json:
        print(f"Environment variable '{cfg.google.credentials_env}' is not set.", file=sys.stderr)
        sys.exit(1)
    client = build_client(creds_json)
    sections_dict = asdict(cfg.report.sections)
    for prop in cfg.properties:
        report = collect_property_data(
            client=client,
            property_config=prop,
            schedule_config=cfg.schedule,
            report_config=cfg.report,
        )
        blocks = render_report(
            report,
            sections=sections_dict,
            custom_template=cfg.report.custom_template,
        )
        webhook_url = cfg.slack.resolve_webhook_url(os.environ)
        token = cfg.slack.resolve_token(os.environ)
        send_report(
            method=cfg.slack.method,
            blocks=blocks,
            webhook_url=webhook_url or None,
            token=token or None,
            channel_id=cfg.slack.channel_id or None,
        )
        cr = report.current_range
        print(f"✅ {prop.name} report sent ({cr[0]} ~ {cr[1]})")


def main() -> None:
    config_path = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("CONFIG_PATH", "config.yaml")
    run(config_path)


if __name__ == "__main__":
    main()
