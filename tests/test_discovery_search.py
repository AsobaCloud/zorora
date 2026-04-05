"""Tests for Discovery map search (local SQLite search_discovery)."""

import os
import tempfile

import pytest


@pytest.fixture()
def tmp_store():
    path = tempfile.mktemp(suffix=".db")
    try:
        from tools.imaging.store import ImagingDataStore

        yield ImagingDataStore(db_path=path)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def test_search_discovery_short_query_returns_empty(tmp_store):
    assert tmp_store.search_discovery("", limit=10) == []
    assert tmp_store.search_discovery("a", limit=10) == []


def test_search_discovery_finds_generation_by_name(tmp_store):
    feat = {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [28.5, -25.9]},
        "properties": {
            "name": "Norton Solar Park",
            "technology": "solar",
            "capacity_mw": 100,
            "status": "announced",
            "country": "Zimbabwe",
        },
    }
    tmp_store.upsert_generation_assets([feat])
    hits = tmp_store.search_discovery("norton", limit=10)
    assert any(h["kind"] == "generation" and "Norton" in h["name"] for h in hits)


def test_update_pipeline_notes_roundtrip(tmp_store):
    tmp_store.upsert_pipeline_asset(
        "brownfield",
        {
            "properties": {
                "id": "g1",
                "name": "Plant X",
                "technology": "solar",
                "capacity_mw": 10,
                "country": "ZA",
                "lat": -26.0,
                "lon": 28.0,
            }
        },
    )
    cur = tmp_store.conn.cursor()
    cur.execute("SELECT id FROM pipeline_assets LIMIT 1")
    aid = cur.fetchone()[0]
    tmp_store.update_pipeline_notes(aid, "  follow up with owner  ")
    row = tmp_store.get_pipeline_asset(aid)
    assert row["notes"].strip() == "follow up with owner"
