"""SQLite cache for regulatory data."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


class RegulatoryDataStore:
    """Local SQLite store for regulatory records with staleness tracking."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = Path(db_path or (Path.home() / ".zorora" / "regulatory_data.db"))
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
            CREATE TABLE IF NOT EXISTS regulatory_events (
                id TEXT PRIMARY KEY,
                jurisdiction TEXT NOT NULL,
                regulator TEXT NOT NULL,
                event_type TEXT NOT NULL,
                title TEXT NOT NULL,
                summary TEXT,
                effective_date TEXT,
                deadline_date TEXT,
                published_date TEXT NOT NULL,
                source_url TEXT,
                properties_json TEXT,
                fetched_at TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS rps_targets (
                id TEXT PRIMARY KEY,
                state TEXT NOT NULL,
                standard_type TEXT NOT NULL,
                tier TEXT,
                year INTEGER NOT NULL,
                target_pct REAL,
                demand_gwh REAL,
                applicable_sales_gwh REAL,
                statewide_sales_gwh REAL,
                achievement_ratio REAL,
                compliance_cost_per_kwh REAL,
                capacity_additions_mw REAL,
                notes TEXT,
                properties_json TEXT,
                fetched_at TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS eia_series (
                id TEXT PRIMARY KEY,
                endpoint TEXT NOT NULL,
                state TEXT,
                fuel_type TEXT,
                period TEXT NOT NULL,
                value REAL,
                unit TEXT,
                properties_json TEXT,
                fetched_at TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS utility_rates (
                id TEXT PRIMARY KEY,
                utility_name TEXT,
                state TEXT,
                sector TEXT,
                rate_kwh REAL,
                lat REAL,
                lon REAL,
                properties_json TEXT,
                fetched_at TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS fetch_metadata (
                source TEXT PRIMARY KEY,
                last_fetched_at TEXT,
                record_count INTEGER DEFAULT 0
            )
            """
        )
        self.conn.commit()

    def _update_metadata(self, source: str, count: int):
        now_utc = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            """
            INSERT OR REPLACE INTO fetch_metadata (source, last_fetched_at, record_count)
            VALUES (?, ?, ?)
            """,
            (source, now_utc, count),
        )
        self.conn.commit()

    def _make_id(self, *parts) -> str:
        raw = "|".join("" if part is None else str(part) for part in parts)
        return hashlib.md5(raw.encode("utf-8")).hexdigest()

    def upsert_rps_targets(self, records: list[dict]):
        if not records:
            return
        now_utc = datetime.now(timezone.utc).isoformat()
        cur = self.conn.cursor()
        for record in records:
            rec_id = self._make_id(
                record.get("state"),
                record.get("standard_type"),
                record.get("tier"),
                record.get("year"),
            )
            cur.execute(
                """
                INSERT OR REPLACE INTO rps_targets
                (id, state, standard_type, tier, year, target_pct, demand_gwh, applicable_sales_gwh,
                 statewide_sales_gwh, achievement_ratio, compliance_cost_per_kwh, capacity_additions_mw,
                 notes, properties_json, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rec_id,
                    record.get("state"),
                    record.get("standard_type"),
                    record.get("tier"),
                    record.get("year"),
                    record.get("target_pct"),
                    record.get("demand_gwh"),
                    record.get("applicable_sales_gwh"),
                    record.get("statewide_sales_gwh"),
                    record.get("achievement_ratio"),
                    record.get("compliance_cost_per_kwh"),
                    record.get("capacity_additions_mw"),
                    record.get("notes"),
                    json.dumps(record.get("properties", {})),
                    now_utc,
                ),
            )
        self.conn.commit()
        self._update_metadata("rps_targets", len(records))

    def upsert_eia_series(self, records: list[dict], endpoint: str):
        if not records:
            return
        now_utc = datetime.now(timezone.utc).isoformat()
        cur = self.conn.cursor()
        for record in records:
            rec_id = self._make_id(
                endpoint,
                record.get("period"),
                record.get("state"),
                record.get("fuel_type"),
                json.dumps(record.get("properties", {}), sort_keys=True),
            )
            cur.execute(
                """
                INSERT OR REPLACE INTO eia_series
                (id, endpoint, state, fuel_type, period, value, unit, properties_json, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rec_id,
                    endpoint,
                    record.get("state"),
                    record.get("fuel_type"),
                    record.get("period"),
                    record.get("value"),
                    record.get("unit"),
                    json.dumps(record.get("properties", {})),
                    now_utc,
                ),
            )
        self.conn.commit()
        self._update_metadata(endpoint, len(records))

    def upsert_utility_rates(self, records: list[dict]):
        if not records:
            return
        now_utc = datetime.now(timezone.utc).isoformat()
        cur = self.conn.cursor()
        for record in records:
            rec_id = self._make_id(
                record.get("utility_name"),
                record.get("sector"),
                record.get("lat"),
                record.get("lon"),
            )
            cur.execute(
                """
                INSERT OR REPLACE INTO utility_rates
                (id, utility_name, state, sector, rate_kwh, lat, lon, properties_json, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rec_id,
                    record.get("utility_name"),
                    record.get("state"),
                    record.get("sector"),
                    record.get("rate_kwh"),
                    record.get("lat"),
                    record.get("lon"),
                    json.dumps(record.get("properties", {})),
                    now_utc,
                ),
            )
        self.conn.commit()
        self._update_metadata("utility_rates", len(records))

    def upsert_regulatory_events(self, events: list[dict]):
        if not events:
            return
        now_utc = datetime.now(timezone.utc).isoformat()
        cur = self.conn.cursor()
        for event in events:
            rec_id = self._make_id(
                event.get("jurisdiction"),
                event.get("regulator"),
                event.get("event_type"),
                event.get("title"),
                event.get("published_date"),
            )
            cur.execute(
                """
                INSERT OR REPLACE INTO regulatory_events
                (id, jurisdiction, regulator, event_type, title, summary, effective_date, deadline_date,
                 published_date, source_url, properties_json, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rec_id,
                    event.get("jurisdiction"),
                    event.get("regulator"),
                    event.get("event_type"),
                    event.get("title"),
                    event.get("summary"),
                    event.get("effective_date"),
                    event.get("deadline_date"),
                    event.get("published_date"),
                    event.get("source_url"),
                    json.dumps(event.get("properties", {})),
                    now_utc,
                ),
            )
        self.conn.commit()
        self._update_metadata("regulatory_events", len(events))

    def get_rps_targets(
        self,
        state: Optional[str] = None,
        year: Optional[int] = None,
        standard_type: Optional[str] = None,
    ) -> list[dict]:
        query = "SELECT * FROM rps_targets WHERE 1=1"
        params: list = []
        if state:
            query += " AND state = ?"
            params.append(state)
        if year is not None:
            query += " AND year = ?"
            params.append(int(year))
        if standard_type:
            query += " AND standard_type = ?"
            params.append(standard_type)
        query += " ORDER BY state, year, tier"
        rows = self.conn.execute(query, params).fetchall()
        return [dict(row) | {"properties": json.loads(row["properties_json"] or "{}")} for row in rows]

    def get_eia_series(self, endpoint: str, state: Optional[str] = None, fuel_type: Optional[str] = None) -> list[dict]:
        query = "SELECT * FROM eia_series WHERE endpoint = ?"
        params: list = [endpoint]
        if state:
            query += " AND state = ?"
            params.append(state)
        if fuel_type:
            query += " AND fuel_type = ?"
            params.append(fuel_type)
        query += " ORDER BY period DESC"
        rows = self.conn.execute(query, params).fetchall()
        return [dict(row) | {"properties": json.loads(row["properties_json"] or "{}")} for row in rows]

    def get_utility_rates(self, state: Optional[str] = None, sector: Optional[str] = None) -> list[dict]:
        query = "SELECT * FROM utility_rates WHERE 1=1"
        params: list = []
        if state:
            query += " AND state = ?"
            params.append(state)
        if sector:
            query += " AND sector = ?"
            params.append(sector)
        query += " ORDER BY utility_name, sector"
        rows = self.conn.execute(query, params).fetchall()
        return [dict(row) | {"properties": json.loads(row["properties_json"] or "{}")} for row in rows]

    def get_regulatory_events(
        self,
        jurisdiction: Optional[str] = None,
        event_type: Optional[str] = None,
    ) -> list[dict]:
        query = "SELECT * FROM regulatory_events WHERE 1=1"
        params: list = []
        if jurisdiction:
            query += " AND jurisdiction = ?"
            params.append(jurisdiction)
        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)
        query += " ORDER BY published_date DESC"
        rows = self.conn.execute(query, params).fetchall()
        return [dict(row) | {"properties": json.loads(row["properties_json"] or "{}")} for row in rows]

    def get_staleness(self, source: str) -> Optional[float]:
        row = self.conn.execute(
            "SELECT last_fetched_at FROM fetch_metadata WHERE source = ?",
            (source,),
        ).fetchone()
        if not row:
            return None
        last = datetime.fromisoformat(row["last_fetched_at"])
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - last).total_seconds() / 3600.0

    def get_last_fetched_at(self, source: str) -> Optional[datetime]:
        row = self.conn.execute(
            "SELECT last_fetched_at FROM fetch_metadata WHERE source = ?",
            (source,),
        ).fetchone()
        if not row or not row["last_fetched_at"]:
            return None
        value = datetime.fromisoformat(row["last_fetched_at"])
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value
