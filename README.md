# ga4-slack-report

Automatically collect Google Analytics 4 traffic data and deliver reports to Slack.

[한국어 README](README_ko.md)

**Features:**

- Multi-property support
- Customizable report periods (daily / weekly / biweekly / monthly / custom)
- Customizable comparison baselines (previous period / same period last week / custom)
- Per-section toggle (summary, traffic sources, pages, devices)
- Slack Webhook + OAuth dual delivery
- Fully customizable message layout via Jinja2 templates
- Automated via GitHub Actions

## Quick Start

### 1. Clone

```bash
git clone https://github.com/your-username/ga4-slack-report.git
cd ga4-slack-report
pip install -r requirements.txt
```

### 2. Create a Google Cloud Service Account

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. **APIs & Services > Library** > search "Google Analytics Data API" > **Enable**
3. **APIs & Services > Credentials** > **Create Service Account**
4. Service Account > **Keys > Add Key > JSON** > download

### 3. Add Service Account to GA4

1. Go to [Google Analytics](https://analytics.google.com/)
2. **Admin > Property > Property Access Management**
3. **Add users** > enter service account email (permission: Viewer or above)

### 4. Set Up Slack

**Webhook (simple):**
1. [Slack API](https://api.slack.com/apps) > **Create New App** > **From scratch**
2. **Incoming Webhooks** > Activate > **Add New Webhook to Workspace**
3. Select channel > copy Webhook URL

**OAuth (flexible):**
1. Create Slack App, then **OAuth & Permissions** > add scopes: `chat:write`, `chat:write.public`
2. Install to workspace > copy Bot User OAuth Token
3. Note the target channel ID

### 5. Create Config

```bash
cp config.example.yaml config.yaml
cp .env.example .env
```

- `config.yaml` — edit property IDs, report period, etc.
- `.env` — fill in your service account JSON, Slack Webhook URL, etc.

### 6. Set Env Vars and Run

Fill in the values in your `.env` file, or export them directly in the terminal.

```bash
# Option 1: Use .env file (recommended)
set -a && source .env && set +a && python main.py config.yaml

# Option 2: Export directly
export GOOGLE_SERVICE_ACCOUNT_JSON='{"type":"service_account","project_id":"...","private_key":"...",...}'
export SLACK_WEBHOOK_URL='https://hooks.slack.com/services/T.../B.../xxxx'
python main.py config.yaml
```

> **Note:** `GOOGLE_SERVICE_ACCOUNT_JSON` must contain the **entire** service account JSON key as a single line. Copy the full contents of the downloaded JSON file.

## Configuration Reference

### schedule

| Key | Type | Default | Description |
|---|---|---|---|
| `period` | string | `daily` | `daily` `weekly` `biweekly` `monthly` `custom` |
| `compare` | string | `previous_period` | `previous_period` `same_period_last_week` `custom` |
| `data_delay_days` | int | `1` | Days to offset for GA4 data delay |
| `custom.current_days` | int | `7` | Current period length when `period: custom` |
| `custom.previous_days` | int | `7` | Previous period length |

**Date range examples** (data_delay_days=1, today=4/11):

| period | Current | Previous (previous_period) |
|---|---|---|
| daily | 4/10 | 4/9 |
| weekly | 4/4 ~ 4/10 | 3/28 ~ 4/3 |
| biweekly | 3/28 ~ 4/10 | 3/14 ~ 3/27 |
| monthly | 3/12 ~ 4/10 | 2/10 ~ 3/11 |

### properties

```yaml
properties:
  - name: "My Website"
    property_id: "123456789"
  - name: "Blog"
    property_id: "987654321"
```

> **Finding your Property ID:** Google Analytics > Admin > Property Settings > Property ID

### google

| Key | Description |
|---|---|
| `credentials_env` | Env var name containing the full service account JSON |

### slack

| Key | Type | Default | Description |
|---|---|---|---|
| `method` | string | `webhook` | `webhook` or `oauth` |
| `webhook_url_env` | string | | Env var name for Webhook URL |
| `token_env` | string | | Env var name for OAuth token |
| `channel_id` | string | | Required for `oauth`, Slack channel ID |

### report

| Key | Type | Default | Description |
|---|---|---|---|
| `sections.summary` | bool | `true` | Overall summary (users, sessions, pageviews, duration, bounce rate) |
| `sections.traffic_sources` | bool | `true` | Top traffic sources |
| `sections.top_pages` | bool | `true` | Top pages by pageviews |
| `sections.top_devices` | bool | `false` | Device category breakdown |
| `top_n` | int | `10` | Number of top items |
| `multi_site_mode` | string | `separate` | `separate` (one message per property) / `combined` |
| `custom_template` | string | `null` | Path to custom Jinja2 template |

## Custom Templates

Use your own Slack Block Kit layout instead of the default.

### 1. Create a template file

`templates/my-custom.json.j2`:

```jinja2
[
  {
    "type": "section",
    "text": {
      "type": "mrkdwn",
      "text": "*{{ property_name }}* Report\nUsers: {{ current.active_users }} ({{ trend(diffs.active_users_pct, '%') }})"
    }
  }
]
```

### 2. Reference it in config.yaml

```yaml
report:
  custom_template: templates/my-custom.json.j2
```

### Available Variables

| Variable | Type | Description |
|---|---|---|
| `property_name` | string | Property name |
| `property_id` | string | GA4 Property ID |
| `current_range[0]` / `current_range[1]` | date | Current period start/end |
| `previous_range[0]` / `previous_range[1]` | date | Previous period start/end |
| `current.active_users` / `.sessions` / `.pageviews` | int | Current metrics |
| `current.avg_session_duration` | float | Average session duration (seconds) |
| `current.bounce_rate` | float | Bounce rate (0-1) |
| `previous.*` | number | Previous period metrics |
| `diffs.active_users_pct` / `.sessions_pct` / `.pageviews_pct` | float | Change rate (%) |
| `diffs.avg_session_duration_pct` | float | Duration change (%) |
| `diffs.bounce_rate_diff` | float | Bounce rate change (%p) |
| `traffic_sources` | list | Top sources `[{source, medium, sessions}]` |
| `pages` | list | Top pages `[{path, pageviews, active_users}]` |
| `devices` | list | Device breakdown `[{category, sessions}]` |

### Available Functions

| Function | Description | Example |
|---|---|---|
| `trend(diff, unit)` | Change arrow | `trend(diffs.active_users_pct, "%")` -> `(▲ +25.0%)` |
| `format_duration(sec)` | Format seconds | `format_duration(125.5)` -> `2m 5s` |
| `format_bounce_rate(rate)` | Format bounce rate | `format_bounce_rate(0.45)` -> `45.0%` |

## GitHub Actions

### Register Secrets

Repo **Settings > Secrets and variables > Actions**:

| Secret | Required | Description |
|---|---|---|
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Yes | Full service account JSON key |
| `SLACK_WEBHOOK_URL` | Conditional | Required for webhook method |
| `SLACK_USER_OAUTH_TOKEN` | Conditional | Required for oauth method |

### Change Schedule

Edit the cron value in `.github/workflows/ga4-slack-report.yml` (UTC):

```yaml
schedule:
  - cron: "0 0 * * 1"    # Weekly Mon 09:00 KST
  - cron: "0 0 * * *"    # Daily at 09:00 KST
  - cron: "0 0 * * 1-5"  # Weekdays 09:00 KST
```

### Manual Run

Actions tab > "GA4 Report -> Slack" > **Run workflow**

## Project Structure

```
ga4-slack-report/
├── ga4_report/              # Core package
│   ├── config.py            # YAML config loader + validation
│   ├── ga4_client.py        # GA4 Data API client + date range calculation
│   ├── report.py            # Data collection + diff calculation
│   ├── renderer.py          # Slack Block Kit renderer
│   ├── slack.py             # Webhook / OAuth delivery
│   └── templates/
│       ├── default.json.j2      # Default English template
│       └── default_ko.json.j2   # Korean template
├── tests/                   # pytest tests
├── config.example.yaml      # Example config
├── .env.example             # Example environment variables
├── main.py                  # Entrypoint
└── requirements.txt         # Dependencies
```

## Local Development

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

## License

MIT
