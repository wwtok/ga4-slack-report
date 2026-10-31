"""CLI: python -m metrics_report {report,collect,backfill}."""
from __future__ import annotations

import argparse
import os
from datetime import date, datetime
from functools import partial
from pathlib import Path

from metrics_report import build
from metrics_report.amplitude import AmplitudeClient
from metrics_report.config import SlackTarget, load_settings, webhook
from metrics_report.confluence import ConfluenceClient, alert, publish
from metrics_report.store import Store
from metrics_report.tick import KST, Deps, tick

SYSTEM_CA = "/etc/ssl/cert.pem"
DB_NAME = "metrics.db"


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="metrics_report")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("report")
    r.add_argument("kind", choices=["weekly", "monthly"])
    r.add_argument("--date", type=date.fromisoformat, default=None)
    r.add_argument("--dry-run", action="store_true")
    r.add_argument("--test", action="store_true")
    sub.add_parser("collect")
    sub.add_parser("backfill")
    sub.add_parser("tick").add_argument("--test", action="store_true")
    return ap


def main(argv: list[str] | None = None) -> None:
    # venv Python lacks system CAs on this Mac
    if "SSL_CERT_FILE" not in os.environ and Path(SYSTEM_CA).exists():
        os.environ["SSL_CERT_FILE"] = SYSTEM_CA

    args = _parser().parse_args(argv)
    settings = load_settings()
    store = Store(settings.data_dir / DB_NAME)
    today = date.today()

    if args.cmd == "collect":
        build.collect_daily(settings, store, today)
        return
    if args.cmd == "backfill":
        build.backfill(settings, store, today)
        return

    amp = AmplitudeClient(settings.secrets.amplitude_api_key, settings.secrets.amplitude_secret_key)
    target = SlackTarget.TEST if args.test else SlackTarget.PROD
    sec = settings.secrets
    if args.cmd == "tick" or not args.dry_run:
        webhook(settings, target)  # fail fast on missing webhook
    conf = ConfluenceClient(settings.confluence_base_url, sec.confluence_email, sec.confluence_api_token)

    if args.cmd == "tick":
        deps = Deps(
            collect=partial(build.collect_daily, settings, store),
            build=lambda kind, d: build.build_report(kind, d, settings, store, amp),
            publish=lambda rep: publish(rep, settings, store, conf, target),
            alert=lambda step, reason: alert(settings, step, reason, target),
        )
        print(tick(datetime.now(KST), settings, store, deps))
        return

    report = build.build_report(args.kind, args.date or today, settings, store, amp)
    if args.dry_run:
        print(build.write_dry_run(report, settings))
        return
    print(publish(report, settings, store, conf, target))


if __name__ == "__main__":
    main()
