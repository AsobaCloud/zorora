"""Local SQLite + JSON storage layer for deep research."""

import sqlite3
import json
import logging
import threading
from pathlib import Path
from typing import List, Dict, Optional, Any

from engine.models import ResearchState

logger = logging.getLogger(__name__)


class LocalStorage:
    """Local SQLite + JSON storage (mirrors newsroom DynamoDB+S3 pattern)"""

    def __init__(self, db_path=None):
        if db_path is None:
            db_path = Path.home() / '.zorora' / 'zorora.db'

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Thread-local storage for SQLite connections
        # Each thread gets its own connection to avoid threading issues
        self._local = threading.local()
        
        # Initialize schema on first connection
        self._init_schema()

    def _get_connection(self):
        """Get thread-local SQLite connection"""
        if not hasattr(self._local, 'conn'):
            self._local.conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False  # Allow cross-thread usage
            )
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    @property
    def conn(self):
        """Thread-safe connection property"""
        return self._get_connection()

    def _init_schema(self):
        """Initialize database schema"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Research findings index
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS research_findings (
                research_id TEXT PRIMARY KEY,
                query TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL,
                completed_at TIMESTAMP,
                synthesis TEXT,              -- Preview (first 500 chars)
                file_path TEXT NOT NULL,     -- Path to full JSON
                total_sources INTEGER,
                max_depth INTEGER
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_query ON research_findings(query)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON research_findings(created_at DESC)")

        # Sources index
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sources (
                source_id TEXT PRIMARY KEY,
                research_id TEXT NOT NULL,
                url TEXT NOT NULL,
                title TEXT,
                credibility_score REAL,
                credibility_category TEXT,
                source_type TEXT,
                FOREIGN KEY (research_id) REFERENCES research_findings(research_id)
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sources_research ON sources(research_id)")

        # Citation graph
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS citations (
                source_id TEXT NOT NULL,
                cites_source_id TEXT NOT NULL,
                research_id TEXT NOT NULL,
                PRIMARY KEY (source_id, cites_source_id)
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cited_by ON citations(cites_source_id)")

        conn.commit()

    def close(self):
        """Close thread-local SQLite connection if open."""
        conn = getattr(self._local, 'conn', None)
        if conn is not None:
            try:
                conn.close()
            finally:
                delattr(self._local, 'conn')

    def __del__(self):
        """Best-effort cleanup for SQLite connection."""
        try:
            self.close()
        except Exception:
            pass

    def save_research(self, state: ResearchState) -> str:
        """Save research to SQLite + JSON file"""
        # Generate IDs and paths
        timestamp = state.started_at.strftime("%Y%m%d_%H%M%S")
        topic_slug = state.original_query[:50].replace(' ', '_').lower().replace('/', '_')
        research_id = f"{topic_slug}_{timestamp}"

        findings_dir = self.db_path.parent / 'research' / 'findings'
        findings_dir.mkdir(parents=True, exist_ok=True)
        file_path = findings_dir / f"{research_id}.json"

        # Save full data to JSON
        with open(file_path, 'w') as f:
            json.dump(state.to_dict(), f, indent=2)

        # Index metadata in SQLite
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO research_findings
            (research_id, query, created_at, completed_at, synthesis, file_path, total_sources, max_depth)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            research_id,
            state.original_query,
            state.started_at,
            state.completed_at,
            state.synthesis[:500] if state.synthesis else None,
            str(file_path),
            state.total_sources,
            state.max_depth
        ))

        # Index sources and citations
        for source in state.sources_checked:
            cursor.execute("""
                INSERT OR IGNORE INTO sources
                (source_id, research_id, url, title, credibility_score, credibility_category, source_type)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (source.source_id, research_id, source.url, source.title,
                  source.credibility_score, source.credibility_category, source.source_type))

        for source_id, cites_list in state.citation_graph.items():
            for cited_id in cites_list:
                cursor.execute("""
                    INSERT OR IGNORE INTO citations (source_id, cites_source_id, research_id)
                    VALUES (?, ?, ?)
                """, (source_id, cited_id, research_id))

        self.conn.commit()
        logger.info(f"Saved research: {research_id} ({state.total_sources} sources)")
        return research_id

    def search_research(self, query: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Fast search using SQLite index"""
        cursor = self.conn.cursor()

        if query:
            cursor.execute("""
                SELECT * FROM research_findings
                WHERE query LIKE ?
                ORDER BY created_at DESC LIMIT ?
            """, (f'%{query}%', limit))
        else:
            cursor.execute("""
                SELECT * FROM research_findings
                ORDER BY created_at DESC LIMIT ?
            """, (limit,))

        return [dict(row) for row in cursor.fetchall()]

    def load_research(self, research_id: str) -> Optional[Dict[str, Any]]:
        """Load full research from JSON file"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT file_path FROM research_findings WHERE research_id = ?", (research_id,))

        row = cursor.fetchone()
        if not row:
            return None

        file_path = Path(row['file_path'])
        if not file_path.exists():
            logger.warning(f"Research file not found: {file_path}")
            return None

        with open(file_path) as f:
            return json.load(f)
