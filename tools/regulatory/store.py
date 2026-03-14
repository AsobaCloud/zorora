"""SQLite cache for regulatory data and normalization provenance."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


class RegulatoryDataStore:
    """Local SQLite store for regulatory records with staleness tracking."""

    _EVENT_COLUMN_DEFINITIONS = {
        "source_system": "TEXT",
        "source_record_id": "TEXT",
        "schema_version": "TEXT",
        "transform_version": "TEXT",
        "transform_run_id": "TEXT",
        "raw_document_id": "TEXT",
    }

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
                source_system TEXT,
                source_record_id TEXT,
                schema_version TEXT,
                transform_version TEXT,
                transform_run_id TEXT,
                raw_document_id TEXT,
                properties_json TEXT,
                fetched_at TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS regulatory_raw_documents (
                id TEXT PRIMARY KEY,
                jurisdiction TEXT,
                source_system TEXT NOT NULL,
                source_url TEXT,
                content_type TEXT,
                fetch_status TEXT NOT NULL,
                http_status INTEGER,
                document_hash TEXT,
                payload_text TEXT,
                metadata_json TEXT,
                fetched_at TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS regulatory_transform_runs (
                id TEXT PRIMARY KEY,
                jurisdiction TEXT,
                source_system TEXT NOT NULL,
                raw_document_id TEXT,
                transform_name TEXT NOT NULL,
                schema_version TEXT NOT NULL,
                transform_version TEXT NOT NULL,
                mapping_json TEXT,
                notes TEXT,
                record_count INTEGER DEFAULT 0,
                ran_at TEXT NOT NULL
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
        self._ensure_columns("regulatory_events", self._EVENT_COLUMN_DEFINITIONS)
        self.conn.commit()

    def _ensure_columns(self, table_name: str, definitions: dict[str, str]):
        columns = {
            row["name"]
            for row in self.conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        for column_name, column_type in definitions.items():
            if column_name not in columns:
                self.conn.execute(
                    f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
                )

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

    def _decode_json(self, raw_value: Optional[str]) -> dict:
        if not raw_value:
            return {}
        try:
            value = json.loads(raw_value)
        except (TypeError, ValueError):
            return {}
        return value if isinstance(value, dict) else {}

    def _coerce_time(self, value: Optional[str], default_value: str) -> str:
        return value or default_value

    def _source_counts(self, rows: list[dict], key: str) -> Counter:
        counts: Counter = Counter()
        for row in rows:
            source = row.get(key)
            if source:
                counts[str(source)] += 1
        return counts

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
                    json.dumps(record.get("properties", {}), sort_keys=True),
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
                    json.dumps(record.get("properties", {}), sort_keys=True),
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
                    json.dumps(record.get("properties", {}), sort_keys=True),
                    now_utc,
                ),
            )
        self.conn.commit()
        self._update_metadata("utility_rates", len(records))

    def upsert_raw_documents(self, documents: list[dict]):
        if not documents:
            return
        now_utc = datetime.now(timezone.utc).isoformat()
        cur = self.conn.cursor()
        for document in documents:
            cur.execute(
                """
                INSERT OR REPLACE INTO regulatory_raw_documents
                (id, jurisdiction, source_system, source_url, content_type, fetch_status, http_status,
                 document_hash, payload_text, metadata_json, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    document.get("id") or self._make_id(
                        document.get("source_system"),
                        document.get("source_url"),
                        document.get("document_hash"),
                    ),
                    document.get("jurisdiction"),
                    document.get("source_system"),
                    document.get("source_url"),
                    document.get("content_type"),
                    document.get("fetch_status") or "ok",
                    document.get("http_status"),
                    document.get("document_hash"),
                    document.get("payload_text"),
                    json.dumps(document.get("metadata", {}), sort_keys=True),
                    self._coerce_time(document.get("fetched_at"), now_utc),
                ),
            )
        self.conn.commit()
        for source_system, count in self._source_counts(documents, "source_system").items():
            self._update_metadata(source_system, count)

    def upsert_transform_runs(self, runs: list[dict]):
        if not runs:
            return
        now_utc = datetime.now(timezone.utc).isoformat()
        cur = self.conn.cursor()
        for run in runs:
            cur.execute(
                """
                INSERT OR REPLACE INTO regulatory_transform_runs
                (id, jurisdiction, source_system, raw_document_id, transform_name, schema_version,
                 transform_version, mapping_json, notes, record_count, ran_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run.get("id") or self._make_id(
                        run.get("source_system"),
                        run.get("raw_document_id"),
                        run.get("transform_name"),
                        run.get("transform_version"),
                    ),
                    run.get("jurisdiction"),
                    run.get("source_system"),
                    run.get("raw_document_id"),
                    run.get("transform_name"),
                    run.get("schema_version"),
                    run.get("transform_version"),
                    json.dumps(run.get("mapping", {}), sort_keys=True),
                    run.get("notes"),
                    int(run.get("record_count", 0) or 0),
                    self._coerce_time(run.get("ran_at"), now_utc),
                ),
            )
        self.conn.commit()

    def upsert_regulatory_events(self, events: list[dict]):
        if not events:
            return
        now_utc = datetime.now(timezone.utc).isoformat()
        cur = self.conn.cursor()
        for event in events:
            rec_id = event.get("id") or self._make_id(
                event.get("source_system"),
                event.get("source_record_id"),
                event.get("jurisdiction"),
                event.get("title"),
                event.get("published_date"),
            )
            cur.execute(
                """
                INSERT OR REPLACE INTO regulatory_events
                (id, jurisdiction, regulator, event_type, title, summary, effective_date, deadline_date,
                 published_date, source_url, source_system, source_record_id, schema_version,
                 transform_version, transform_run_id, raw_document_id, properties_json, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    event.get("source_system"),
                    event.get("source_record_id"),
                    event.get("schema_version"),
                    event.get("transform_version"),
                    event.get("transform_run_id"),
                    event.get("raw_document_id"),
                    json.dumps(event.get("properties", {}), sort_keys=True),
                    self._coerce_time(event.get("fetched_at"), now_utc),
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
        return [dict(row) | {"properties": self._decode_json(row["properties_json"])} for row in rows]

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
        return [dict(row) | {"properties": self._decode_json(row["properties_json"])} for row in rows]

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
        return [dict(row) | {"properties": self._decode_json(row["properties_json"])} for row in rows]

    def get_raw_documents(
        self,
        source_system: Optional[str] = None,
        jurisdiction: Optional[str] = None,
        fetch_status: Optional[str] = None,
    ) -> list[dict]:
        query = "SELECT * FROM regulatory_raw_documents WHERE 1=1"
        params: list = []
        if source_system:
            query += " AND source_system = ?"
            params.append(source_system)
        if jurisdiction:
            query += " AND jurisdiction = ?"
            params.append(jurisdiction)
        if fetch_status:
            query += " AND fetch_status = ?"
            params.append(fetch_status)
        query += " ORDER BY fetched_at DESC, source_url"
        rows = self.conn.execute(query, params).fetchall()
        return [dict(row) | {"metadata": self._decode_json(row["metadata_json"])} for row in rows]

    def get_transform_runs(
        self,
        source_system: Optional[str] = None,
        jurisdiction: Optional[str] = None,
        transform_name: Optional[str] = None,
    ) -> list[dict]:
        query = "SELECT * FROM regulatory_transform_runs WHERE 1=1"
        params: list = []
        if source_system:
            query += " AND source_system = ?"
            params.append(source_system)
        if jurisdiction:
            query += " AND jurisdiction = ?"
            params.append(jurisdiction)
        if transform_name:
            query += " AND transform_name = ?"
            params.append(transform_name)
        query += " ORDER BY ran_at DESC, transform_name"
        rows = self.conn.execute(query, params).fetchall()
        return [dict(row) | {"mapping": self._decode_json(row["mapping_json"])} for row in rows]

    def get_regulatory_events(
        self,
        jurisdiction: Optional[str] = None,
        event_type: Optional[str] = None,
        source_system: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> list[dict]:
        query = "SELECT * FROM regulatory_events WHERE 1=1"
        params: list = []
        if jurisdiction:
            query += " AND jurisdiction = ?"
            params.append(jurisdiction)
        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)
        if source_system:
            query += " AND source_system = ?"
            params.append(source_system)
        query += " ORDER BY published_date DESC, title"
        if limit is not None:
            query += " LIMIT ?"
            params.append(int(limit))
        rows = self.conn.execute(query, params).fetchall()
        return [dict(row) | {"properties": self._decode_json(row["properties_json"])} for row in rows]

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
