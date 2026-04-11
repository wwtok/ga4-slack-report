from __future__ import annotations

import os

import pytest

from ga4_report.config import load_config

MINIMAL_YAML = """
properties:
  - name: "Test Site"
    property_id: "123456789"
google:
  credentials_env: GOOGLE_SA_JSON
slack:
  method: webhook
  webhook_url_env: SLACK_URL
"""

FULL_YAML = """
schedule:
  period: weekly
  compare: same_period_last_week
  data_delay_days: 2
properties:
  - name: "Blog"
    property_id: "111111111"
  - name: "Portfolio"
    property_id: "222222222"
google:
  credentials_env: MY_SA_JSON
slack:
  method: oauth
  token_env: MY_TOKEN
  channel_id: C12345
report:
  sections:
    summary: true
    traffic_sources: true
    top_pages: false
    top_devices: true
  top_n: 5
  multi_site_mode: combined
  custom_template: templates/my.json.j2
"""


def test_load_minimal_config(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text(MINIMAL_YAML)
    cfg = load_config(str(p))
    assert cfg.properties[0].name == "Test Site"
    assert cfg.properties[0].property_id == "123456789"
    assert cfg.schedule.period == "daily"
    assert cfg.schedule.data_delay_days == 1
    assert cfg.report.top_n == 10
    assert cfg.report.sections.summary is True
    assert cfg.report.sections.traffic_sources is True


def test_load_full_config(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text(FULL_YAML)
    cfg = load_config(str(p))
    assert cfg.schedule.period == "weekly"
    assert cfg.schedule.data_delay_days == 2
    assert len(cfg.properties) == 2
    assert cfg.properties[1].property_id == "222222222"
    assert cfg.slack.method == "oauth"
    assert cfg.slack.channel_id == "C12345"
    assert cfg.report.sections.top_pages is False
    assert cfg.report.sections.top_devices is True
    assert cfg.report.multi_site_mode == "combined"


def test_invalid_period_raises(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text(
        "schedule:\n  period: hourly\nproperties:\n  - name: T\n    property_id: '1'\ngoogle:\n  credentials_env: X\nslack:\n  method: webhook\n  webhook_url_env: Y\n"
    )
    with pytest.raises(ValueError, match="period"):
        load_config(str(p))


def test_no_properties_raises(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text(
        "properties: []\ngoogle:\n  credentials_env: X\nslack:\n  method: webhook\n  webhook_url_env: Y\n"
    )
    with pytest.raises(ValueError, match="propert"):
        load_config(str(p))


def test_oauth_requires_channel_id(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text(
        "properties:\n  - name: T\n    property_id: '1'\ngoogle:\n  credentials_env: X\nslack:\n  method: oauth\n  token_env: TOK\n"
    )
    with pytest.raises(ValueError, match="channel_id"):
        load_config(str(p))


def test_env_var_resolution(tmp_path, monkeypatch):
    p = tmp_path / "config.yaml"
    p.write_text(MINIMAL_YAML)
    cfg = load_config(str(p))
    monkeypatch.setenv("GOOGLE_SA_JSON", '{"type":"service_account"}')
    assert cfg.google.resolve_credentials(os.environ) == '{"type":"service_account"}'
