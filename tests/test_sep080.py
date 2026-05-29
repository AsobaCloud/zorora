"""SEP-080: finish user-data isolation — pipeline PK, feasibility, legacy greenfield.

Verifies the three gaps closed in SEP-080:
  1. upsert_pipeline_asset namespaces the primary key by user_id, so two users
     saving the same source asset get distinct rows instead of one overwriting
     the other via INSERT OR REPLACE.
  2. feasibility_results are isolated per owner: a result written by user A is
     invisible to user B at the store layer (read / single / progress).
  3. greenfield watchlist sites are isolated per owner.

These exercise the store layer directly with a temp DB (the same pattern other
imaging tests use). The HTTP layer reuses the same store methods, so store-level
isolation is the load-bearing guarantee.
"""

from __future__ import annotations

import pytest

USER_A = "user-aaa"
USER_B = "user-bbb"


@pytest.fixture()
def store(tmp_path):
    from tools.imaging.store import ImagingDataStore

    s = ImagingDataStore(db_path=str(tmp_path / "imaging_test.db"))
    yield s
    s.close()


def _asset(source_asset_id="123", name="Plant X"):
    return {
        "properties": {
            "id": source_asset_id,
            "name": name,
            "asset_name": name,
            "technology": "solar",
            "capacity_mw": 50,
            "country": "ZA",
            "lat": -26.0,
            "lon": 28.0,
        }
    }


# --- Gap 1: pipeline asset PK collision ------------------------------------

def test_pipeline_asset_two_users_same_source_do_not_collide(store):
    a = store.upsert_pipeline_asset("gem", _asset(name="A's plant"), user_id=USER_A)
    b = store.upsert_pipeline_asset("gem", _asset(name="B's plant"), user_id=USER_B)

    # Distinct primary keys — B did not overwrite A.
    assert a["id"] != b["id"], "pipeline asset ids collided across users"

    # A still owns the original row with the original name.
    a_row = store.get_pipeline_asset(a["id"], user_ids=[USER_A])
    assert a_row is not None
    assert a_row["asset_name"] == "A's plant"

    # B cannot see A's asset; A cannot see B's.
    assert store.get_pipeline_asset(a["id"], user_ids=[USER_B]) is None
    assert store.get_pipeline_asset(b["id"], user_ids=[USER_A]) is None

    a_list = store.list_pipeline_assets(user_ids=[USER_A])
    assert {row["id"] for row in a_list} == {a["id"]}


def test_pipeline_asset_legacy_null_owner_preserved(store):
    # No user_id => legacy/public bucket, unchanged id format.
    legacy = store.upsert_pipeline_asset("gem", _asset(source_asset_id="999"))
    assert legacy["id"] == "gem:999"
    assert store.get_pipeline_asset("gem:999", user_ids=[USER_A]) is None
    assert store.get_pipeline_asset("gem:999") is not None  # NULL-owner lookup


# --- Gap 2: feasibility isolation ------------------------------------------

def _findings():
    return {"key_finding": "ok", "risks": [], "gaps": [], "sources": [], "evidence_rows": []}


def test_feasibility_results_isolated_by_owner(store):
    item_id = "gem:abc"
    store.upsert_feasibility_result(
        item_id=item_id, item_type="brownfield", tab="production",
        conclusion="favorable", confidence="high", findings=_findings(),
        user_id=USER_A,
    )

    # A sees it; B does not.
    assert len(store.get_feasibility_results(item_id, user_ids=[USER_A])) == 1
    assert store.get_feasibility_results(item_id, user_ids=[USER_B]) == []

    assert store.get_feasibility_result(item_id, "production", user_ids=[USER_A]) is not None
    assert store.get_feasibility_result(item_id, "production", user_ids=[USER_B]) is None

    assert store.get_feasibility_progress(item_id, user_ids=[USER_A])["completed"] == 1
    assert store.get_feasibility_progress(item_id, user_ids=[USER_B])["completed"] == 0


# --- Gap 3: greenfield watchlist isolation ---------------------------------

def _site(name="Site Z"):
    return {"name": name, "technology": "wind", "country": "ZA", "lat": -25.0, "lon": 27.0}


def test_watchlist_sites_isolated_by_owner(store):
    a = store.upsert_watchlist_site(_site("A site"), user_id=USER_A)
    store.upsert_watchlist_site(_site("B site"), user_id=USER_B)

    a_ids = {row["id"] for row in store.list_watchlist_sites(user_ids=[USER_A])}
    b_ids = {row["id"] for row in store.list_watchlist_sites(user_ids=[USER_B])}
    assert a["id"] in a_ids
    assert a["id"] not in b_ids
    assert a_ids.isdisjoint(b_ids)

    # compare-by-ids respects ownership
    assert store.get_watchlist_sites_by_ids([a["id"]], user_ids=[USER_B]) == []
    assert len(store.get_watchlist_sites_by_ids([a["id"]], user_ids=[USER_A])) == 1
