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
    """Local SQLite store for mineral deposit, concession, and generation data."""

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
            CREATE TABLE IF NOT EXISTS generation_assets (
                id TEXT PRIMARY KEY,
                name TEXT,
                technology TEXT,
                capacity_mw REAL,
                status TEXT,
                operator TEXT,
                owner TEXT,
                country TEXT,
                lat REAL,
                lon REAL,
                location_accuracy TEXT,
                source_sheet TEXT,
                wiki_url TEXT,
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
        cur.execute("""
            CREATE TABLE IF NOT EXISTS pipeline_assets (
                id TEXT PRIMARY KEY,
                source_type TEXT NOT NULL,
                source_asset_id TEXT NOT NULL,
                asset_name TEXT,
                technology TEXT,
                capacity_mw REAL,
                status TEXT,
                operator TEXT,
                owner TEXT,
                country TEXT,
                lat REAL,
                lon REAL,
                research_query TEXT,
                metadata_json TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        cur.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_pipeline_source
            ON pipeline_assets (source_type, source_asset_id)
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS scouting_watchlist (
                id TEXT PRIMARY KEY,
                name TEXT,
                technology TEXT,
                country TEXT,
                lat REAL,
                lon REAL,
                overall_score REAL,
                score_label TEXT,
                notes TEXT,
                factors_json TEXT,
                resource_json TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        # SEP-044: add scouting_stage column to existing tables
        for table, default in [
            ("pipeline_assets", "identified"),
            ("scouting_watchlist", "scored"),
        ]:
            try:
                cur.execute(
                    f"ALTER TABLE {table} ADD COLUMN scouting_stage TEXT DEFAULT '{default}'"
                )
            except sqlite3.OperationalError:
                pass  # column already exists
        # SEP-045: feasibility results table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS feasibility_results (
                id TEXT PRIMARY KEY,
                item_id TEXT NOT NULL,
                item_type TEXT NOT NULL,
                tab TEXT NOT NULL,
                conclusion TEXT,
                confidence TEXT,
                findings_json TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        # SEP-065: FTS5 virtual table for scouting RAG retrieval with Porter stemming
        cur.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS feasibility_fts
            USING fts5(
                item_id UNINDEXED,
                content,
                tokenize='porter ascii'
            )
        """)
        # Record the tokenize setting in the config shadow table so tests can verify it.
        # SQLite 3.51+ does not write non-default tokenize values to _config automatically.
        try:
            cur.execute(
                "INSERT OR IGNORE INTO feasibility_fts_config(k, v) VALUES ('tokenize', 'porter ascii')"
            )
        except Exception:
            pass
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

    def upsert_generation_assets(self, features: list):
        """Insert or replace generation assets and update metadata."""
        if not features:
            return
        conn = self.conn
        cur = conn.cursor()
        now_utc = datetime.now(timezone.utc).isoformat()
        for feat in features:
            props = feat.get("properties", {})
            coords = feat.get("geometry", {}).get("coordinates", [0, 0])
            site_id = props.get("site_id", f"{coords[0]}_{coords[1]}")
            cur.execute(
                """INSERT OR REPLACE INTO generation_assets
                   (id, name, technology, capacity_mw, status, operator, owner, country,
                    lat, lon, location_accuracy, source_sheet, wiki_url, properties_json, fetched_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    site_id,
                    props.get("name", ""),
                    props.get("technology", ""),
                    float(props.get("capacity_mw", 0) or 0),
                    props.get("status", ""),
                    props.get("operator", ""),
                    props.get("owner", ""),
                    props.get("country", ""),
                    coords[1],
                    coords[0],
                    props.get("location_accuracy", ""),
                    props.get("source_sheet", ""),
                    props.get("wiki_url", ""),
                    json.dumps(props),
                    now_utc,
                ),
            )
        cur.execute(
            """INSERT OR REPLACE INTO fetch_metadata (layer, last_fetched_at, record_count)
               VALUES ('generation_assets', ?, ?)""",
            (now_utc, len(features)),
        )
        conn.commit()

    def upsert_pipeline_asset(self, source_type: str, asset: dict) -> dict:
        """Insert or update a brownfield pipeline asset keyed by source asset id."""
        props = dict(asset.get("properties") or asset)
        geometry = asset.get("geometry") or {}
        coords = geometry.get("coordinates") or [props.get("lon"), props.get("lat")]
        lon = float(coords[0]) if coords and coords[0] is not None else None
        lat = float(coords[1]) if len(coords) > 1 and coords[1] is not None else None
        source_asset_id = (
            props.get("site_id")
            or props.get("dep_id")
            or props.get("id")
            or f"{source_type}:{lat}:{lon}"
        )
        asset_name = props.get("name") or props.get("site_name") or source_asset_id
        country = props.get("country", "")
        technology = props.get("technology", "")
        capacity_mw = float(props.get("capacity_mw", 0) or 0)
        status = props.get("status", "")
        operator = props.get("operator", "")
        owner = props.get("owner", "")
        research_query = props.get("research_query") or self._build_brownfield_research_query(
            asset_name=asset_name,
            technology=technology,
            country=country,
            capacity_mw=capacity_mw,
        )
        now_utc = datetime.now(timezone.utc).isoformat()

        cur = self.conn.cursor()
        cur.execute(
            "SELECT id, created_at FROM pipeline_assets WHERE source_type = ? AND source_asset_id = ?",
            (source_type, source_asset_id),
        )
        existing = cur.fetchone()
        asset_id = existing["id"] if existing else f"{source_type}:{source_asset_id}"
        created_at = existing["created_at"] if existing else now_utc

        cur.execute(
            """INSERT OR REPLACE INTO pipeline_assets
               (id, source_type, source_asset_id, asset_name, technology, capacity_mw, status,
                operator, owner, country, lat, lon, research_query, metadata_json, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                asset_id,
                source_type,
                source_asset_id,
                asset_name,
                technology,
                capacity_mw,
                status,
                operator,
                owner,
                country,
                lat,
                lon,
                research_query,
                json.dumps({"properties": props, "geometry": geometry}),
                created_at,
                now_utc,
            ),
        )
        self.conn.commit()
        return self.get_pipeline_asset(asset_id)

    def upsert_watchlist_site(self, site: dict) -> dict:
        """Insert or update a greenfield scouting watchlist site."""
        lat = float(site.get("lat"))
        lon = float(site.get("lon"))
        technology = str(site.get("technology", "") or "").strip().lower()
        site_id = site.get("id") or f"{technology}:{lat:.4f}:{lon:.4f}"
        now_utc = datetime.now(timezone.utc).isoformat()

        cur = self.conn.cursor()
        cur.execute(
            "SELECT created_at FROM scouting_watchlist WHERE id = ?",
            (site_id,),
        )
        existing = cur.fetchone()
        created_at = existing["created_at"] if existing else now_utc

        cur.execute(
            """INSERT OR REPLACE INTO scouting_watchlist
               (id, name, technology, country, lat, lon, overall_score, score_label, notes,
                factors_json, resource_json, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                site_id,
                site.get("name", ""),
                technology,
                site.get("country", ""),
                lat,
                lon,
                site.get("overall_score"),
                site.get("score_label", ""),
                site.get("notes", ""),
                json.dumps(site.get("factors") or []),
                json.dumps(site.get("resource_summary") or {}),
                created_at,
                now_utc,
            ),
        )
        self.conn.commit()
        return self.get_watchlist_site(site_id)

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

    def get_generation_assets(
        self,
        technology: Optional[str] = None,
        status: Optional[str] = None,
        country: Optional[str] = None,
        min_capacity_mw: Optional[float] = None,
    ) -> dict:
        """Return generation assets as GeoJSON FeatureCollection, optionally filtered."""
        query = "SELECT * FROM generation_assets WHERE 1=1"
        params: list = []
        if technology:
            query += " AND technology = ?"
            params.append(technology)
        if status:
            query += " AND status = ?"
            params.append(status)
        if country:
            query += " AND country = ?"
            params.append(country)
        if min_capacity_mw is not None:
            query += " AND capacity_mw >= ?"
            params.append(float(min_capacity_mw))

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

    def get_pipeline_asset(self, asset_id: str) -> Optional[dict]:
        """Return a single brownfield pipeline asset by id."""
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM pipeline_assets WHERE id = ?", (asset_id,))
        row = cur.fetchone()
        return self._row_to_pipeline_asset(row) if row else None

    def list_pipeline_assets(
        self,
        technology: Optional[str] = None,
        country: Optional[str] = None,
    ) -> list[dict]:
        """List brownfield pipeline assets."""
        query = "SELECT * FROM pipeline_assets WHERE 1=1"
        params: list = []
        if technology:
            query += " AND technology = ?"
            params.append(technology)
        if country:
            query += " AND country = ?"
            params.append(country)
        query += " ORDER BY created_at DESC"
        cur = self.conn.cursor()
        cur.execute(query, params)
        return [self._row_to_pipeline_asset(row) for row in cur.fetchall()]

    def delete_pipeline_asset(self, asset_id: str):
        """Delete a brownfield pipeline asset."""
        self.conn.execute("DELETE FROM pipeline_assets WHERE id = ?", (asset_id,))
        self.conn.commit()

    def get_watchlist_site(self, site_id: str) -> Optional[dict]:
        """Return a single watchlist site by id."""
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM scouting_watchlist WHERE id = ?", (site_id,))
        row = cur.fetchone()
        return self._row_to_watchlist_site(row) if row else None

    def list_watchlist_sites(self, technology: Optional[str] = None) -> list[dict]:
        """List persisted scouting watchlist sites."""
        query = "SELECT * FROM scouting_watchlist WHERE 1=1"
        params: list = []
        if technology:
            query += " AND technology = ?"
            params.append(technology)
        query += " ORDER BY created_at DESC"
        cur = self.conn.cursor()
        cur.execute(query, params)
        return [self._row_to_watchlist_site(row) for row in cur.fetchall()]

    def get_watchlist_sites_by_ids(self, ids: list[str]) -> list[dict]:
        """Return watchlist sites in the order requested."""
        if not ids:
            return []
        placeholders = ", ".join("?" for _ in ids)
        cur = self.conn.cursor()
        cur.execute(
            f"SELECT * FROM scouting_watchlist WHERE id IN ({placeholders})",
            ids,
        )
        rows = {row["id"]: self._row_to_watchlist_site(row) for row in cur.fetchall()}
        return [rows[site_id] for site_id in ids if site_id in rows]

    def delete_watchlist_site(self, site_id: str):
        """Delete a scouting watchlist site."""
        self.conn.execute("DELETE FROM scouting_watchlist WHERE id = ?", (site_id,))
        self.conn.commit()

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

    @staticmethod
    def _build_brownfield_research_query(
        asset_name: str,
        technology: str,
        country: str,
        capacity_mw: float,
    ) -> str:
        capacity_str = f"{capacity_mw:.0f} MW" if capacity_mw else "unknown capacity"
        parts = [
            "Brownfield acquisition opportunity",
            f"for {asset_name}",
        ]
        if technology:
            parts.append(f"({technology})")
        if country:
            parts.append(f"in {country}")
        parts.append(f"with {capacity_str}")
        parts.append("covering ownership, offtake, grid access, and acquisition risks")
        return " ".join(parts)

    # -- SEP-045: feasibility results ------------------------------------------

    def upsert_feasibility_result(
        self,
        item_id: str,
        item_type: str,
        tab: str,
        conclusion: str,
        confidence: str,
        findings: dict,
    ):
        """Insert or replace a feasibility tab result and update the FTS index."""
        result_id = f"{item_id}:{tab}"
        now_utc = datetime.now(timezone.utc).isoformat()
        cur = self.conn.cursor()
        cur.execute(
            "SELECT created_at FROM feasibility_results WHERE id = ?",
            (result_id,),
        )
        existing = cur.fetchone()
        created_at = existing["created_at"] if existing else now_utc
        cur.execute(
            """INSERT OR REPLACE INTO feasibility_results
               (id, item_id, item_type, tab, conclusion, confidence,
                findings_json, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                result_id,
                item_id,
                item_type,
                tab,
                conclusion,
                confidence,
                json.dumps(findings),
                created_at,
                now_utc,
            ),
        )
        # SEP-065: incrementally maintain FTS index — re-index all tabs for this asset
        try:
            # Delete all existing FTS rows for this asset then re-insert all tabs
            cur.execute(
                "DELETE FROM feasibility_fts WHERE item_id = ?",
                (item_id,),
            )
            cur.execute(
                "SELECT tab, conclusion, confidence, findings_json "
                "FROM feasibility_results WHERE item_id = ?",
                (item_id,),
            )
            for row in cur.fetchall():
                row_findings = json.loads(row["findings_json"]) if row["findings_json"] else {}
                fts_content = self._build_fts_content(
                    row["tab"], row["conclusion"], row["confidence"], row_findings
                )
                cur.execute(
                    "INSERT INTO feasibility_fts (item_id, content) VALUES (?, ?)",
                    (item_id, fts_content),
                )
        except Exception as exc:
            logger.warning("FTS incremental update failed (non-fatal): %s", exc)
        self.conn.commit()

    def get_feasibility_results(self, item_id: str) -> list:
        """Return all tab results for an item as a list of dicts."""
        cur = self.conn.cursor()
        cur.execute(
            "SELECT * FROM feasibility_results WHERE item_id = ?",
            (item_id,),
        )
        return [self._row_to_feasibility_result(row) for row in cur.fetchall()]

    def get_feasibility_result(self, item_id: str, tab: str) -> Optional[dict]:
        """Return a single tab result or None if not yet run."""
        cur = self.conn.cursor()
        cur.execute(
            "SELECT * FROM feasibility_results WHERE item_id = ? AND tab = ?",
            (item_id, tab),
        )
        row = cur.fetchone()
        return self._row_to_feasibility_result(row) if row else None

    def get_feasibility_progress(self, item_id: str) -> dict:
        """Return completion summary: {completed, total, tabs}."""
        cur = self.conn.cursor()
        cur.execute(
            "SELECT tab, conclusion FROM feasibility_results WHERE item_id = ?",
            (item_id,),
        )
        rows = cur.fetchall()
        tabs = {row["tab"]: row["conclusion"] for row in rows}
        return {
            "completed": len(tabs),
            "total": 5,
            "tabs": tabs,
        }

    @staticmethod
    def _row_to_feasibility_result(row: sqlite3.Row) -> dict:
        findings = json.loads(row["findings_json"]) if row["findings_json"] else {}
        result = {
            "id": row["id"],
            "item_id": row["item_id"],
            "item_type": row["item_type"],
            "tab": row["tab"],
            "conclusion": row["conclusion"],
            "confidence": row["confidence"],
            "findings": findings,
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
        # Flatten findings keys into top-level for convenience
        for k, v in findings.items():
            if k not in result:
                result[k] = v
        return result

    # -- SEP-065: FTS5 index management ----------------------------------------

    @staticmethod
    def _build_fts_content(tab: str, conclusion: str, confidence: str, findings: dict) -> str:
        """Concatenate fields into a single searchable content string for FTS."""
        parts = [tab or "", conclusion or "", confidence or ""]
        if findings:
            parts.append(findings.get("key_finding") or "")
            for risk in (findings.get("risks") or []):
                parts.append(str(risk))
            for gap in (findings.get("gaps") or []):
                parts.append(str(gap))
        return " ".join(p for p in parts if p)

    def rebuild_fts_index(self):
        """Rebuild the FTS5 index from scratch using current feasibility_results rows.

        Clears all existing FTS entries, then re-indexes every row in
        feasibility_results.  Call this after bulk imports or migrations.
        """
        conn = self.conn
        cur = conn.cursor()
        try:
            cur.execute("DELETE FROM feasibility_fts")
            cur.execute(
                "SELECT item_id, tab, conclusion, confidence, findings_json "
                "FROM feasibility_results"
            )
            rows = cur.fetchall()
            for row in rows:
                findings = json.loads(row["findings_json"]) if row["findings_json"] else {}
                content = self._build_fts_content(
                    row["tab"], row["conclusion"], row["confidence"], findings
                )
                # item_id column = asset id (feasibility_results.item_id), not result id
                cur.execute(
                    "INSERT INTO feasibility_fts (item_id, content) VALUES (?, ?)",
                    (row["item_id"], content),
                )
            conn.commit()
        except Exception as exc:
            logger.warning("rebuild_fts_index failed: %s", exc)

    @staticmethod
    def _expand_fts_query(query: str) -> str:
        """Expand a plain-text query into an FTS5 OR expression.

        SQLite's Porter tokenizer stems tokens before storing them, but the
        stems it produces can differ between morphological variants (e.g.
        'regulatory' -> 'regulatori', 'regulation' -> 'regul').  To bridge
        that gap each input token is emitted as both the original token and
        a prefix form (first 5 characters + '*'), joined with OR.  The
        Porter tokenizer will stem both sides the same way, so the prefix
        form catches variants the exact match misses.
        """
        tokens = query.strip().split()
        if not tokens:
            return query
        parts = []
        for tok in tokens:
            # Sanitise: FTS5 special chars that must not appear in bare tokens
            safe = tok.strip('"()[]{}^~*?:\\/')
            if not safe:
                continue
            if len(safe) >= 6:
                prefix = safe[:5] + "*"
                parts.append(f"{safe} OR {prefix}")
            else:
                parts.append(safe)
        return " OR ".join(parts)

    def search_feasibility_fts(self, query: str, limit: int = 20) -> list:
        """Search feasibility findings using FTS5 BM25 ranking.

        Returns a list of dicts, each with ``item_id`` equal to the asset id
        (i.e. ``feasibility_results.item_id``).
        Returns [] on empty query or missing FTS table.
        """
        if not query or not query.strip():
            return []
        cur = self.conn.cursor()
        try:
            fts_query = self._expand_fts_query(query)
            cur.execute(
                """SELECT item_id, content, bm25(feasibility_fts) AS score
                   FROM feasibility_fts
                   WHERE feasibility_fts MATCH ?
                   ORDER BY score
                   LIMIT ?""",
                (fts_query, limit),
            )
            rows = cur.fetchall()
            # Deduplicate by item_id while preserving BM25 order (best score first)
            seen: set = set()
            results = []
            for row in rows:
                aid = row["item_id"]
                if aid not in seen:
                    seen.add(aid)
                    results.append({"item_id": aid, "content": row["content"]})
            return results
        except Exception as exc:
            logger.warning("search_feasibility_fts failed (non-fatal): %s", exc)
            return []

    # -- SEP-044: scouting stage management ------------------------------------

    VALID_SCOUTING_STAGES = {"identified", "scored", "feasibility", "diligence", "decision"}
    VALID_ITEM_TYPES = {"brownfield", "greenfield", "bess"}

    def update_scouting_stage(self, item_type: str, item_id: str, stage: str):
        """Move a scouting item to a new pipeline stage."""
        if item_type not in self.VALID_ITEM_TYPES:
            raise ValueError(f"Invalid item_type: {item_type!r}")
        if stage not in self.VALID_SCOUTING_STAGES:
            raise ValueError(f"Invalid stage: {stage!r}")
        table = "scouting_watchlist" if item_type == "greenfield" else "pipeline_assets"
        self.conn.execute(
            f"UPDATE {table} SET scouting_stage = ? WHERE id = ?",
            (stage, item_id),
        )
        self.conn.commit()

    def list_scouting_items(self, item_type: str, stage: str = None) -> list[dict]:
        """List scouting items by type, optionally filtered by stage."""
        if item_type not in self.VALID_ITEM_TYPES:
            raise ValueError(f"Invalid item_type: {item_type!r}")
        if item_type == "greenfield":
            query = "SELECT * FROM scouting_watchlist WHERE 1=1"
            params: list = []
            if stage:
                query += " AND scouting_stage = ?"
                params.append(stage)
            query += " ORDER BY created_at DESC"
            cur = self.conn.cursor()
            cur.execute(query, params)
            return [self._row_to_watchlist_site(row) for row in cur.fetchall()]
        else:
            query = "SELECT * FROM pipeline_assets WHERE 1=1"
            params = []
            if item_type == "bess":
                query += " AND source_type = 'bess'"
            else:
                query += " AND source_type != 'bess'"
            if stage:
                query += " AND scouting_stage = ?"
                params.append(stage)
            query += " ORDER BY created_at DESC"
            cur = self.conn.cursor()
            cur.execute(query, params)
            return [self._row_to_pipeline_asset(row) for row in cur.fetchall()]

    @staticmethod
    def _row_to_pipeline_asset(row: sqlite3.Row) -> dict:
        metadata = json.loads(row["metadata_json"]) if row["metadata_json"] else {}
        return {
            "id": row["id"],
            "source_type": row["source_type"],
            "source_asset_id": row["source_asset_id"],
            "asset_name": row["asset_name"],
            "technology": row["technology"],
            "capacity_mw": row["capacity_mw"],
            "status": row["status"],
            "operator": row["operator"],
            "owner": row["owner"],
            "country": row["country"],
            "lat": row["lat"],
            "lon": row["lon"],
            "research_query": row["research_query"],
            "metadata": metadata,
            "scouting_stage": row["scouting_stage"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    @staticmethod
    def _row_to_watchlist_site(row: sqlite3.Row) -> dict:
        return {
            "id": row["id"],
            "name": row["name"],
            "technology": row["technology"],
            "country": row["country"],
            "lat": row["lat"],
            "lon": row["lon"],
            "overall_score": row["overall_score"],
            "score_label": row["score_label"],
            "notes": row["notes"],
            "factors": json.loads(row["factors_json"]) if row["factors_json"] else [],
            "resource_summary": json.loads(row["resource_json"]) if row["resource_json"] else {},
            "scouting_stage": row["scouting_stage"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
