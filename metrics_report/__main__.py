"""CLI: python -m metrics_report {report,collect,backfill}."""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

from metrics_report import build
from metrics_report.amplitude import AmplitudeClient
from metrics_report.config import load_settings
from metrics_report.store import Store

SYSTEM_CA = "/etc/ssl/cert.pem"
DB_NAME = "metrics.db"


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="metrics_report")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("report")
    r.add_argument("kind", choices=["weekly", "monthly"])
    r.add_argument("--date", type=date.fromisoformat, default=None)
    r.add_argument("--dry-run", action="store_true")
    sub.add_parser("collect")
    sub.add_parser("backfill")
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

    if not args.dry_run:
        sys.exit("publish not implemented yet (Task 7)")

    amp = AmplitudeClient(settings.secrets.amplitude_api_key, settings.secrets.amplitude_secret_key)
    report = build.build_report(args.kind, args.date or today, settings, store, amp)
    print(build.write_dry_run(report, settings))


if __name__ == "__main__":
    main()
