"""Render PropertyReport to Slack Block Kit JSON via Jinja2."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from jinja2 import Environment, FileSystemLoader

from ga4_report.report import PropertyReport

_TEMPLATES_DIR = Path(__file__).parent / "templates"


def _trend(diff: float, unit: str) -> str:
    if abs(diff) < 0.05:
        return "→ 0"
    arrow = "▲" if diff > 0 else "▼"
    return f"({arrow} {diff:+.1f}{unit})"


def _trend_pos(diff: float) -> str:
    if abs(diff) < 0.1:
        return "→ 0"
    arrow = "▲" if diff < 0 else "▼"
    return f"({arrow} {abs(diff):.1f})"


def _extract_path(url: str) -> str:
    try:
        return urlparse(url).path or url
    except Exception:
        return url


def _format_duration(seconds: float) -> str:
    if seconds < 0:
        seconds = 0.0
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m}m {s}s"


def _format_bounce_rate(rate: float) -> str:
    return f"{rate * 100:.1f}%"


def _build_context(report: PropertyReport, sections: dict) -> dict:
    return {
        "property_name": report.property_name,
        "property_id": report.property_id,
        "current_range": report.current_range,
        "previous_range": report.previous_range,
        "current": report.current,
        "previous": report.previous,
        "diffs": report.diffs,
        "traffic_sources": report.traffic_sources,
        "pages": report.pages,
        "devices": report.devices,
        "sections": sections,
    }


def render_report(
    report: PropertyReport,
    *,
    sections: dict,
    custom_template: Optional[str] = None,
) -> list:
    context = _build_context(report, sections)
    if custom_template:
        tpl_path = Path(custom_template)
        env = Environment(
            loader=FileSystemLoader(str(tpl_path.parent)),
            keep_trailing_newline=True,
        )
    else:
        env = Environment(
            loader=FileSystemLoader(str(_TEMPLATES_DIR)),
            keep_trailing_newline=True,
        )
        tpl_path = Path("default.json.j2")
    env.globals["trend"] = _trend
    env.globals["trend_pos"] = _trend_pos
    env.globals["extract_path"] = _extract_path
    env.globals["format_duration"] = _format_duration
    env.globals["format_bounce_rate"] = _format_bounce_rate
    template = env.get_template(tpl_path.name)
    rendered = template.render(**context)
    return json.loads(rendered)
