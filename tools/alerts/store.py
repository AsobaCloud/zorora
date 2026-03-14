"""SQLite-backed recurring digest alerts store."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional


class AlertStore:
    """Stores saved digest alerts and their result history."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = Path(db_path or (Path.home() / ".zorora" / "alerts.db"))
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._init_schema()

    def _get_connection(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn"):
            self._local.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    @property
    def conn(self) -> sqlite3.Connection:
        return self._get_connection()

    def close(self):
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            try:
                conn.close()
            finally:
                delattr(self._local, "conn")

    def _init_schema(self):
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS digest_alerts (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                topic TEXT,
                date_window_days INTEGER NOT NULL DEFAULT 7,
                article_limit INTEGER NOT NULL DEFAULT 100,
                staged_series_json TEXT,
                interval TEXT NOT NULL DEFAULT 'daily',
                last_run_at TEXT,
                created_at TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS digest_alert_results (
                id TEXT PRIMARY KEY,
                alert_id TEXT NOT NULL,
                run_at TEXT NOT NULL,
                synthesis TEXT,
                article_count INTEGER,
                articles_json TEXT,
                market_snapshot_json TEXT,
                read INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        self.conn.commit()

    def create_alert(
        self,
        name: str,
        topic: str,
        date_window_days: int,
        article_limit: int,
        staged_series: list[str],
        interval: str,
    ) -> str:
        alert_id = str(uuid.uuid4())
        self.conn.execute(
            """
            INSERT INTO digest_alerts
            (id, name, topic, date_window_days, article_limit, staged_series_json, interval, last_run_at, created_at, enabled)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                alert_id,
                name,
                topic,
                int(date_window_days),
                int(article_limit),
                json.dumps(staged_series or []),
                interval,
                None,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        self.conn.commit()
        return alert_id

    def list_alerts(self) -> list[dict]:
        rows = self.conn.execute(
            """
            SELECT a.*, COALESCE((
                SELECT COUNT(*)
                FROM digest_alert_results r
                WHERE r.alert_id = a.id AND r.read = 0
            ), 0) AS unread_count
            FROM digest_alerts a
            ORDER BY a.created_at DESC
            """
        ).fetchall()
        return [self._row_to_alert(row) | {"unread_count": row["unread_count"]} for row in rows]

    def get_alert(self, alert_id: str) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT * FROM digest_alerts WHERE id = ?",
            (alert_id,),
        ).fetchone()
        return self._row_to_alert(row) if row else None

    def update_alert(self, alert_id: str, **kwargs):
        if not kwargs:
            return
        fields = []
        params = []
        for key, value in kwargs.items():
            if key == "staged_series":
                key = "staged_series_json"
                value = json.dumps(value or [])
            if key == "enabled":
                value = 1 if value else 0
            fields.append(f"{key} = ?")
            params.append(value)
        params.append(alert_id)
        self.conn.execute(
            f"UPDATE digest_alerts SET {', '.join(fields)} WHERE id = ?",
            params,
        )
        self.conn.commit()

    def delete_alert(self, alert_id: str):
        self.conn.execute("DELETE FROM digest_alert_results WHERE alert_id = ?", (alert_id,))
        self.conn.execute("DELETE FROM digest_alerts WHERE id = ?", (alert_id,))
        self.conn.commit()

    def store_result(
        self,
        alert_id: str,
        synthesis: str,
        article_count: int,
        articles: list[dict],
        market_snapshot: Optional[dict],
    ) -> str:
        result_id = str(uuid.uuid4())
        self.conn.execute(
            """
            INSERT INTO digest_alert_results
            (id, alert_id, run_at, synthesis, article_count, articles_json, market_snapshot_json, read)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0)
            """,
            (
                result_id,
                alert_id,
                datetime.now(timezone.utc).isoformat(),
                synthesis,
                int(article_count),
                json.dumps(articles or []),
                json.dumps(market_snapshot or {}),
            ),
        )
        self.conn.commit()
        return result_id

    def get_results(self, alert_id: str, limit: int = 20, offset: int = 0) -> list[dict]:
        rows = self.conn.execute(
            """
            SELECT * FROM digest_alert_results
            WHERE alert_id = ?
            ORDER BY run_at DESC
            LIMIT ? OFFSET ?
            """,
            (alert_id, int(limit), int(offset)),
        ).fetchall()
        return [
            dict(row)
            | {
                "articles": json.loads(row["articles_json"] or "[]"),
                "market_snapshot": json.loads(row["market_snapshot_json"] or "{}"),
            }
            for row in rows
        ]

    def mark_read(self, result_id: str):
        self.conn.execute("UPDATE digest_alert_results SET read = 1 WHERE id = ?", (result_id,))
        self.conn.commit()

    def mark_all_read(self, alert_id: str):
        self.conn.execute("UPDATE digest_alert_results SET read = 1 WHERE alert_id = ?", (alert_id,))
        self.conn.commit()

    def get_due_alerts(self, now: Optional[datetime] = None) -> list[dict]:
        now = now or datetime.now(timezone.utc)
        rows = self.conn.execute("SELECT * FROM digest_alerts WHERE enabled = 1").fetchall()
        due = []
        for row in rows:
            alert = self._row_to_alert(row)
            last_run_at = alert.get("last_run_at")
            if not last_run_at:
                due.append(alert)
                continue
            last_run = datetime.fromisoformat(last_run_at)
            if last_run.tzinfo is None:
                last_run = last_run.replace(tzinfo=timezone.utc)
            delta = timedelta(days=1 if alert.get("interval") == "daily" else 7)
            if now - last_run >= delta:
                due.append(alert)
        return due

    def _row_to_alert(self, row: sqlite3.Row) -> dict:
        return {
            "id": row["id"],
            "name": row["name"],
            "topic": row["topic"],
            "date_window_days": row["date_window_days"],
            "article_limit": row["article_limit"],
            "staged_series": json.loads(row["staged_series_json"] or "[]"),
            "interval": row["interval"],
            "last_run_at": row["last_run_at"],
            "created_at": row["created_at"],
            "enabled": bool(row["enabled"]),
        }
