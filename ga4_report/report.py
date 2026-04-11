"""Property report model, diff helpers, and data collection orchestration."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List, Tuple

from google.analytics.data_v1beta import BetaAnalyticsDataClient

from ga4_report.config import PropertyConfig, ReportConfig, ScheduleConfig
from ga4_report.ga4_client import (
    compute_date_ranges,
    fetch_devices,
    fetch_summary,
    fetch_top_pages,
    fetch_traffic_sources,
)


@dataclass
class PropertyReport:
    property_name: str
    property_id: str
    current_range: Tuple[date, date]
    previous_range: Tuple[date, date]
    current: dict  # {active_users, sessions, pageviews, avg_session_duration, bounce_rate}
    previous: dict  # same keys
    diffs: dict  # {active_users_pct, sessions_pct, ...}
    traffic_sources: List[dict]  # [{source, medium, sessions}]
    pages: List[dict]  # [{path, pageviews, active_users}]
    devices: List[dict]  # [{category, sessions}]


def diff_pct(current_val: float, previous_val: float) -> float:
    if previous_val != 0:
        return ((current_val - previous_val) / previous_val) * 100
    if current_val > 0:
        return 100.0
    return 0.0


def build_property_report(
    *,
    property_name: str,
    property_id: str,
    current: dict,
    previous: dict,
    traffic_sources: List[dict],
    pages: List[dict],
    devices: List[dict],
    current_range: Tuple[date, date],
    previous_range: Tuple[date, date],
) -> PropertyReport:
    diffs = {
        "active_users_pct": diff_pct(current["active_users"], previous["active_users"]),
        "sessions_pct": diff_pct(current["sessions"], previous["sessions"]),
        "pageviews_pct": diff_pct(current["pageviews"], previous["pageviews"]),
        "avg_session_duration_pct": diff_pct(
            current["avg_session_duration"], previous["avg_session_duration"]
        ),
        "bounce_rate_diff": round(
            (current["bounce_rate"] - previous["bounce_rate"]) * 100, 10
        ),
    }
    return PropertyReport(
        property_name=property_name,
        property_id=property_id,
        current_range=current_range,
        previous_range=previous_range,
        current=current,
        previous=previous,
        diffs=diffs,
        traffic_sources=traffic_sources,
        pages=pages,
        devices=devices,
    )


def collect_property_data(
    client: BetaAnalyticsDataClient,
    property_config: PropertyConfig,
    schedule_config: ScheduleConfig,
    report_config: ReportConfig,
) -> PropertyReport:
    current_range, previous_range = compute_date_ranges(
        schedule_config.period,
        schedule_config.compare,
        schedule_config.data_delay_days,
        schedule_config.custom,
    )
    c_start, c_end = current_range
    p_start, p_end = previous_range
    pid = property_config.property_id

    current = fetch_summary(client, pid, c_start, c_end)
    previous = fetch_summary(client, pid, p_start, p_end)

    sections = report_config.sections
    top_n = report_config.top_n

    if sections.traffic_sources:
        traffic_sources = fetch_traffic_sources(client, pid, c_start, c_end, top_n)
    else:
        traffic_sources = []

    if sections.top_pages:
        pages = fetch_top_pages(client, pid, c_start, c_end, top_n)
    else:
        pages = []

    if sections.top_devices:
        devices = fetch_devices(client, pid, c_start, c_end)
    else:
        devices = []

    return build_property_report(
        property_name=property_config.name,
        property_id=pid,
        current=current,
        previous=previous,
        traffic_sources=traffic_sources,
        pages=pages,
        devices=devices,
        current_range=current_range,
        previous_range=previous_range,
    )
