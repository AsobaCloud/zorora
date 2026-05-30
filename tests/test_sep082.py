"""Tests for SEP-082: LocalStorage graceful migration of pre-existing research_findings table.

The application must boot against a SQLite database whose `research_findings` table
was created by an older schema version that does NOT include the `user_id` column.

Success criteria (per spec):
  - LocalStorage(db_path=...) constructed against such a DB initializes WITHOUT raising.
  - After construction, `research_findings` has a `user_id` column.
  - After construction, an index named `idx_user_id` exists on `research_findings`.
  - A brand-new (empty) database still initializes cleanly and has the same column/index.

All tests are expected to FAIL until SEP-082 is implemented.
"""

from __future__ import annotations

import sqlite3
import pathlib



# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

OLD_SCHEMA_DDL = """
CREATE TABLE research_findings (
    research_id TEXT PRIMARY KEY,
    query TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    synthesis TEXT,
    file_path TEXT NOT NULL,
    total_sources INTEGER,
    max_depth INTEGER
)
"""

# Additional legacy-era tables that may exist alongside the old findings table.
LEGACY_SOURCES_DDL = """
CREATE TABLE IF NOT EXISTS sources (
    source_id TEXT PRIMARY KEY,
    research_id TEXT NOT NULL,
    url TEXT NOT NULL
)
"""


def _create_old_schema_db(db_path: pathlib.Path) -> None:
    """Create a SQLite database that looks like a pre-user_id deployment."""
    conn = sqlite3.connect(str(db_path))
    conn.execute(OLD_SCHEMA_DDL)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_query ON research_findings(query)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_created_at ON research_findings(created_at DESC)"
    )
    # Deliberately omit the idx_user_id index — that is the missing piece.
    conn.execute(LEGACY_SOURCES_DDL)
    conn.commit()
    conn.close()


def _create_old_schema_db_with_data(db_path: pathlib.Path) -> None:
    """Old-schema DB pre-populated with a row (no user_id column)."""
    _create_old_schema_db(db_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO research_findings "
        "(research_id, query, created_at, file_path) "
        "VALUES (?, ?, datetime('now'), ?)",
        ("legacy_001", "solar energy zambia", "/tmp/legacy_001.json"),
    )
    conn.commit()
    conn.close()


def _column_names(db_path: pathlib.Path, table: str) -> set:
    conn = sqlite3.connect(str(db_path))
    cur = conn.execute(f"PRAGMA table_info({table})")
    names = {row[1] for row in cur.fetchall()}
    conn.close()
    return names


def _index_names(db_path: pathlib.Path, table: str) -> set:
    conn = sqlite3.connect(str(db_path))
    cur = conn.execute(f"PRAGMA index_list({table})")
    names = {row[1] for row in cur.fetchall()}
    conn.close()
    return names


def _make_local_storage(db_path):
    from engine.storage import LocalStorage
    return LocalStorage(db_path=str(db_path))


# ===========================================================================
# 1. Happy path — brand-new empty database (regression guard)
# ===========================================================================


class TestNewDatabaseInit:
    """LocalStorage must initialize cleanly on a fresh, empty database."""

    def test_hp1_new_db_does_not_raise(self, tmp_path):
        """Constructing LocalStorage on a new DB must not raise any exception."""
        db_path = tmp_path / "fresh.db"
        store = _make_local_storage(db_path)
        store.close()

    def test_hp2_new_db_has_user_id_column(self, tmp_path):
        """After init on a new DB, research_findings must have a user_id column."""
        db_path = tmp_path / "fresh.db"
        store = _make_local_storage(db_path)
        store.close()

        columns = _column_names(db_path, "research_findings")
        assert "user_id" in columns, (
            f"user_id column missing from fresh research_findings. "
            f"Columns present: {columns}"
        )

    def test_hp3_new_db_has_idx_user_id_index(self, tmp_path):
        """After init on a new DB, idx_user_id index must exist on research_findings."""
        db_path = tmp_path / "fresh.db"
        store = _make_local_storage(db_path)
        store.close()

        indexes = _index_names(db_path, "research_findings")
        assert "idx_user_id" in indexes, (
            f"idx_user_id index missing from fresh research_findings. "
            f"Indexes present: {indexes}"
        )


# ===========================================================================
# 2. Old-schema database — migration path (the core SEP-082 requirement)
# ===========================================================================


