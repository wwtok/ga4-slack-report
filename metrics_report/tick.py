"""Hourly scheduler: run due jobs (collect, weekly, monthly) once each."""
from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date, datetime
from typing import Callable
from zoneinfo import ZoneInfo

from metrics_report.metrics import Report
from metrics_report.periods import monthly_label, monthly_period, weekly_label, weekly_period
from metrics_report.confluence import JOB_PUBLISH, STATUS_OK
from metrics_report.store import Store

KST = ZoneInfo("Asia/Seoul")
COLLECT_HOUR = 12
REPORT_HOUR = 9
NAVER_DEADLINE_HOUR = 18
SATURDAY = 5
FIRST_DAY = 1
JOB_COLLECT = "collect"
JOB_ALERT = "alert"


@dataclass
class Deps:
    collect: Callable[[date], None]
    build: Callable[[str, date], Report]
    publish: Callable[[Report], str]
    alert: Callable[[str, str], None]


def _alert_once(store: Store, deps: Deps, today: date, job: str, label: str, e: Exception) -> None:
    # one alert per (job, label) per day
    key = f"{job}:{label}:{today.isoformat()}"
    if store.run_done(JOB_ALERT, key):
        return
    try:
        deps.alert(job, str(e))
    except Exception as send_err:  # alert failure must not stop other jobs
        print(f"alert failed: {send_err}", file=sys.stderr)
        return
    store.mark_run(JOB_ALERT, key, STATUS_OK)


def tick(now: datetime, settings, store: Store, deps: Deps) -> list[str]:
    today = now.date()
    ran: list[str] = []

    def run(job: str, label: str, fn) -> None:
        try:
            fn()
            ran.append(job)
        except Exception as e:
            _alert_once(store, deps, today, job, label, e)

    def collect() -> None:
        deps.collect(today)
        store.mark_run(JOB_COLLECT, today.isoformat(), STATUS_OK)

    def report(kind: str) -> None:
        rep = deps.build(kind, today)
        # retry hourly until the deadline, then ship the reduced report
        if rep.naver is None and now.hour < NAVER_DEADLINE_HOUR:
            raise RuntimeError(f"네이버 데이터 없음, {NAVER_DEADLINE_HOUR}시까지 재시도")
        deps.publish(rep)

    weekly = weekly_label(weekly_period(today))
    monthly = monthly_label(monthly_period(today))
    weekly_due = not (today.weekday() == SATURDAY and now.hour < REPORT_HOUR)
    monthly_due = not (today.day == FIRST_DAY and now.hour < REPORT_HOUR)

    if now.hour >= COLLECT_HOUR and not store.run_done(JOB_COLLECT, today.isoformat()):
        run("collect", today.isoformat(), collect)
    if weekly_due and not store.run_done(JOB_PUBLISH, weekly):
        run("weekly", weekly, lambda: report("weekly"))
    if monthly_due and not store.run_done(JOB_PUBLISH, monthly):
        run("monthly", monthly, lambda: report("monthly"))
    return ran
