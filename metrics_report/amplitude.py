"""Amplitude Dashboard REST client."""
from __future__ import annotations

import base64
import json
import urllib.request
from typing import Literal
from urllib.parse import urlencode

from metrics_report.periods import Period

BASE_URL = "https://amplitude.com/api/2/"
TIMEOUT_SEC = 60
DATE_FMT = "%Y%m%d"
PAGE_VIEWED = "[Amplitude] Page Viewed"
LOCALHOST_FILTER = {
    "subprop_type": "event",
    "subprop_key": "[Amplitude] Page Domain",
    "subprop_op": "is not",
    "subprop_value": ["localhost"],
}
NAVER_DOMAINS = ["m.search.naver.com", "search.naver.com"]
INITIAL_REFERRER_PROP = "gp:initial_referring_domain"
GROUP_LIMIT = 100


def parse_series(payload: dict) -> list[int]:
    return payload["data"]["series"][0]


def parse_retention(payload: dict, n: int) -> float | None:
    """Ratio at period n after cohort (combined[0]=cohort, [1]=same period).

    None if the cell is still `incomplete`: callers must pass mature cohorts.
    """
    combined = payload["data"]["series"][0]["combined"]
    if n + 1 >= len(combined):
        return None
    cell = combined[n + 1]
    if cell.get("incomplete") or not cell["outof"]:
        return None
    return cell["count"] / cell["outof"]


def parse_grouped(payload: dict) -> dict[str, int]:
    d = payload["data"]
    return {
        label[1]: d["seriesCollapsed"][i][0]["value"]
        for i, label in enumerate(d["seriesLabels"])
    }


def _collapsed(payload: dict) -> int:
    return payload["data"]["seriesCollapsed"][0][0]["value"]


def _event(event_type: str, **extra) -> dict:
    return {"event_type": event_type, "filters": [LOCALHOST_FILTER], **extra}


class AmplitudeClient:
    def __init__(self, api_key: str, secret_key: str, opener=urllib.request.urlopen):
        token = base64.b64encode(f"{api_key}:{secret_key}".encode()).decode()
        self._auth = f"Basic {token}"
        self._open = opener

    def _get(self, path: str, params: dict) -> dict:
        req = urllib.request.Request(
            f"{BASE_URL}{path}?{urlencode(params)}",
            headers={"Authorization": self._auth},
        )
        with self._open(req, timeout=TIMEOUT_SEC) as resp:
            return json.loads(resp.read())

    @staticmethod
    def _range(p: Period) -> dict:
        return {"start": p.start.strftime(DATE_FMT), "end": p.end.strftime(DATE_FMT)}

    def _users(self, p: Period, m: str, interval: int) -> list[int]:
        return parse_series(self._get("users", {**self._range(p), "m": m, "i": interval}))

    def _seg(self, p: Period, event: dict, m: str, **extra) -> dict:
        params = {"e": json.dumps(event), "m": m, **self._range(p), **extra}
        return self._get("events/segmentation", params)

    def active_users(self, p: Period, interval: Literal[1, 7, 30]) -> list[int]:
        """Values per interval. ponytail: /users takes only user-property segments,
        so the localhost filter (an event property) can't apply here."""
        return self._users(p, "active", interval)

    def new_users(self, p: Period) -> int:
        """Not localhost-filtered (see active_users)."""
        return sum(self._users(p, "new", 1))

    def pageviews(self, p: Period) -> tuple[int, int]:
        ev = _event(PAGE_VIEWED)
        return (
            _collapsed(self._seg(p, ev, "totals")),
            _collapsed(self._seg(p, ev, "uniques")),
        )

    def sessions(self, p: Period) -> int:
        return _collapsed(self._seg(p, _event("session_start"), "totals"))

    def users_by_referring_domain(self, p: Period) -> dict[str, int]:
        ev = _event(
            PAGE_VIEWED, group_by=[{"type": "event", "value": "referring_domain"}]
        )
        return parse_grouped(self._seg(p, ev, "uniques", limit=GROUP_LIMIT))

    def event_totals(self, p: Period, event_type: str) -> int:
        return _collapsed(self._seg(p, _event(event_type), "totals"))

    def _retention(
        self, p: Period, interval: int, n: int, se: dict, segment: dict | None = None
    ) -> float | None:
        params = {
            "se": json.dumps(se),
            "re": json.dumps(_event("_active")),
            "i": interval,
            **self._range(p),
        }
        if segment:
            params["s"] = json.dumps([segment])
        return parse_retention(self._get("retention", params), n)

    def next_period_retention(
        self,
        cohort: Period,
        interval: Literal[7, 30],
        source: Literal["naver", "other"] | None = None,
    ) -> float | None:
        segment = None
        if source:
            op = "is" if source == "naver" else "is not"
            segment = {"prop": INITIAL_REFERRER_PROP, "op": op, "values": NAVER_DOMAINS}
        return self._retention(cohort, interval, 1, _event("_new"), segment)

    def day_n_retention(
        self, cohort: Period, days: tuple[int, ...] = (1, 7)
    ) -> dict[int, float | None]:
        # one daily-interval query serves every n
        params = {
            "se": json.dumps(_event("_new")),
            "re": json.dumps(_event("_active")),
            "i": 1,
            **self._range(cohort),
        }
        payload = self._get("retention", params)
        return {n: parse_retention(payload, n) for n in days}

    def landing_retention_by_path(
        self, cohort: Period, paths: list[str]
    ) -> dict[str, float | None]:
        """Approximation: no landing-page user property exists, so use users who
        viewed `path` with a naver referring_domain, retained after 1 week."""
        out = {}
        for path in paths:
            se = {
                "event_type": PAGE_VIEWED,
                "filters": [
                    LOCALHOST_FILTER,
                    {
                        "subprop_type": "event",
                        "subprop_key": "[Amplitude] Page Path",
                        "subprop_op": "is",
                        "subprop_value": [path],
                    },
                    {
                        "subprop_type": "event",
                        "subprop_key": "referring_domain",
                        "subprop_op": "is",
                        "subprop_value": NAVER_DOMAINS,
                    },
                ],
            }
            out[path] = self._retention(cohort, 7, 1, se)
        return out
