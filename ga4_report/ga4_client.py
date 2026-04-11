"""GA4 Data API client helpers and date range calculation."""
from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange as GA4DateRange,
    Dimension,
    Metric,
    OrderBy,
    RunReportRequest,
)
from google.oauth2.service_account import Credentials

from ga4_report.config import CustomSchedule

DateRange = Tuple[date, date]

_PERIOD_DAYS = {
    "daily": 1,
    "weekly": 7,
    "biweekly": 14,
    "monthly": 30,
}


def compute_date_ranges(
    period: str,
    compare: str,
    data_delay_days: int,
    custom: Optional[CustomSchedule],
    *,
    ref_date: Optional[date] = None,
) -> Tuple[DateRange, DateRange]:
    today = ref_date or date.today()
    end = today - timedelta(days=data_delay_days)
    if period == "custom":
        assert custom is not None
        current_days = custom.current_days
    else:
        current_days = _PERIOD_DAYS[period]
    start = end - timedelta(days=current_days - 1)
    current_range: DateRange = (start, end)
    if compare == "same_period_last_week":
        shift = timedelta(days=7)
        previous_range: DateRange = (start - shift, end - shift)
    elif compare == "custom" and custom is not None:
        prev_end = start - timedelta(days=1)
        prev_start = prev_end - timedelta(days=custom.previous_days - 1)
        previous_range = (prev_start, prev_end)
    else:
        prev_end = start - timedelta(days=1)
        if period == "custom" and custom is not None:
            prev_days = custom.previous_days
        else:
            prev_days = current_days
        prev_start = prev_end - timedelta(days=prev_days - 1)
        previous_range = (prev_start, prev_end)
    return current_range, previous_range


def build_client(credentials_json: str) -> BetaAnalyticsDataClient:
    info = json.loads(credentials_json)
    creds = Credentials.from_service_account_info(
        info,
        scopes=["https://www.googleapis.com/auth/analytics.readonly"],
    )
    return BetaAnalyticsDataClient(credentials=creds)


def fetch_summary(client: BetaAnalyticsDataClient, property_id: str, start: date, end: date) -> Dict[str, Any]:
    request = RunReportRequest(
        property=f"properties/{property_id}",
        date_ranges=[GA4DateRange(start_date=start.isoformat(), end_date=end.isoformat())],
        metrics=[
            Metric(name="activeUsers"),
            Metric(name="sessions"),
            Metric(name="screenPageViews"),
            Metric(name="averageSessionDuration"),
            Metric(name="bounceRate"),
        ],
    )
    response = client.run_report(request)
    if not response.rows:
        return {
            "active_users": 0,
            "sessions": 0,
            "pageviews": 0,
            "avg_session_duration": 0.0,
            "bounce_rate": 0.0,
        }
    values = response.rows[0].metric_values
    return {
        "active_users": int(values[0].value),
        "sessions": int(values[1].value),
        "pageviews": int(values[2].value),
        "avg_session_duration": float(values[3].value),
        "bounce_rate": float(values[4].value),
    }


def _sessions_desc_order() -> OrderBy:
    return OrderBy(desc=True, metric=OrderBy.MetricOrderBy(metric_name="sessions"))


def _screen_page_views_desc_order() -> OrderBy:
    return OrderBy(desc=True, metric=OrderBy.MetricOrderBy(metric_name="screenPageViews"))


def fetch_traffic_sources(
    client: BetaAnalyticsDataClient,
    property_id: str,
    start: date,
    end: date,
    limit: int,
) -> List[Dict[str, Any]]:
    request = RunReportRequest(
        property=f"properties/{property_id}",
        date_ranges=[GA4DateRange(start_date=start.isoformat(), end_date=end.isoformat())],
        dimensions=[
            Dimension(name="sessionSource"),
            Dimension(name="sessionMedium"),
        ],
        metrics=[Metric(name="sessions")],
        order_bys=[_sessions_desc_order()],
        limit=limit,
    )
    response = client.run_report(request)
    rows: List[Dict[str, Any]] = []
    for row in response.rows:
        src = row.dimension_values[0].value
        med = row.dimension_values[1].value
        sess = int(row.metric_values[0].value)
        rows.append({"source": src, "medium": med, "sessions": sess})
    return rows


def fetch_top_pages(
    client: BetaAnalyticsDataClient,
    property_id: str,
    start: date,
    end: date,
    limit: int,
) -> List[Dict[str, Any]]:
    request = RunReportRequest(
        property=f"properties/{property_id}",
        date_ranges=[GA4DateRange(start_date=start.isoformat(), end_date=end.isoformat())],
        dimensions=[Dimension(name="pagePath")],
        metrics=[
            Metric(name="screenPageViews"),
            Metric(name="activeUsers"),
        ],
        order_bys=[_screen_page_views_desc_order()],
        limit=limit,
    )
    response = client.run_report(request)
    rows: List[Dict[str, Any]] = []
    for row in response.rows:
        path = row.dimension_values[0].value
        pvs = int(row.metric_values[0].value)
        users = int(row.metric_values[1].value)
        rows.append({"path": path, "pageviews": pvs, "active_users": users})
    return rows


def fetch_devices(
    client: BetaAnalyticsDataClient,
    property_id: str,
    start: date,
    end: date,
) -> List[Dict[str, Any]]:
    request = RunReportRequest(
        property=f"properties/{property_id}",
        date_ranges=[GA4DateRange(start_date=start.isoformat(), end_date=end.isoformat())],
        dimensions=[Dimension(name="deviceCategory")],
        metrics=[Metric(name="sessions")],
    )
    response = client.run_report(request)
    rows: List[Dict[str, Any]] = []
    for row in response.rows:
        category = row.dimension_values[0].value
        sess = int(row.metric_values[0].value)
        rows.append({"category": category, "sessions": sess})
    return rows
