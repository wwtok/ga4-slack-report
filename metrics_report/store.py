"""SQLite store for rank snapshots, daily totals and run status."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

from metrics_report.periods import Period

STATUS_OK = "ok"

SCHEMA = """
CREATE TABLE IF NOT EXISTS ranks (
    snapshot_date TEXT NOT NULL,
    window_days INTEGER NOT NULL,
    kind TEXT NOT NULL,
    item TEXT NOT NULL,
    clicks INTEGER NOT NULL,
    impressions INTEGER NOT NULL,
    ctr REAL NOT NULL,
    exposed_rank REAL,
    PRIMARY KEY (snapshot_date, window_days, kind, item)
);
CREATE TABLE IF NOT EXISTS daily_totals (
    day TEXT PRIMARY KEY,
    impressions INTEGER NOT NULL,
    clicks INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
    job TEXT NOT NULL,
    label TEXT NOT NULL,
    status TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (job, label)
);
"""


@dataclass
class RankRow:
    kind: Literal["keyword", "url"]
    item: str
    clicks: int
    impressions: int
    ctr: float
    exposed_rank: float | None


@dataclass
class DailyTotal:
    day: date
    impressions: int
    clicks: int


class Store:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path)
        self._db.executescript(SCHEMA)

    def save_ranks(
        self, snapshot_date: date, window_days: int, rows: list[RankRow]
    ) -> None:
        snap = snapshot_date.isoformat()
        with self._db:
            # Replace the whole snapshot so stale rows don't linger
            self._db.execute(
                "DELETE FROM ranks WHERE snapshot_date=? AND window_days=?",
                (snap, window_days),
            )
            self._db.executemany(
                "INSERT INTO ranks VALUES (?,?,?,?,?,?,?,?)",
                [
                    (snap, window_days, r.kind, r.item, r.clicks,
                     r.impressions, r.ctr, r.exposed_rank)
                    for r in rows
                ],
            )

    def ranks(self, snapshot_date: date, window_days: int, kind: str) -> list[RankRow]:
        cur = self._db.execute(
            "SELECT kind, item, clicks, impressions, ctr, exposed_rank FROM ranks"
            " WHERE snapshot_date=? AND window_days=? AND kind=? ORDER BY rowid",
            (snapshot_date.isoformat(), window_days, kind),
        )
        return [RankRow(*row) for row in cur]

    def latest_rank_snapshot(self, window_days: int, before: date) -> date | None:
        (latest,) = self._db.execute(
            "SELECT MAX(snapshot_date) FROM ranks"
            " WHERE window_days=? AND snapshot_date<?",
            (window_days, before.isoformat()),
        ).fetchone()
        return date.fromisoformat(latest) if latest else None

    def save_daily_totals(self, rows: list[DailyTotal]) -> None:
        with self._db:
            self._db.executemany(
                "INSERT OR REPLACE INTO daily_totals VALUES (?,?,?)",
                [(r.day.isoformat(), r.impressions, r.clicks) for r in rows],
            )

    def daily_totals(self, p: Period) -> list[DailyTotal]:
        cur = self._db.execute(
            "SELECT day, impressions, clicks FROM daily_totals"
            " WHERE day BETWEEN ? AND ? ORDER BY day",
            (p.start.isoformat(), p.end.isoformat()),
        )
        return [DailyTotal(date.fromisoformat(d), i, c) for d, i, c in cur]

    def run_done(self, job: str, label: str) -> bool:
        row = self._db.execute(
            "SELECT status FROM runs WHERE job=? AND label=?", (job, label)
        ).fetchone()
        return row is not None and row[0] == STATUS_OK

    def mark_run(
        self, job: str, label: str, status: Literal["ok", "failed"], detail: str = ""
    ) -> None:
        with self._db:
            self._db.execute(
                "INSERT OR REPLACE INTO runs VALUES (?,?,?,?)",
                (job, label, status, detail),
            )
