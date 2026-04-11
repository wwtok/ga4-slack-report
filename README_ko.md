# ga4-slack-report

Google Analytics 4 트래픽 데이터를 자동 수집하여 Slack으로 리포트를 전송합니다.

[English README](README.md)

**주요 기능:**

- 멀티 프로퍼티 지원
- 리포트 기간 설정 가능 (일간 / 주간 / 격주 / 월간 / 커스텀)
- 비교 기준 설정 가능 (이전 기간 / 전주 동기간 / 커스텀)
- 섹션별 토글 (요약, 유입경로, 페이지, 디바이스)
- Slack Webhook + OAuth 이중 전송 지원
- Jinja2 템플릿으로 메시지 레이아웃 완전 커스텀 가능
- GitHub Actions로 자동화

## 빠른 시작

### 1. 클론

```bash
git clone https://github.com/your-username/ga4-slack-report.git
cd ga4-slack-report
pip install -r requirements.txt
```

### 2. Google Cloud 서비스 계정 생성

1. [Google Cloud Console](https://console.cloud.google.com/) 접속
2. **APIs & Services > 라이브러리** > "Google Analytics Data API" 검색 > **사용 설정**
3. **APIs & Services > 사용자 인증 정보** > **서비스 계정 만들기**
4. 서비스 계정 > **키 > 키 추가 > JSON** > 다운로드

### 3. GA4에 서비스 계정 추가

1. [Google Analytics](https://analytics.google.com/) 접속
2. **관리 > 속성 > 속성 액세스 관리**
3. **사용자 추가** > 서비스 계정 이메일 입력 (권한: 뷰어 이상)

### 4. Slack 설정

**Webhook (간단):**
1. [Slack API](https://api.slack.com/apps) > **Create New App** > **From scratch**
2. **Incoming Webhooks** > Activate > **Add New Webhook to Workspace**
3. 채널 선택 > Webhook URL 복사

**OAuth (유연):**
1. Slack App 생성 후 **OAuth & Permissions** > 스코프 추가: `chat:write`, `chat:write.public`
2. 워크스페이스에 설치 > Bot User OAuth Token 복사
3. 대상 채널 ID 메모

### 5. 설정 파일 생성

```bash
cp config.example.yaml config.yaml
cp .env.example .env
```

- `config.yaml` — 프로퍼티 ID, 리포트 기간 등 편집
- `.env` — 서비스 계정 JSON, Slack Webhook URL 등 입력

### 6. 환경변수 설정 및 실행

`.env` 파일에 값을 입력하거나, 터미널에서 직접 export합니다.

```bash
# 방법 1: .env 파일 사용 (권장)
set -a && source .env && set +a && python main.py config.yaml

# 방법 2: 직접 export
export GOOGLE_SERVICE_ACCOUNT_JSON='{"type":"service_account","project_id":"...","private_key":"...",...}'
export SLACK_WEBHOOK_URL='https://hooks.slack.com/services/T.../B.../xxxx'
python main.py config.yaml
```

> **참고:** `GOOGLE_SERVICE_ACCOUNT_JSON`에는 다운로드한 서비스 계정 JSON 키의 **전체 내용**을 한 줄로 넣어야 합니다.

## 설정 레퍼런스

### schedule

| 키 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `period` | string | `daily` | `daily` `weekly` `biweekly` `monthly` `custom` |
| `compare` | string | `previous_period` | `previous_period` `same_period_last_week` `custom` |
| `data_delay_days` | int | `1` | GA4 데이터 지연 보정 일수 |
| `custom.current_days` | int | `7` | `period: custom` 시 현재 기간 일수 |
| `custom.previous_days` | int | `7` | 이전 기간 일수 |

**날짜 범위 예시** (data_delay_days=1, 오늘=4/11):

| period | 현재 기간 | 이전 기간 (previous_period) |
|---|---|---|
| daily | 4/10 | 4/9 |
| weekly | 4/4 ~ 4/10 | 3/28 ~ 4/3 |
| biweekly | 3/28 ~ 4/10 | 3/14 ~ 3/27 |
| monthly | 3/12 ~ 4/10 | 2/10 ~ 3/11 |

### properties

```yaml
properties:
  - name: "내 웹사이트"
    property_id: "123456789"
  - name: "블로그"
    property_id: "987654321"
```

> **Property ID 찾기:** Google Analytics > 관리 > 속성 설정 > 속성 ID

### google

| 키 | 설명 |
|---|---|
| `credentials_env` | 서비스 계정 JSON이 담긴 환경변수 이름 |

### slack

| 키 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `method` | string | `webhook` | `webhook` 또는 `oauth` |
| `webhook_url_env` | string | | Webhook URL이 담긴 환경변수 이름 |
| `token_env` | string | | OAuth 토큰이 담긴 환경변수 이름 |
| `channel_id` | string | | `oauth` 시 필수, Slack 채널 ID |

### report

| 키 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `sections.summary` | bool | `true` | 전체 요약 (사용자, 세션, 페이지뷰, 체류시간, 이탈률) |
| `sections.traffic_sources` | bool | `true` | 유입 경로 |
| `sections.top_pages` | bool | `true` | TOP 페이지 |
| `sections.top_devices` | bool | `false` | 디바이스 분포 |
| `top_n` | int | `10` | 상위 항목 수 |
| `multi_site_mode` | string | `separate` | `separate` (프로퍼티별 개별 메시지) / `combined` |
| `custom_template` | string | `null` | 커스텀 Jinja2 템플릿 경로 |

## 커스텀 템플릿

기본 템플릿 대신 직접 만든 Slack Block Kit 레이아웃을 사용할 수 있습니다.

### 한글 리포트 사용

```yaml
report:
  custom_template: ga4_report/templates/default_ko.json.j2
```

### 직접 만들기

`templates/my-custom.json.j2`:

```jinja2
[
  {
    "type": "section",
    "text": {
      "type": "mrkdwn",
      "text": "*{{ property_name }}* 리포트\n사용자: {{ current.active_users }} ({{ trend(diffs.active_users_pct, '%') }})"
    }
  }
]
```

```yaml
report:
  custom_template: templates/my-custom.json.j2
```

### 사용 가능한 변수

| 변수 | 타입 | 설명 |
|---|---|---|
| `property_name` | string | 프로퍼티 이름 |
| `property_id` | string | GA4 Property ID |
| `current_range[0]` / `current_range[1]` | date | 현재 기간 시작/끝 |
| `previous_range[0]` / `previous_range[1]` | date | 이전 기간 시작/끝 |
| `current.active_users` / `.sessions` / `.pageviews` | int | 현재 기간 지표 |
| `current.avg_session_duration` | float | 평균 세션 시간 (초) |
| `current.bounce_rate` | float | 이탈률 (0-1) |
| `diffs.active_users_pct` / `.sessions_pct` / `.pageviews_pct` | float | 변화율 (%) |
| `diffs.avg_session_duration_pct` | float | 세션 시간 변화율 (%) |
| `diffs.bounce_rate_diff` | float | 이탈률 변화 (%p) |
| `traffic_sources` | list | 유입 경로 `[{source, medium, sessions}]` |
| `pages` | list | TOP 페이지 `[{path, pageviews, active_users}]` |
| `devices` | list | 디바이스 `[{category, sessions}]` |

### 사용 가능한 함수

| 함수 | 설명 | 예시 |
|---|---|---|
| `trend(diff, unit)` | 변화 화살표 | `trend(diffs.active_users_pct, "%")` -> `(▲ +25.0%)` |
| `format_duration(sec)` | 초 → 시간 포맷 | `format_duration(125.5)` -> `2m 5s` |
| `format_bounce_rate(rate)` | 이탈률 포맷 | `format_bounce_rate(0.45)` -> `45.0%` |

## GitHub Actions

### Secrets 등록

레포 **Settings > Secrets and variables > Actions**:

| Secret | 필수 여부 | 설명 |
|---|---|---|
| `GOOGLE_SERVICE_ACCOUNT_JSON` | 필수 | 서비스 계정 JSON 키 전체 |
| `SLACK_WEBHOOK_URL` | 조건부 | webhook 방식일 때 필수 |
| `SLACK_USER_OAUTH_TOKEN` | 조건부 | oauth 방식일 때 필수 |

### 스케줄 변경

`.github/workflows/ga4-slack-report.yml`의 cron 값을 수정합니다 (UTC 기준):

```yaml
schedule:
  - cron: "0 0 * * 1"    # 매주 월요일 KST 09:00
  - cron: "0 0 * * *"    # 매일 KST 09:00
  - cron: "0 0 * * 1-5"  # 평일 KST 09:00
```

### 수동 실행

Actions 탭 > "GA4 Report -> Slack" > **Run workflow**

## 프로젝트 구조

```
ga4-slack-report/
├── ga4_report/              # 코어 패키지
│   ├── config.py            # YAML 설정 로더 + 검증
│   ├── ga4_client.py        # GA4 Data API 클라이언트 + 날짜 범위 계산
│   ├── report.py            # 데이터 수집 + 변화율 계산
│   ├── renderer.py          # Slack Block Kit 렌더러
│   ├── slack.py             # Webhook / OAuth 전송
│   └── templates/
│       ├── default.json.j2      # 기본 영문 템플릿
│       └── default_ko.json.j2   # 한국어 템플릿
├── tests/                   # pytest 테스트
├── config.example.yaml      # 설정 예시
├── .env.example             # 환경변수 예시
├── main.py                  # 엔트리포인트
└── requirements.txt         # 의존성
```

## 로컬 개발

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

## 라이선스

MIT
