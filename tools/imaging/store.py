"""SQLite cache for imaging/deposit data — follows MarketDataStore pattern."""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class ImagingDataStore:
    """Local SQLite store for mineral deposit and concession data."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = self._default_db_path()
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._init_schema()

    @staticmethod
    def _default_db_path() -> str:
        return str(Path.home() / ".zorora" / "imaging_data.db")

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

    def _init_schema(self):
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS deposits (
                id TEXT PRIMARY KEY,
                name TEXT,
                lat REAL,
                lon REAL,
                commodity TEXT,
                deposit_type TEXT,
                dev_status TEXT,
                country TEXT,
                properties_json TEXT,
                fetched_at TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS concessions (
                id TEXT PRIMARY KEY,
                name TEXT,
                lat REAL,
                lon REAL,
                operator TEXT,
                mineral_type TEXT,
                status TEXT,
                country TEXT,
                properties_json TEXT,
                fetched_at TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS fetch_metadata (
                layer TEXT PRIMARY KEY,
                last_fetched_at TEXT,
                record_count INTEGER DEFAULT 0
            )
        """)
        conn.commit()

    # -- writes ---------------------------------------------------------------

    def upsert_deposits(self, features: list):
        """Insert or replace deposit features and update metadata."""
        if not features:
            return
        conn = self.conn
        cur = conn.cursor()
        now_utc = datetime.now(timezone.utc).isoformat()
        for feat in features:
            props = feat.get("properties", {})
            coords = feat.get("geometry", {}).get("coordinates", [0, 0])
            dep_id = props.get("dep_id", f"{coords[0]}_{coords[1]}")
            cur.execute(
                """INSERT OR REPLACE INTO deposits
                   (id, name, lat, lon, commodity, deposit_type, dev_status,
                    country, properties_json, fetched_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    dep_id,
                    props.get("name", ""),
                    props.get("latitude", coords[1]),
                    props.get("longitude", coords[0]),
                    props.get("commod1", ""),
                    props.get("dep_type", ""),
                    props.get("dev_stat", ""),
                    props.get("country", ""),
                    json.dumps(props),
                    now_utc,
                ),
            )
        cur.execute(
            """INSERT OR REPLACE INTO fetch_metadata (layer, last_fetched_at, record_count)
               VALUES ('deposits', ?, ?)""",
            (now_utc, len(features)),
        )
        conn.commit()

    def upsert_concessions(self, features: list):
        """Insert or replace concession features and update metadata."""
        if not features:
            return
        conn = self.conn
        cur = conn.cursor()
        now_utc = datetime.now(timezone.utc).isoformat()
        for feat in features:
            props = feat.get("properties", {})
            coords = feat.get("geometry", {}).get("coordinates", [0, 0])
            con_id = f"{props.get('name', '')}_{coords[0]}_{coords[1]}"
            cur.execute(
                """INSERT OR REPLACE INTO concessions
                   (id, name, lat, lon, operator, mineral_type, status,
                    country, properties_json, fetched_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    con_id,
                    props.get("name", ""),
                    coords[1],
                    coords[0],
                    props.get("operator", ""),
                    props.get("mineral_type", ""),
                    props.get("status", ""),
                    props.get("country", ""),
                    json.dumps(props),
                    now_utc,
                ),
            )
        cur.execute(
            """INSERT OR REPLACE INTO fetch_metadata (layer, last_fetched_at, record_count)
               VALUES ('concessions', ?, ?)""",
            (now_utc, len(features)),
        )
        conn.commit()

    # -- reads ----------------------------------------------------------------

    def get_deposits(
        self, commodity: Optional[str] = None, country: Optional[str] = None,
    ) -> dict:
        """Return deposits as GeoJSON FeatureCollection, optionally filtered."""
        query = "SELECT * FROM deposits WHERE 1=1"
        params: list = []
        if commodity:
            query += " AND commodity = ?"
            params.append(commodity)
        if country:
            query += " AND country = ?"
            params.append(country)

        cur = self.conn.cursor()
        cur.execute(query, params)
        rows = cur.fetchall()

        features = []
        for row in rows:
            props = json.loads(row["properties_json"])
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [row["lon"], row["lat"]]},
                "properties": props,
            })
        return {"type": "FeatureCollection", "features": features}

    def get_concessions(
        self, country: Optional[str] = None,
    ) -> dict:
        """Return concessions as GeoJSON FeatureCollection, optionally filtered."""
        query = "SELECT * FROM concessions WHERE 1=1"
        params: list = []
        if country:
            query += " AND country = ?"
            params.append(country)

        cur = self.conn.cursor()
        cur.execute(query, params)
        rows = cur.fetchall()

        features = []
        for row in rows:
            props = json.loads(row["properties_json"])
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [row["lon"], row["lat"]]},
                "properties": props,
            })
        return {"type": "FeatureCollection", "features": features}

    def get_staleness(self, layer: str) -> Optional[float]:
        """Return hours since last fetch for a layer, or None if never fetched."""
        cur = self.conn.cursor()
        cur.execute(
            "SELECT last_fetched_at FROM fetch_metadata WHERE layer = ?", (layer,)
        )
        row = cur.fetchone()
        if not row:
            return None
        last = datetime.fromisoformat(row["last_fetched_at"])
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - last
        return delta.total_seconds() / 3600.0
