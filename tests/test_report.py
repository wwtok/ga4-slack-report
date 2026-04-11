"""Tests for ga4_report.report."""
from datetime import date

from ga4_report.report import build_property_report, diff_pct


def test_diff_pct_normal():
    assert diff_pct(150, 100) == 50.0


def test_diff_pct_from_zero():
    assert diff_pct(100, 0) == 100.0
    assert diff_pct(0, 0) == 0.0


def test_diff_pct_decrease():
    assert diff_pct(50, 100) == -50.0


def test_build_property_report():
    current = {
        "active_users": 100,
        "sessions": 150,
        "pageviews": 300,
        "avg_session_duration": 120.5,
        "bounce_rate": 0.45,
    }
    previous = {
        "active_users": 80,
        "sessions": 100,
        "pageviews": 200,
        "avg_session_duration": 100.0,
        "bounce_rate": 0.50,
    }
    report = build_property_report(
        property_name="Test",
        property_id="123",
        current=current,
        previous=previous,
        traffic_sources=[{"source": "google", "medium": "organic", "sessions": 80}],
        pages=[{"path": "/", "pageviews": 200, "active_users": 50}],
        devices=[{"category": "desktop", "sessions": 100}],
        current_range=(date(2026, 4, 4), date(2026, 4, 10)),
        previous_range=(date(2026, 3, 28), date(2026, 4, 3)),
    )
    assert report.property_name == "Test"
    assert report.diffs["active_users_pct"] == 25.0
    assert report.diffs["sessions_pct"] == 50.0
    assert report.diffs["pageviews_pct"] == 50.0
    assert report.diffs["avg_session_duration_pct"] == 20.5
    assert report.diffs["bounce_rate_diff"] == -5.0  # (0.45 - 0.50) * 100
    assert len(report.traffic_sources) == 1
    assert len(report.pages) == 1
    assert len(report.devices) == 1


def test_build_report_zero_previous():
    current = {
        "active_users": 100,
        "sessions": 50,
        "pageviews": 200,
        "avg_session_duration": 60.0,
        "bounce_rate": 0.30,
    }
    previous = {
        "active_users": 0,
        "sessions": 0,
        "pageviews": 0,
        "avg_session_duration": 0.0,
        "bounce_rate": 0.0,
    }
    report = build_property_report(
        property_name="New",
        property_id="456",
        current=current,
        previous=previous,
        traffic_sources=[],
        pages=[],
        devices=[],
        current_range=(date(2026, 4, 10), date(2026, 4, 10)),
        previous_range=(date(2026, 4, 9), date(2026, 4, 9)),
    )
    assert report.diffs["active_users_pct"] == 100.0
    assert report.diffs["sessions_pct"] == 100.0
    assert report.diffs["bounce_rate_diff"] == 30.0  # (0.30 - 0.0) * 100