class TestOldSchemaDBInit:
    """LocalStorage must handle a pre-existing research_findings table without user_id."""

    def test_hp4_old_schema_does_not_raise_on_init(self, tmp_path):
        """Constructing LocalStorage against an old-schema DB must not raise."""
        db_path = tmp_path / "old_schema.db"
        _create_old_schema_db(db_path)

        # This must NOT raise — prior to the fix it raises OperationalError because
        # CREATE TABLE IF NOT EXISTS succeeds but IDX creation fails or user_id is missing.
        store = _make_local_storage(db_path)
        store.close()

    def test_hp5_old_schema_gets_user_id_column_after_init(self, tmp_path):
        """After LocalStorage init against old-schema DB, user_id column must be present."""
        db_path = tmp_path / "old_schema.db"
        _create_old_schema_db(db_path)

        store = _make_local_storage(db_path)
        store.close()

        columns = _column_names(db_path, "research_findings")
        assert "user_id" in columns, (
            f"user_id column not added to old-schema research_findings. "
            f"Columns present: {columns}"
        )

    def test_hp6_old_schema_gets_idx_user_id_after_init(self, tmp_path):
        """After LocalStorage init against old-schema DB, idx_user_id must exist."""
        db_path = tmp_path / "old_schema.db"
        _create_old_schema_db(db_path)

        store = _make_local_storage(db_path)
        store.close()

        indexes = _index_names(db_path, "research_findings")
        assert "idx_user_id" in indexes, (
            f"idx_user_id index not created on old-schema research_findings. "
            f"Indexes present: {indexes}"
        )


# ===========================================================================
# 3. Old-schema DB with pre-existing data — rows must be preserved
# ===========================================================================


class TestOldSchemaDataPreservation:
    """Pre-existing rows in the old research_findings table must survive migration."""

    def test_ec1_existing_rows_preserved_after_migration(self, tmp_path):
        """Legacy rows must still be present after LocalStorage init migrates the table."""
        db_path = tmp_path / "old_data.db"
        _create_old_schema_db_with_data(db_path)

        store = _make_local_storage(db_path)
        store.close()

        conn = sqlite3.connect(str(db_path))
        cur = conn.execute(
            "SELECT research_id, query FROM research_findings WHERE research_id = 'legacy_001'"
        )
        row = cur.fetchone()
        conn.close()

        assert row is not None, (
            "Legacy row 'legacy_001' was lost during migration — existing data must be preserved"
        )
        assert row[1] == "solar energy zambia", (
            f"Legacy row data corrupted: expected 'solar energy zambia', got {row[1]!r}"
        )

    def test_ec2_legacy_rows_have_null_user_id_after_migration(self, tmp_path):
        """Rows that existed before migration must have user_id=NULL (not some default)."""
        db_path = tmp_path / "old_data.db"
        _create_old_schema_db_with_data(db_path)

        store = _make_local_storage(db_path)
        store.close()

        conn = sqlite3.connect(str(db_path))
        cur = conn.execute(
            "SELECT user_id FROM research_findings WHERE research_id = 'legacy_001'"
        )
        row = cur.fetchone()
        conn.close()

        assert row is not None, "Row 'legacy_001' must exist after migration"
        assert row[0] is None, (
            f"Pre-existing rows should have user_id=NULL after migration, got {row[0]!r}"
        )

    def test_ec3_row_count_unchanged_after_migration(self, tmp_path):
        """Migration must not duplicate or delete rows."""
        db_path = tmp_path / "old_data.db"
        _create_old_schema_db_with_data(db_path)

        # Verify pre-migration count
        conn = sqlite3.connect(str(db_path))
        pre_count = conn.execute("SELECT COUNT(*) FROM research_findings").fetchone()[0]
        conn.close()

        store = _make_local_storage(db_path)
        store.close()

        conn = sqlite3.connect(str(db_path))
        post_count = conn.execute("SELECT COUNT(*) FROM research_findings").fetchone()[0]
        conn.close()

        assert post_count == pre_count, (
            f"Row count changed during migration: was {pre_count}, now {post_count}. "
            "Migration must not add or remove rows."
        )


# ===========================================================================
# 4. Idempotency — running init twice must not raise
# ===========================================================================


class TestIdempotency:
    """_init_schema must be safe to run against an already-migrated database."""

    def test_ec4_second_init_on_migrated_db_does_not_raise(self, tmp_path):
        """Opening LocalStorage twice on the same old-schema DB must not raise on second open."""
        db_path = tmp_path / "idempotent.db"
        _create_old_schema_db(db_path)

        store_a = _make_local_storage(db_path)
        store_a.close()

        # Second open — the table already has user_id; adding the column again must not fail.
        store_b = _make_local_storage(db_path)
        store_b.close()

    def test_ec5_second_init_on_fresh_db_does_not_raise(self, tmp_path):
        """Opening LocalStorage twice on a fresh DB (both have user_id) must not raise."""
        db_path = tmp_path / "fresh_idempotent.db"

        store_a = _make_local_storage(db_path)
        store_a.close()

        store_b = _make_local_storage(db_path)
        store_b.close()


# ===========================================================================
# 5. Schema integrity after migration
# ===========================================================================


