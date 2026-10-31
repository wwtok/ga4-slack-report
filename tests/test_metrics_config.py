from pathlib import Path

import pytest

from metrics_report.config import load_settings

YAML = """
amplitude_project_id: "1"
naver_site: "https://example.com"
naver_site_hash: "abc"
aside_account: "u7"
confluence_base_url: "https://x.atlassian.net/wiki"
confluence_space_key: "SD"
confluence_parent_page_id: null
data_dir: "data"
out_dir: "out"
okr_links:
  "KR 3.1": "https://x/1"
"""

ENV = {
    "AMPLITUDE_API_KEY": "a",
    "AMPLITUDE_SECRET_KEY": "b",
    "CONFLUENCE_EMAIL": "e",
    "CONFLUENCE_API_TOKEN": "t",
    "SLACK_WEBHOOK_URL": "w",
}


def _yaml(tmp_path):
    p = tmp_path / "m.yaml"
    p.write_text(YAML)
    return str(p)


def test_load_settings_reads_yaml_and_env(tmp_path):
    s = load_settings(_yaml(tmp_path), ENV)
    assert s.amplitude_project_id == "1"
    assert s.naver_site_hash == "abc"
    assert s.aside_account == "u7"
    assert s.confluence_parent_page_id is None
    assert s.data_dir == Path("data")
    assert s.out_dir == Path("out")
    assert s.okr_links == {"KR 3.1": "https://x/1"}
    assert s.secrets.amplitude_api_key == "a"
    assert s.secrets.slack_webhook_url == "w"


def test_missing_secret_raises(tmp_path):
    env = {k: v for k, v in ENV.items() if k != "AMPLITUDE_SECRET_KEY"}
    with pytest.raises(ValueError, match="AMPLITUDE_SECRET_KEY"):
        load_settings(_yaml(tmp_path), env)
