# 지표 리포트 외부 API 노트

2026-10-31 실제 호출로 확인한 형태. 수치·키워드 원본은 적지 않는다(레포 PUBLIC).

## 네이버 서치어드바이저 (비공식 내부 API)

- 호출 위치: `aside repl --account u7`(Aside "누구뽑지" 프로필, 네이버 `noo` 아이디 로그인). 다른 프로필은 noo9.kr 권한이 없다.
- 페이지 컨텍스트에서 호출해야 한다: `openTab('https://searchadvisor.naver.com/console/site/report/expose?site=https%3A%2F%2Fwww.noo9.kr')` 후 `page.evaluate(() => fetch(url, { credentials: 'include' }))`.
- Playwright `page.on('request')` 이벤트는 Aside repl에서 동작하지 않는다(네트워크 확인은 `performance.getEntriesByType('resource')`).
- 엔드포인트 (상대 경로):

```
GET /api-console/report/expose/{siteHash}?site=https:%2F%2Fwww.noo9.kr&period={P}&device={D}&topN={N}
siteHash = 8e352bf0c86e587880e7dcd0f80a414fc844acb31b50755f77ae25ac4daa26a8
P ∈ {1, 7, 30, 60, 90}   (14 등 그 외 → code 151 FAIL_NOT_EXIST_DATA, items [])
D = d(PC+Mobile) | m(Mobile) | p(PC로 추정, 미확인)
N = 최대 1000
```

- 응답 (code 0 = 성공, 응답 시간 0.1~0.3초):

```json
{
  "code": 0, "message": "SUCCESS",
  "meta": { "latestDate": "YYYYMMDD" },
  "items": [{
    "period": { "period": 7, "clickCount": 0, "exposeCount": 0, "ctr": 0.5,
                "prevClickRatio": 36.6, "prevExposeRatio": 9, "prevCtrRatio": 0.1, "emptyRatio": false },
    "querys": [{ "key": "<검색어>", "clickCount": 0, "exposeCount": 0, "ctr": 29.7, "exposedRank": 1.4 }],
    "urls":   [{ "key": "https://www.noo9.kr/<퍼센트 인코딩 경로>", "clickCount": 0, "exposeCount": 0, "ctr": 2.6, "exposedRank": 2.9 }],
    "logs":   [{ "date": "YYYYMMDD", "clickCount": 0, "exposeCount": 0, "ctr": 0.5, "exposedRank": 1, "wmtSite": false }]
  }]
}
```

- `ctr`는 **퍼센트 값**(29.7 = 29.7%). `logs`는 기간 내 일별 총계(정렬 안 됨 → date로 정렬).
- 한 번 호출로 기간 총계·키워드·URL·일별 총계를 모두 받는다.
- topN=1000일 때 행 수(10/31 기준): P=1 → 50/50(상한 50으로 보임), P=7 → querys 282 / urls 195, P=30 → 829 / 415, P=90 → 1000 / 616.
- 데이터 지연 1일(10/31에 latestDate 20261030).
- 로그인 안 됨/권한 없음: 콘솔이 "오류 - 네이버 서치어드바이저 / 접근권한이 없습니다" 페이지로 바뀐다. 스크립트는 page title에 `오류`가 있거나 응답 code ≠ 0이면 실패로 처리한다.

## Amplitude Dashboard REST

- Free 플랜에서 동작 확인. 인증은 `curl -u "$KEY:$SECRET"`(Basic). 호스트 `https://amplitude.com/api/2/`.
- `GET users?start=YYYYMMDD&end=YYYYMMDD&m=active|new&i=1|7|30` → `data.series[0]`(값 배열), `data.xValues`(날짜).
- `GET events/segmentation?e=<json>&m=uniques|totals&start&end[&limit]`
  - group by: `e={"event_type":"[Amplitude] Page Viewed","group_by":[{"type":"event","value":"referring_domain"}]}`
  - 응답: `data.seriesLabels`(`[[0, "<값>"], ...]`), `data.seriesCollapsed`(`[[{"setId":"","value":N}], ...]` 기간 합계), `data.series`, `data.xValues`.
  - referring_domain 값 예: `m.search.naver.com`, `search.naver.com`, `(none)`, `www.noo9.kr`(내부 이동), `www.google.com`.
  - 필터: `"filters":[{"subprop_type":"event","subprop_key":"[Amplitude] Page Domain","subprop_op":"is not","subprop_value":["localhost"]}]` 동작 확인.
- `GET retention?se=<json>&re=<json>&start&end&i=1|7`
  - `data.series[0].combined` = `[{count, outof, incomplete}, ...]`.
  - **인덱스 의미**: `[0]` = 코호트 크기, `[1]` = 같은 기간(0일차/0주차) 재활동, `[2]` = 1일 후/1주 후. 즉 Week 1 재방문율 = `combined[2].count / combined[2].outof`, D1 = i=1의 `combined[2]`, D7 = `combined[8]`.
  - se=`{"event_type":"_new"}`, re=`{"event_type":"_active"}`.
  - 참고: 10월 코호트에서 Week 1 재방문은 거의 0명(D2~D8도 0). 지표 값이 대부분 0%로 나올 수 있다.
- 이벤트 속성: `[Amplitude] Page Domain`(값 `www.noo9.kr`, `noo9.kr`), `[Amplitude] Page Path`(**디코딩된 한글 경로**), `referring_domain`, `referrer`.
- 사용자 속성: `gp:initial_referring_domain`, `gp:referring_domain`, `gp:initial_referrer` 등(`gp:` 접두사). **최초 랜딩 페이지 속성은 없다.**
- 이벤트 목록에 **`Signed Up` 없음** → 가입 수 지표 미지원.
- 랜딩 페이지별 재방문율: 전용 속성이 없어 근사만 가능 — se=`[Amplitude] Page Viewed` + 필터(Page Path = 경로, referring_domain ∈ 네이버) → re=`_active`, i=7. 페이지당 쿼리 1회.
- 프로젝트 타임존: 미확인(Task 6 dry-run에서 Amplitude 화면 값과 대조).

## Slack

- 웹훅 대상 채널: `#트래픽알리미` (noo9vote). 2026-10-31 기준 멤버 4명 / 워크스페이스 활성 멤버 9명. 전원 공유 여부는 운영 전환(Task 8) 전에 결정.
