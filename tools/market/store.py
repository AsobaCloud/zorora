"""SQLite cache for market data — follows engine/storage.py pattern."""

from __future__ import annotations

import logging
import shutil
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)


class MarketDataStore:
    """Local SQLite store for market observations with staleness tracking."""

    _SEED_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "market_data.db"

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = str(Path.home() / ".zorora" / "market_data.db")
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # Seed from committed DB if user DB doesn't exist yet
        if not self.db_path.exists() and self._SEED_DB_PATH.exists():
            shutil.copy2(str(self._SEED_DB_PATH), str(self.db_path))
            logger.info("Seeded market_data.db from %s", self._SEED_DB_PATH)
        self._local = threading.local()
        self._init_schema()
        self._migrate_schema()

    # -- connection management ------------------------------------------------

    def _get_connection(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn"):
            self._local.conn = sqlite3.connect(
                str(self.db_path), check_same_thread=False
            )
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

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    # -- schema ---------------------------------------------------------------

    def _init_schema(self):
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS observations (
                provider TEXT NOT NULL DEFAULT 'fred',
                series_id TEXT NOT NULL,
                date TEXT NOT NULL,
                value REAL NOT NULL,
                PRIMARY KEY (provider, series_id, date)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS fetch_metadata (
                provider TEXT NOT NULL DEFAULT 'fred',
                series_id TEXT NOT NULL,
                last_fetched_at TEXT NOT NULL,
                last_observation_date TEXT,
                observation_count INTEGER DEFAULT 0,
                PRIMARY KEY (provider, series_id)
            )
        """)
        conn.commit()

    def _migrate_schema(self):
        """Migrate v1 tables (no provider column) to v2 (with provider)."""
        conn = self._get_connection()
        cur = conn.cursor()
        # Check if observations table has a provider column
        cur.execute("PRAGMA table_info(observations)")
        columns = {row["name"] for row in cur.fetchall()}
        if "provider" in columns:
            return  # Already migrated

        logger.info("Migrating market_data.db schema to add provider column")
        cur.executescript("""
            ALTER TABLE observations RENAME TO observations_v1;
            ALTER TABLE fetch_metadata RENAME TO fetch_metadata_v1;

            CREATE TABLE observations (
                provider TEXT NOT NULL DEFAULT 'fred',
                series_id TEXT NOT NULL,
                date TEXT NOT NULL,
                value REAL NOT NULL,
                PRIMARY KEY (provider, series_id, date)
            );
            INSERT INTO observations (provider, series_id, date, value)
                SELECT 'fred', series_id, date, value FROM observations_v1;

            CREATE TABLE fetch_metadata (
                provider TEXT NOT NULL DEFAULT 'fred',
                series_id TEXT NOT NULL,
                last_fetched_at TEXT NOT NULL,
                last_observation_date TEXT,
                observation_count INTEGER DEFAULT 0,
                PRIMARY KEY (provider, series_id)
            );
            INSERT INTO fetch_metadata (provider, series_id, last_fetched_at, last_observation_date, observation_count)
                SELECT 'fred', series_id, last_fetched_at, last_observation_date, observation_count FROM fetch_metadata_v1;

            DROP TABLE observations_v1;
            DROP TABLE fetch_metadata_v1;
        """)
        conn.commit()
        logger.info("Schema migration complete")

    # -- writes ---------------------------------------------------------------

    def upsert_observations(
        self, series_id: str, observations: List[Tuple[str, float]], provider: str = "fred"
    ):
        """Insert or replace observations and update metadata."""
        if not observations:
            return
        conn = self.conn
        cur = conn.cursor()
        cur.executemany(
            "INSERT OR REPLACE INTO observations (provider, series_id, date, value) VALUES (?, ?, ?, ?)",
            [(provider, series_id, d, v) for d, v in observations],
        )
        last_date = max(d for d, _ in observations)
        now_utc = datetime.now(timezone.utc).isoformat()
        cur.execute(
            "SELECT COUNT(*) FROM observations WHERE provider = ? AND series_id = ?",
            (provider, series_id),
        )
        actual_count = cur.fetchone()[0]
        cur.execute(
            """INSERT OR REPLACE INTO fetch_metadata
               (provider, series_id, last_fetched_at, last_observation_date, observation_count)
               VALUES (?, ?, ?, ?, ?)""",
            (provider, series_id, now_utc, last_date, actual_count),
        )
        conn.commit()
        logger.debug("Upserted %d obs for %s/%s (last=%s)", len(observations), provider, series_id, last_date)

    # -- reads ----------------------------------------------------------------

    def get_last_observation_date(self, series_id: str, provider: str = "fred") -> Optional[str]:
        """Return the most recent observation date stored, or None."""
        cur = self.conn.cursor()
        cur.execute(
            "SELECT last_observation_date FROM fetch_metadata WHERE provider = ? AND series_id = ?",
            (provider, series_id),
        )
        row = cur.fetchone()
        return row["last_observation_date"] if row else None

    def get_staleness(self, series_id: str, provider: str = "fred") -> Optional[float]:
        """Return hours since last fetch, or None if never fetched."""
        cur = self.conn.cursor()
        cur.execute(
            "SELECT last_fetched_at FROM fetch_metadata WHERE provider = ? AND series_id = ?",
            (provider, series_id),
        )
        row = cur.fetchone()
        if not row:
            return None
        last = datetime.fromisoformat(row["last_fetched_at"])
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - last
        return delta.total_seconds() / 3600.0

    def get_series_df(
        self,
        series_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        provider: str = "fred",
    ) -> pd.DataFrame:
        """Return a DataFrame with DatetimeIndex for one series."""
        query = "SELECT date, value FROM observations WHERE provider = ? AND series_id = ?"
        params: list = [provider, series_id]
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)
        query += " ORDER BY date"

        cur = self.conn.cursor()
        cur.execute(query, params)
        rows = cur.fetchall()
        if not rows:
            return pd.DataFrame(columns=["value"])
        df = pd.DataFrame(rows, columns=["date", "value"])
        df["date"] = pd.to_datetime(df["date"])
        df.set_index("date", inplace=True)
        return df

    def get_multi_series_df(
        self, series_ids: List[str], start_date: Optional[str] = None
    ) -> pd.DataFrame:
        """Return a DataFrame with one column per series (using labels)."""
        from tools.market.series import SERIES_CATALOG

        frames = {}
        for sid in series_ids:
            series = SERIES_CATALOG.get(sid)
            provider = series.provider if series else "fred"
            df = self.get_series_df(sid, start_date=start_date, provider=provider)
            label = series.label if series else sid
            if not df.empty:
                frames[label] = df["value"]
        if not frames:
            return pd.DataFrame()
        return pd.DataFrame(frames)