class TestSchemaIntegrityAfterMigration:
    """All expected columns and indexes must be present after migrating an old-schema DB."""

    def test_ec6_all_expected_columns_present_after_migration(self, tmp_path):
        """research_findings must have all its defined columns after migration."""
        db_path = tmp_path / "old_schema.db"
        _create_old_schema_db(db_path)

        store = _make_local_storage(db_path)
        store.close()

        columns = _column_names(db_path, "research_findings")
        expected = {
            "research_id",
            "user_id",
            "query",
            "created_at",
            "completed_at",
            "synthesis",
            "file_path",
            "total_sources",
            "max_depth",
        }
        missing = expected - columns
        assert not missing, (
            f"After migration, research_findings is missing columns: {missing}. "
            f"Columns present: {columns}"
        )

    def test_ec7_other_indexes_preserved_after_migration(self, tmp_path):
        """Pre-existing indexes (idx_query, idx_created_at) must survive migration."""
        db_path = tmp_path / "old_schema.db"
        _create_old_schema_db(db_path)

        store = _make_local_storage(db_path)
        store.close()

        indexes = _index_names(db_path, "research_findings")
        for expected_index in ("idx_query", "idx_created_at", "idx_user_id"):
            assert expected_index in indexes, (
                f"Index '{expected_index}' missing after migration. "
                f"Indexes present: {indexes}"
            )

    def test_ec8_other_tables_unaffected_by_migration(self, tmp_path):
        """Tables other than research_findings must still exist after migration."""
        db_path = tmp_path / "old_schema.db"
        _create_old_schema_db(db_path)

        store = _make_local_storage(db_path)
        store.close()

        conn = sqlite3.connect(str(db_path))
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = {row[0] for row in cur.fetchall()}
        conn.close()

        # Tables defined in the current full schema that must all be present
        for expected_table in (
            "research_findings",
            "sources",
            "citations",
            "research_feedback",
            "research_chat_history",
            "user_settings",
        ):
            assert expected_table in tables, (
                f"Table '{expected_table}' missing after LocalStorage init on old-schema DB. "
                f"Tables present: {tables}"
            )


# ===========================================================================
# 6. Error handling — db path in non-existent directory
# ===========================================================================


class TestErrorHandling:
    """LocalStorage must create parent directories if they do not exist."""

    def test_eh1_missing_parent_directory_created(self, tmp_path):
        """LocalStorage must create the parent directory tree if it doesn't exist."""
        db_path = tmp_path / "nested" / "deep" / "zorora.db"
        # Parent does not exist yet — LocalStorage must create it.
        store = _make_local_storage(db_path)
        store.close()
        assert db_path.exists(), (
            f"DB file was not created at {db_path}"
        )


# ===========================================================================
# 7. Invariant — user_id column allows NULL values
# ===========================================================================


class TestUserIdColumnNullability:
    """The user_id column added during migration must be nullable (NULL for legacy data)."""

    def test_inv1_user_id_column_allows_null(self, tmp_path):
        """Inserting a row with user_id=NULL must succeed after migration."""
        db_path = tmp_path / "old_schema.db"
        _create_old_schema_db(db_path)

        store = _make_local_storage(db_path)
        store.close()

        conn = sqlite3.connect(str(db_path))
        # This must not raise — user_id must default to nullable.
        conn.execute(
            "INSERT INTO research_findings "
            "(research_id, user_id, query, created_at, file_path) "
            "VALUES (?, NULL, ?, datetime('now'), ?)",
            ("test_null_user", "test query", "/tmp/test.json"),
        )
        conn.commit()
        cur = conn.execute(
            "SELECT user_id FROM research_findings WHERE research_id = 'test_null_user'"
        )
        row = cur.fetchone()
        conn.close()

        assert row is not None, "Inserted row not found"
        assert row[0] is None, f"user_id should be NULL, got {row[0]!r}"

    def test_inv2_user_id_column_accepts_non_null_value(self, tmp_path):
        """Inserting a row with a non-NULL user_id must also succeed after migration."""
        db_path = tmp_path / "old_schema.db"
        _create_old_schema_db(db_path)

        store = _make_local_storage(db_path)
        store.close()

        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "INSERT INTO research_findings "
            "(research_id, user_id, query, created_at, file_path) "
            "VALUES (?, ?, ?, datetime('now'), ?)",
            ("test_with_user", "user@example.com", "query with user", "/tmp/test2.json"),
        )
        conn.commit()
        cur = conn.execute(
            "SELECT user_id FROM research_findings WHERE research_id = 'test_with_user'"
        )
        row = cur.fetchone()
        conn.close()

        assert row is not None, "Inserted row not found"
        assert row[0] == "user@example.com", f"user_id should be 'user@example.com', got {row[0]!r}"
