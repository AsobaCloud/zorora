"""Tests for SEP-044: Scouting Section with Kanban Pipeline.

Covers:
  - ImagingDataStore: scouting_stage column on pipeline_assets and
    scouting_watchlist tables, update_scouting_stage(), list_scouting_items(),
    and _row_to_* helper inclusion of scouting_stage.
  - Flask API: GET/PUT/DELETE /api/scouting/items endpoints.
  - Integration: round-trip from asset creation through stage transitions.

All tests are expected to FAIL until SEP-044 is implemented.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Helpers / fixtures shared by store and API tests
# ---------------------------------------------------------------------------

VALID_STAGES = ["identified", "scored", "feasibility", "diligence", "decision"]


def _make_brownfield_asset(name: str = "Kafue Solar", country: str = "Zambia") -> dict:
    """Minimal brownfield asset payload accepted by upsert_pipeline_asset."""
    return {
        "properties": {
            "site_id": f"gen:{name.lower().replace(' ', '_')}",
            "name": name,
            "technology": "solar",
            "capacity_mw": 100.0,
            "status": "operating",
            "operator": "Acme Energy",
            "owner": "Acme Energy",
            "country": country,
        },
        "geometry": {"type": "Point", "coordinates": [27.8, -15.4]},
    }


_greenfield_counter = 0


def _make_greenfield_site(name: str = "Limpopo Ridge", country: str = "South Africa") -> dict:
    """Minimal greenfield site payload accepted by upsert_watchlist_site."""
    global _greenfield_counter
    _greenfield_counter += 1
    return {
        "name": name,
        "technology": "solar",
        "lat": -24.5 + (_greenfield_counter * 0.01),
        "lon": 29.0 + (_greenfield_counter * 0.01),
        "overall_score": 72.0,
        "score_label": "strong",
        "country": country,
        "factors": [],
        "resource_summary": {},
    }


# ---------------------------------------------------------------------------
# 1. Store tests — scouting_stage column defaults
# ---------------------------------------------------------------------------


class TestScoutingStageColumnDefaults:
    """After SEP-044, both tables must carry a scouting_stage column with defaults."""

    def test_pipeline_asset_has_scouting_stage_column(self, tmp_path):
        """pipeline_assets schema must include scouting_stage column."""
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "store.db"))
        cur = store.conn.cursor()
        cur.execute("PRAGMA table_info(pipeline_assets)")
        columns = {row["name"] for row in cur.fetchall()}
        store.close()
        assert "scouting_stage" in columns, (
            "pipeline_assets table must have a scouting_stage column after SEP-044"
        )

    def test_scouting_watchlist_has_scouting_stage_column(self, tmp_path):
        """scouting_watchlist schema must include scouting_stage column."""
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "store.db"))
        cur = store.conn.cursor()
        cur.execute("PRAGMA table_info(scouting_watchlist)")
        columns = {row["name"] for row in cur.fetchall()}
        store.close()
        assert "scouting_stage" in columns, (
            "scouting_watchlist table must have a scouting_stage column after SEP-044"
        )

    def test_new_brownfield_asset_defaults_to_identified_stage(self, tmp_path):
        """A freshly inserted pipeline asset must default to stage 'identified'."""
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "store.db"))
        asset = store.upsert_pipeline_asset("brownfield", _make_brownfield_asset())
        store.close()
        assert asset.get("scouting_stage") == "identified", (
            f"Expected 'identified', got {asset.get('scouting_stage')!r}"
        )

    def test_new_greenfield_site_defaults_to_scored_stage(self, tmp_path):
        """A freshly inserted watchlist site must default to stage 'scored'."""
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "store.db"))
        site = store.upsert_watchlist_site(_make_greenfield_site())
        store.close()
        assert site.get("scouting_stage") == "scored", (
            f"Expected 'scored', got {site.get('scouting_stage')!r}"
        )

    def test_new_bess_asset_defaults_to_identified_stage(self, tmp_path):
        """A BESS pipeline asset must also default to stage 'identified'."""
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "store.db"))
        bess_payload = _make_brownfield_asset("Kariba BESS")
        bess_payload["properties"]["technology"] = "bess"
        asset = store.upsert_pipeline_asset("bess", bess_payload)
        store.close()
        assert asset.get("scouting_stage") == "identified", (
            f"Expected 'identified' for BESS asset, got {asset.get('scouting_stage')!r}"
        )


# ---------------------------------------------------------------------------
# 2. Store tests — _row_to_* helpers include scouting_stage
# ---------------------------------------------------------------------------


class TestRowHelperIncludesStagingField:
    """_row_to_pipeline_asset and _row_to_watchlist_site must expose scouting_stage."""

    def test_row_to_pipeline_asset_includes_scouting_stage(self, tmp_path):
        """_row_to_pipeline_asset must include 'scouting_stage' key in the returned dict."""
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "store.db"))
        asset = store.upsert_pipeline_asset("brownfield", _make_brownfield_asset())
        store.close()
        assert "scouting_stage" in asset, (
            "pipeline asset dict must contain 'scouting_stage' key"
        )

    def test_row_to_watchlist_site_includes_scouting_stage(self, tmp_path):
        """_row_to_watchlist_site must include 'scouting_stage' key in the returned dict."""
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "store.db"))
        site = store.upsert_watchlist_site(_make_greenfield_site())
        store.close()
        assert "scouting_stage" in site, (
            "watchlist site dict must contain 'scouting_stage' key"
        )

    def test_get_pipeline_asset_includes_scouting_stage(self, tmp_path):
        """get_pipeline_asset must return dict including scouting_stage."""
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "store.db"))
        asset = store.upsert_pipeline_asset("brownfield", _make_brownfield_asset())
        fetched = store.get_pipeline_asset(asset["id"])
        store.close()
        assert fetched is not None
        assert "scouting_stage" in fetched

    def test_get_watchlist_site_includes_scouting_stage(self, tmp_path):
        """get_watchlist_site must return dict including scouting_stage."""
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "store.db"))
        site = store.upsert_watchlist_site(_make_greenfield_site())
        fetched = store.get_watchlist_site(site["id"])
        store.close()
        assert fetched is not None
        assert "scouting_stage" in fetched


# ---------------------------------------------------------------------------
# 3. Store tests — update_scouting_stage()
# ---------------------------------------------------------------------------


class TestUpdateScoutingStage:
    """update_scouting_stage must mutate the correct row in the correct table."""

    def test_update_brownfield_stage_to_scored(self, tmp_path):
        """Updating a brownfield asset stage must persist the new stage."""
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "store.db"))
        asset = store.upsert_pipeline_asset("brownfield", _make_brownfield_asset())
        store.update_scouting_stage("brownfield", asset["id"], "scored")
        updated = store.get_pipeline_asset(asset["id"])
        store.close()
        assert updated["scouting_stage"] == "scored", (
            f"Expected 'scored' after update, got {updated['scouting_stage']!r}"
        )

    def test_update_greenfield_stage_to_feasibility(self, tmp_path):
        """Updating a greenfield site stage must persist in scouting_watchlist."""
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "store.db"))
        site = store.upsert_watchlist_site(_make_greenfield_site())
        store.update_scouting_stage("greenfield", site["id"], "feasibility")
        updated = store.get_watchlist_site(site["id"])
        store.close()
        assert updated["scouting_stage"] == "feasibility", (
            f"Expected 'feasibility', got {updated['scouting_stage']!r}"
        )

    def test_update_bess_stage_routes_to_pipeline_assets(self, tmp_path):
        """Updating a BESS item's stage must update the pipeline_assets row."""
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "store.db"))
        bess_payload = _make_brownfield_asset("Itezhi BESS")
        bess_payload["properties"]["technology"] = "bess"
        asset = store.upsert_pipeline_asset("bess", bess_payload)
        store.update_scouting_stage("bess", asset["id"], "diligence")
        updated = store.get_pipeline_asset(asset["id"])
        store.close()
        assert updated["scouting_stage"] == "diligence"

    def test_update_stage_to_decision(self, tmp_path):
        """All five valid stages must be reachable, including 'decision'."""
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "store.db"))
        asset = store.upsert_pipeline_asset("brownfield", _make_brownfield_asset())
        for stage in VALID_STAGES:
            store.update_scouting_stage("brownfield", asset["id"], stage)
            updated = store.get_pipeline_asset(asset["id"])
            assert updated["scouting_stage"] == stage, (
                f"Expected stage '{stage}', got {updated['scouting_stage']!r}"
            )
        store.close()

    def test_update_stage_for_nonexistent_id_does_not_raise(self, tmp_path):
        """update_scouting_stage on a missing ID must not raise an exception."""
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "store.db"))
        # Should silently do nothing, not raise
        store.update_scouting_stage("brownfield", "nonexistent-id", "scored")
        store.close()

    def test_update_does_not_alter_other_fields(self, tmp_path):
        """Stage update must not overwrite asset_name or other pipeline_assets fields."""
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "store.db"))
        asset = store.upsert_pipeline_asset("brownfield", _make_brownfield_asset("Kafue Solar"))
        original_name = asset["asset_name"]
        store.update_scouting_stage("brownfield", asset["id"], "scored")
        updated = store.get_pipeline_asset(asset["id"])
        store.close()
        assert updated["asset_name"] == original_name, (
            "Stage update must not modify asset_name"
        )

    def test_update_stage_invalid_type_raises_value_error(self, tmp_path):
        """update_scouting_stage with an invalid item_type must raise ValueError."""
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "store.db"))
        with pytest.raises(ValueError, match="item_type"):
            store.update_scouting_stage("nuclear", "some-id", "scored")
        store.close()

    def test_update_stage_invalid_stage_raises_value_error(self, tmp_path):
        """update_scouting_stage with an invalid stage must raise ValueError."""
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "store.db"))
        asset = store.upsert_pipeline_asset("brownfield", _make_brownfield_asset())
        with pytest.raises(ValueError, match="stage"):
            store.update_scouting_stage("brownfield", asset["id"], "published")
        store.close()

    def test_update_stage_idempotent_same_stage_twice(self, tmp_path):
        """Setting the same stage twice must succeed without error or data corruption."""
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "store.db"))
        asset = store.upsert_pipeline_asset("brownfield", _make_brownfield_asset())
        store.update_scouting_stage("brownfield", asset["id"], "scored")
        store.update_scouting_stage("brownfield", asset["id"], "scored")
        updated = store.get_pipeline_asset(asset["id"])
        store.close()
        assert updated["scouting_stage"] == "scored"


# ---------------------------------------------------------------------------
# 4. Store tests — list_scouting_items()
# ---------------------------------------------------------------------------


class TestListScoutingItems:
    """list_scouting_items must query the correct table and optionally filter by stage."""

    def test_list_brownfield_returns_pipeline_assets(self, tmp_path):
        """list_scouting_items('brownfield') must return items from pipeline_assets."""
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "store.db"))
        store.upsert_pipeline_asset("brownfield", _make_brownfield_asset("Asset Alpha"))
        store.upsert_pipeline_asset("brownfield", _make_brownfield_asset("Asset Beta"))
        items = store.list_scouting_items("brownfield")
        store.close()
        assert len(items) == 2
        names = {item["asset_name"] for item in items}
        assert "Asset Alpha" in names
        assert "Asset Beta" in names

    def test_list_greenfield_returns_watchlist_sites(self, tmp_path):
        """list_scouting_items('greenfield') must return items from scouting_watchlist."""
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "store.db"))
        store.upsert_watchlist_site(_make_greenfield_site("Site Gamma"))
        items = store.list_scouting_items("greenfield")
        store.close()
        assert len(items) == 1
        assert items[0]["name"] == "Site Gamma"

    def test_list_bess_returns_only_bess_source_type(self, tmp_path):
        """list_scouting_items('bess') must return only pipeline_assets with source_type='bess'."""
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "store.db"))
        # Insert one brownfield and one BESS asset
        store.upsert_pipeline_asset("brownfield", _make_brownfield_asset("Solar Farm"))
        bess_payload = _make_brownfield_asset("Grid BESS")
        bess_payload["properties"]["technology"] = "bess"
        store.upsert_pipeline_asset("bess", bess_payload)

        bess_items = store.list_scouting_items("bess")
        store.close()
        assert len(bess_items) == 1
        assert bess_items[0]["source_type"] == "bess"

    def test_list_with_stage_filter_returns_only_matching_stage(self, tmp_path):
        """list_scouting_items with stage kwarg must only return items at that stage."""
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "store.db"))
        asset1 = store.upsert_pipeline_asset("brownfield", _make_brownfield_asset("Kwale Solar"))
        asset2 = store.upsert_pipeline_asset("brownfield", _make_brownfield_asset("Athi Solar"))
        # Move asset1 to 'scored', leave asset2 at 'identified'
        store.update_scouting_stage("brownfield", asset1["id"], "scored")

        identified = store.list_scouting_items("brownfield", stage="identified")
        scored = store.list_scouting_items("brownfield", stage="scored")
        store.close()

        assert len(identified) == 1
        assert identified[0]["id"] == asset2["id"]
        assert len(scored) == 1
        assert scored[0]["id"] == asset1["id"]

    def test_list_with_stage_filter_returns_empty_when_none_match(self, tmp_path):
        """list_scouting_items with a stage that matches no items returns empty list."""
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "store.db"))
        store.upsert_pipeline_asset("brownfield", _make_brownfield_asset())
        result = store.list_scouting_items("brownfield", stage="decision")
        store.close()
        assert result == []

    def test_list_returns_empty_for_empty_store(self, tmp_path):
        """list_scouting_items on an empty store returns an empty list."""
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "store.db"))
        assert store.list_scouting_items("brownfield") == []
        assert store.list_scouting_items("greenfield") == []
        assert store.list_scouting_items("bess") == []
        store.close()

    def test_list_items_each_contain_scouting_stage(self, tmp_path):
        """Every item returned by list_scouting_items must include 'scouting_stage'."""
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "store.db"))
        store.upsert_pipeline_asset("brownfield", _make_brownfield_asset())
        items = store.list_scouting_items("brownfield")
        store.close()
        for item in items:
            assert "scouting_stage" in item, (
                f"Item {item.get('id')!r} is missing 'scouting_stage'"
            )

    def test_list_scouting_items_invalid_type_raises_value_error(self, tmp_path):
        """list_scouting_items with an invalid item_type must raise ValueError."""
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "store.db"))
        with pytest.raises(ValueError, match="item_type"):
            store.list_scouting_items("nuclear")
        store.close()


# ---------------------------------------------------------------------------
# 5. API tests — /api/scouting/items endpoints
# ---------------------------------------------------------------------------


@pytest.fixture
def client(tmp_path):
    """Flask test client with ImagingDataStore patched to a temp DB."""
    from ui.web.app import app
    from tools.imaging.store import ImagingDataStore

    store = ImagingDataStore(db_path=str(tmp_path / "api_test.db"))
    app.config["TESTING"] = True
    with patch("ui.web.app.ImagingDataStore", return_value=store):
        with app.test_client() as c:
            yield c, store
    store.close()


class TestScoutingItemsListEndpoint:
    """GET /api/scouting/items?type=<type> returns items with scouting_stage."""

    def test_list_brownfield_items_returns_200(self, tmp_path):
        """GET /api/scouting/items?type=brownfield responds 200."""
        from ui.web.app import app
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "api.db"))
        app.config["TESTING"] = True
        with patch("ui.web.app.ImagingDataStore", return_value=store):
            with app.test_client() as c:
                resp = c.get("/api/scouting/items?type=brownfield")
        store.close()
        assert resp.status_code == 200

    def test_list_brownfield_items_response_has_items_key(self, tmp_path):
        """GET /api/scouting/items?type=brownfield returns JSON with 'items' list."""
        from ui.web.app import app
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "api.db"))
        app.config["TESTING"] = True
        with patch("ui.web.app.ImagingDataStore", return_value=store):
            with app.test_client() as c:
                resp = c.get("/api/scouting/items?type=brownfield")
        store.close()
        data = resp.get_json()
        assert "items" in data
        assert isinstance(data["items"], list)

    def test_list_brownfield_items_includes_scouting_stage(self, tmp_path):
        """Each brownfield item in GET /api/scouting/items must carry scouting_stage."""
        from ui.web.app import app
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "api.db"))
        store.upsert_pipeline_asset("brownfield", _make_brownfield_asset("Tana Solar"))
        app.config["TESTING"] = True
        with patch("ui.web.app.ImagingDataStore", return_value=store):
            with app.test_client() as c:
                resp = c.get("/api/scouting/items?type=brownfield")
        store.close()
        data = resp.get_json()
        assert len(data["items"]) == 1
        assert "scouting_stage" in data["items"][0]

    def test_list_greenfield_items_returns_200(self, tmp_path):
        """GET /api/scouting/items?type=greenfield responds 200."""
        from ui.web.app import app
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "api.db"))
        app.config["TESTING"] = True
        with patch("ui.web.app.ImagingDataStore", return_value=store):
            with app.test_client() as c:
                resp = c.get("/api/scouting/items?type=greenfield")
        store.close()
        assert resp.status_code == 200

    def test_list_greenfield_items_default_stage_scored(self, tmp_path):
        """Greenfield items created via watchlist must appear with stage 'scored'."""
        from ui.web.app import app
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "api.db"))
        store.upsert_watchlist_site(_make_greenfield_site("Springbok Flats"))
        app.config["TESTING"] = True
        with patch("ui.web.app.ImagingDataStore", return_value=store):
            with app.test_client() as c:
                resp = c.get("/api/scouting/items?type=greenfield")
        store.close()
        data = resp.get_json()
        assert len(data["items"]) == 1
        assert data["items"][0]["scouting_stage"] == "scored"

    def test_list_bess_items_returns_200(self, tmp_path):
        """GET /api/scouting/items?type=bess responds 200."""
        from ui.web.app import app
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "api.db"))
        app.config["TESTING"] = True
        with patch("ui.web.app.ImagingDataStore", return_value=store):
            with app.test_client() as c:
                resp = c.get("/api/scouting/items?type=bess")
        store.close()
        assert resp.status_code == 200

    def test_list_bess_items_excludes_brownfield_assets(self, tmp_path):
        """BESS query must not return brownfield (non-bess source_type) pipeline assets."""
        from ui.web.app import app
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "api.db"))
        store.upsert_pipeline_asset("brownfield", _make_brownfield_asset("Wind Farm"))
        bess_payload = _make_brownfield_asset("BESS 1")
        bess_payload["properties"]["technology"] = "bess"
        store.upsert_pipeline_asset("bess", bess_payload)
        app.config["TESTING"] = True
        with patch("ui.web.app.ImagingDataStore", return_value=store):
            with app.test_client() as c:
                resp = c.get("/api/scouting/items?type=bess")
        store.close()
        data = resp.get_json()
        assert len(data["items"]) == 1
        assert data["items"][0]["source_type"] == "bess"

    def test_list_items_filtered_by_stage(self, tmp_path):
        """GET /api/scouting/items?type=greenfield&stage=scored filters by stage."""
        from ui.web.app import app
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "api.db"))
        site = store.upsert_watchlist_site(_make_greenfield_site("Orange River"))
        # Move to feasibility
        store.update_scouting_stage("greenfield", site["id"], "feasibility")
        # Add another site still at scored (default)
        store.upsert_watchlist_site(_make_greenfield_site("Namaqualand"))
        app.config["TESTING"] = True
        with patch("ui.web.app.ImagingDataStore", return_value=store):
            with app.test_client() as c:
                resp_scored = c.get("/api/scouting/items?type=greenfield&stage=scored")
                resp_feasibility = c.get("/api/scouting/items?type=greenfield&stage=feasibility")
        store.close()
        assert resp_scored.status_code == 200
        assert resp_feasibility.status_code == 200
        scored_data = resp_scored.get_json()
        feasibility_data = resp_feasibility.get_json()
        assert len(scored_data["items"]) == 1
        assert scored_data["items"][0]["name"] == "Namaqualand"
        assert len(feasibility_data["items"]) == 1
        assert feasibility_data["items"][0]["name"] == "Orange River"

    def test_list_items_missing_type_param_returns_400(self, tmp_path):
        """GET /api/scouting/items without 'type' param must return 400."""
        from ui.web.app import app
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "api.db"))
        app.config["TESTING"] = True
        with patch("ui.web.app.ImagingDataStore", return_value=store):
            with app.test_client() as c:
                resp = c.get("/api/scouting/items")
        store.close()
        assert resp.status_code == 400

    def test_list_items_invalid_type_returns_400(self, tmp_path):
        """GET /api/scouting/items?type=unknown must return 400."""
        from ui.web.app import app
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "api.db"))
        app.config["TESTING"] = True
        with patch("ui.web.app.ImagingDataStore", return_value=store):
            with app.test_client() as c:
                resp = c.get("/api/scouting/items?type=unknown")
        store.close()
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# 6. API tests — PUT /api/scouting/items/<id>/stage
# ---------------------------------------------------------------------------


class TestScoutingItemsUpdateStageEndpoint:
    """PUT /api/scouting/items/<id>/stage moves an item to a new pipeline stage."""

    def test_update_stage_brownfield_returns_200(self, tmp_path):
        """PUT with valid brownfield stage returns 200."""
        from ui.web.app import app
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "api.db"))
        asset = store.upsert_pipeline_asset("brownfield", _make_brownfield_asset())
        app.config["TESTING"] = True
        with patch("ui.web.app.ImagingDataStore", return_value=store):
            with app.test_client() as c:
                resp = c.put(
                    f"/api/scouting/items/{asset['id']}/stage",
                    json={"type": "brownfield", "stage": "scored"},
                )
        store.close()
        assert resp.status_code == 200

    def test_update_stage_persists_new_stage(self, tmp_path):
        """PUT /stage must actually persist the new stage in the database."""
        from ui.web.app import app
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "api.db"))
        asset = store.upsert_pipeline_asset("brownfield", _make_brownfield_asset())
        app.config["TESTING"] = True
        with patch("ui.web.app.ImagingDataStore", return_value=store):
            with app.test_client() as c:
                c.put(
                    f"/api/scouting/items/{asset['id']}/stage",
                    json={"type": "brownfield", "stage": "feasibility"},
                )
        updated = store.get_pipeline_asset(asset["id"])
        store.close()
        assert updated["scouting_stage"] == "feasibility"

    def test_update_stage_response_contains_updated_item(self, tmp_path):
        """PUT /stage response body must include the updated item with new stage."""
        from ui.web.app import app
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "api.db"))
        asset = store.upsert_pipeline_asset("brownfield", _make_brownfield_asset())
        app.config["TESTING"] = True
        with patch("ui.web.app.ImagingDataStore", return_value=store):
            with app.test_client() as c:
                resp = c.put(
                    f"/api/scouting/items/{asset['id']}/stage",
                    json={"type": "brownfield", "stage": "diligence"},
                )
        store.close()
        data = resp.get_json()
        assert "item" in data, (
            "PUT /stage response must include the updated item under 'item' key"
        )
        assert data["item"]["scouting_stage"] == "diligence", (
            "Returned item must reflect the new stage"
        )

    def test_update_stage_invalid_stage_returns_400(self, tmp_path):
        """PUT /stage with an invalid stage value must return 400."""
        from ui.web.app import app
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "api.db"))
        asset = store.upsert_pipeline_asset("brownfield", _make_brownfield_asset())
        app.config["TESTING"] = True
        with patch("ui.web.app.ImagingDataStore", return_value=store):
            with app.test_client() as c:
                resp = c.put(
                    f"/api/scouting/items/{asset['id']}/stage",
                    json={"type": "brownfield", "stage": "published"},
                )
        store.close()
        assert resp.status_code == 400

    def test_update_stage_missing_stage_field_returns_400(self, tmp_path):
        """PUT /stage without 'stage' in body must return 400."""
        from ui.web.app import app
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "api.db"))
        asset = store.upsert_pipeline_asset("brownfield", _make_brownfield_asset())
        app.config["TESTING"] = True
        with patch("ui.web.app.ImagingDataStore", return_value=store):
            with app.test_client() as c:
                resp = c.put(
                    f"/api/scouting/items/{asset['id']}/stage",
                    json={"type": "brownfield"},
                )
        store.close()
        assert resp.status_code == 400

    def test_update_stage_missing_type_field_returns_400(self, tmp_path):
        """PUT /stage without 'type' in body must return 400."""
        from ui.web.app import app
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "api.db"))
        asset = store.upsert_pipeline_asset("brownfield", _make_brownfield_asset())
        app.config["TESTING"] = True
        with patch("ui.web.app.ImagingDataStore", return_value=store):
            with app.test_client() as c:
                resp = c.put(
                    f"/api/scouting/items/{asset['id']}/stage",
                    json={"stage": "scored"},
                )
        store.close()
        assert resp.status_code == 400

    def test_update_stage_empty_body_returns_400(self, tmp_path):
        """PUT /stage with no JSON body must return 400."""
        from ui.web.app import app
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "api.db"))
        asset = store.upsert_pipeline_asset("brownfield", _make_brownfield_asset())
        app.config["TESTING"] = True
        with patch("ui.web.app.ImagingDataStore", return_value=store):
            with app.test_client() as c:
                resp = c.put(f"/api/scouting/items/{asset['id']}/stage")
        store.close()
        assert resp.status_code == 400

    def test_update_greenfield_stage_via_api(self, tmp_path):
        """PUT /stage for a greenfield item type must update the watchlist record."""
        from ui.web.app import app
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "api.db"))
        site = store.upsert_watchlist_site(_make_greenfield_site("Kalahari Site"))
        app.config["TESTING"] = True
        with patch("ui.web.app.ImagingDataStore", return_value=store):
            with app.test_client() as c:
                resp = c.put(
                    f"/api/scouting/items/{site['id']}/stage",
                    json={"type": "greenfield", "stage": "diligence"},
                )
        updated = store.get_watchlist_site(site["id"])
        store.close()
        assert resp.status_code == 200
        assert updated["scouting_stage"] == "diligence"

    def test_update_all_valid_stages_via_api(self, tmp_path):
        """Every valid stage must be settable via PUT /stage endpoint."""
        from ui.web.app import app
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "api.db"))
        asset = store.upsert_pipeline_asset("brownfield", _make_brownfield_asset())
        app.config["TESTING"] = True
        with patch("ui.web.app.ImagingDataStore", return_value=store):
            with app.test_client() as c:
                for stage in VALID_STAGES:
                    resp = c.put(
                        f"/api/scouting/items/{asset['id']}/stage",
                        json={"type": "brownfield", "stage": stage},
                    )
                    assert resp.status_code == 200, (
                        f"Stage '{stage}' should be valid but returned {resp.status_code}"
                    )
        store.close()


# ---------------------------------------------------------------------------
# 7. API tests — DELETE /api/scouting/items/<id>
# ---------------------------------------------------------------------------


class TestScoutingItemsDeleteEndpoint:
    """DELETE /api/scouting/items/<id>?type=<type> removes the item."""

    def test_delete_brownfield_item_returns_200(self, tmp_path):
        """DELETE brownfield item responds 200."""
        from ui.web.app import app
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "api.db"))
        asset = store.upsert_pipeline_asset("brownfield", _make_brownfield_asset())
        app.config["TESTING"] = True
        with patch("ui.web.app.ImagingDataStore", return_value=store):
            with app.test_client() as c:
                resp = c.delete(f"/api/scouting/items/{asset['id']}?type=brownfield")
        store.close()
        assert resp.status_code == 200

    def test_delete_brownfield_item_actually_removes_from_store(self, tmp_path):
        """DELETE /api/scouting/items/<id> must remove the record from pipeline_assets."""
        from ui.web.app import app
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "api.db"))
        asset = store.upsert_pipeline_asset("brownfield", _make_brownfield_asset())
        asset_id = asset["id"]
        app.config["TESTING"] = True
        with patch("ui.web.app.ImagingDataStore", return_value=store):
            with app.test_client() as c:
                c.delete(f"/api/scouting/items/{asset_id}?type=brownfield")
        remaining = store.get_pipeline_asset(asset_id)
        store.close()
        assert remaining is None

    def test_delete_greenfield_item_returns_200(self, tmp_path):
        """DELETE greenfield item responds 200."""
        from ui.web.app import app
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "api.db"))
        site = store.upsert_watchlist_site(_make_greenfield_site())
        app.config["TESTING"] = True
        with patch("ui.web.app.ImagingDataStore", return_value=store):
            with app.test_client() as c:
                resp = c.delete(f"/api/scouting/items/{site['id']}?type=greenfield")
        store.close()
        assert resp.status_code == 200

    def test_delete_greenfield_item_removes_from_watchlist(self, tmp_path):
        """DELETE greenfield item must remove the record from scouting_watchlist."""
        from ui.web.app import app
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "api.db"))
        site = store.upsert_watchlist_site(_make_greenfield_site("Cape Winelands"))
        site_id = site["id"]
        app.config["TESTING"] = True
        with patch("ui.web.app.ImagingDataStore", return_value=store):
            with app.test_client() as c:
                c.delete(f"/api/scouting/items/{site_id}?type=greenfield")
        remaining = store.get_watchlist_site(site_id)
        store.close()
        assert remaining is None

    def test_delete_missing_type_param_returns_400(self, tmp_path):
        """DELETE /api/scouting/items/<id> without 'type' query param returns 400."""
        from ui.web.app import app
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "api.db"))
        app.config["TESTING"] = True
        with patch("ui.web.app.ImagingDataStore", return_value=store):
            with app.test_client() as c:
                resp = c.delete("/api/scouting/items/some-fake-id")
        store.close()
        assert resp.status_code == 400

    def test_delete_bess_item_returns_200(self, tmp_path):
        """DELETE BESS item responds 200."""
        from ui.web.app import app
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "api.db"))
        bess_payload = _make_brownfield_asset("Hwange BESS")
        bess_payload["properties"]["technology"] = "bess"
        asset = store.upsert_pipeline_asset("bess", bess_payload)
        app.config["TESTING"] = True
        with patch("ui.web.app.ImagingDataStore", return_value=store):
            with app.test_client() as c:
                resp = c.delete(f"/api/scouting/items/{asset['id']}?type=bess")
        store.close()
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 8. API tests — POST /api/scouting/items (unified create)
# ---------------------------------------------------------------------------


class TestScoutingItemsCreateEndpoint:
    """POST /api/scouting/items creates items via the unified endpoint."""

    def test_create_brownfield_item_returns_200(self, tmp_path):
        """POST /api/scouting/items with type=brownfield creates a pipeline asset."""
        from ui.web.app import app
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "api.db"))
        app.config["TESTING"] = True
        with patch("ui.web.app.ImagingDataStore", return_value=store):
            with app.test_client() as c:
                resp = c.post(
                    "/api/scouting/items",
                    json={
                        "type": "brownfield",
                        "source_type": "generation",
                        "asset": _make_brownfield_asset("Lusaka Wind"),
                    },
                )
        store.close()
        assert resp.status_code == 200

    def test_create_brownfield_item_persists_in_store(self, tmp_path):
        """POST /api/scouting/items brownfield must persist the item in pipeline_assets."""
        from ui.web.app import app
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "api.db"))
        app.config["TESTING"] = True
        with patch("ui.web.app.ImagingDataStore", return_value=store):
            with app.test_client() as c:
                c.post(
                    "/api/scouting/items",
                    json={
                        "type": "brownfield",
                        "source_type": "generation",
                        "asset": _make_brownfield_asset("Lusaka Wind"),
                    },
                )
        items = store.list_pipeline_assets()
        store.close()
        assert len(items) == 1
        assert items[0]["asset_name"] == "Lusaka Wind"

    def test_create_greenfield_item_returns_200(self, tmp_path):
        """POST /api/scouting/items with type=greenfield creates a watchlist site."""
        from ui.web.app import app
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "api.db"))
        app.config["TESTING"] = True
        with patch("ui.web.app.ImagingDataStore", return_value=store):
            with app.test_client() as c:
                resp = c.post(
                    "/api/scouting/items",
                    json={
                        "type": "greenfield",
                        "site": _make_greenfield_site("Karoo Basin"),
                    },
                )
        store.close()
        assert resp.status_code == 200

    def test_create_greenfield_item_persists_with_scored_stage(self, tmp_path):
        """POST /api/scouting/items greenfield must persist with scouting_stage='scored'."""
        from ui.web.app import app
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "api.db"))
        app.config["TESTING"] = True
        with patch("ui.web.app.ImagingDataStore", return_value=store):
            with app.test_client() as c:
                c.post(
                    "/api/scouting/items",
                    json={
                        "type": "greenfield",
                        "site": _make_greenfield_site("Karoo Basin"),
                    },
                )
        items = store.list_scouting_items("greenfield")
        store.close()
        assert len(items) == 1
        assert items[0]["scouting_stage"] == "scored"

    def test_create_bess_item_persists_with_bess_source_type(self, tmp_path):
        """POST /api/scouting/items with type=bess sets source_type='bess' in pipeline_assets."""
        from ui.web.app import app
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "api.db"))
        bess_payload = _make_brownfield_asset("Midrand BESS")
        bess_payload["properties"]["technology"] = "bess"
        app.config["TESTING"] = True
        with patch("ui.web.app.ImagingDataStore", return_value=store):
            with app.test_client() as c:
                resp = c.post(
                    "/api/scouting/items",
                    json={
                        "type": "bess",
                        "source_type": "bess",
                        "asset": bess_payload,
                    },
                )
        items = store.list_scouting_items("bess")
        store.close()
        assert resp.status_code == 200
        assert len(items) == 1
        assert items[0]["source_type"] == "bess"

    def test_create_missing_type_returns_400(self, tmp_path):
        """POST /api/scouting/items without 'type' must return 400."""
        from ui.web.app import app
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "api.db"))
        app.config["TESTING"] = True
        with patch("ui.web.app.ImagingDataStore", return_value=store):
            with app.test_client() as c:
                resp = c.post(
                    "/api/scouting/items",
                    json={"source_type": "generation", "asset": _make_brownfield_asset()},
                )
        store.close()
        assert resp.status_code == 400

    def test_create_invalid_type_returns_400(self, tmp_path):
        """POST /api/scouting/items with type=nuclear must return 400."""
        from ui.web.app import app
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "api.db"))
        app.config["TESTING"] = True
        with patch("ui.web.app.ImagingDataStore", return_value=store):
            with app.test_client() as c:
                resp = c.post(
                    "/api/scouting/items",
                    json={"type": "nuclear", "asset": _make_brownfield_asset()},
                )
        store.close()
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# 9. Integration test — full pipeline lifecycle
# ---------------------------------------------------------------------------


class TestScoutingKanbanIntegration:
    """End-to-end: create asset via pipeline POST, trace through scouting stages."""

    def test_new_pipeline_asset_appears_in_scouting_at_identified_stage(self, tmp_path):
        """Asset created via POST /api/pipeline/assets shows up in scouting at 'identified'."""
        from ui.web.app import app
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "integration.db"))
        app.config["TESTING"] = True
        with patch("ui.web.app.ImagingDataStore", return_value=store):
            with app.test_client() as c:
                # Create via existing pipeline endpoint
                create_resp = c.post(
                    "/api/pipeline/assets",
                    json={
                        "source_type": "brownfield",
                        "asset": _make_brownfield_asset("Victoria Falls Solar"),
                    },
                )
                assert create_resp.status_code == 200, (
                    f"Pipeline create failed: {create_resp.get_json()}"
                )

                # Must appear in scouting items at 'identified' stage
                list_resp = c.get("/api/scouting/items?type=brownfield")
                assert list_resp.status_code == 200
                items = list_resp.get_json()["items"]
                assert len(items) == 1
                assert items[0]["scouting_stage"] == "identified"
        store.close()

    def test_move_asset_to_scored_then_verify_stage_filters(self, tmp_path):
        """Moving a brownfield asset to 'scored' updates list filters correctly."""
        from ui.web.app import app
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "integration.db"))
        app.config["TESTING"] = True
        with patch("ui.web.app.ImagingDataStore", return_value=store):
            with app.test_client() as c:
                # Create asset
                create_resp = c.post(
                    "/api/pipeline/assets",
                    json={
                        "source_type": "brownfield",
                        "asset": _make_brownfield_asset("Muchinga Wind"),
                    },
                )
                asset_id = create_resp.get_json()["asset"]["id"]

                # Move to 'scored'
                put_resp = c.put(
                    f"/api/scouting/items/{asset_id}/stage",
                    json={"type": "brownfield", "stage": "scored"},
                )
                assert put_resp.status_code == 200

                # GET with stage=scored must include it
                scored_resp = c.get("/api/scouting/items?type=brownfield&stage=scored")
                assert scored_resp.status_code == 200
                scored_items = scored_resp.get_json()["items"]
                assert any(item["id"] == asset_id for item in scored_items), (
                    "Asset must appear in stage=scored results after PUT"
                )

                # GET with stage=identified must NOT include it
                identified_resp = c.get(
                    "/api/scouting/items?type=brownfield&stage=identified"
                )
                identified_items = identified_resp.get_json()["items"]
                assert not any(item["id"] == asset_id for item in identified_items), (
                    "Asset must NOT appear in stage=identified results after moving to scored"
                )
        store.close()

    def test_full_kanban_lifecycle_brownfield(self, tmp_path):
        """Asset can advance through all five stages in order."""
        from ui.web.app import app
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "integration.db"))
        app.config["TESTING"] = True
        with patch("ui.web.app.ImagingDataStore", return_value=store):
            with app.test_client() as c:
                create_resp = c.post(
                    "/api/pipeline/assets",
                    json={
                        "source_type": "brownfield",
                        "asset": _make_brownfield_asset("Zambezi Hydro"),
                    },
                )
                asset_id = create_resp.get_json()["asset"]["id"]

                for stage in VALID_STAGES:
                    put_resp = c.put(
                        f"/api/scouting/items/{asset_id}/stage",
                        json={"type": "brownfield", "stage": stage},
                    )
                    assert put_resp.status_code == 200, (
                        f"Stage transition to '{stage}' failed with {put_resp.status_code}"
                    )
                    get_resp = c.get(f"/api/scouting/items?type=brownfield&stage={stage}")
                    items = get_resp.get_json()["items"]
                    assert any(item["id"] == asset_id for item in items), (
                        f"Asset not found in stage='{stage}' immediately after PUT"
                    )
        store.close()

    def test_greenfield_watchlist_site_appears_in_scouting_scored(self, tmp_path):
        """Greenfield site added via watchlist POST shows up in scouting at 'scored'."""
        from ui.web.app import app
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "integration.db"))
        app.config["TESTING"] = True
        with patch("ui.web.app.ImagingDataStore", return_value=store):
            with app.test_client() as c:
                create_resp = c.post(
                    "/api/scouting/watchlist",
                    json={"site": _make_greenfield_site("De Aar Solar")},
                )
                assert create_resp.status_code == 200

                list_resp = c.get("/api/scouting/items?type=greenfield")
                assert list_resp.status_code == 200
                items = list_resp.get_json()["items"]
                assert len(items) == 1
                assert items[0]["scouting_stage"] == "scored"
        store.close()

    def test_delete_item_removes_from_scouting_list(self, tmp_path):
        """Deleting an item via DELETE /api/scouting/items/<id> removes it from lists."""
        from ui.web.app import app
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "integration.db"))
        app.config["TESTING"] = True
        with patch("ui.web.app.ImagingDataStore", return_value=store):
            with app.test_client() as c:
                create_resp = c.post(
                    "/api/pipeline/assets",
                    json={
                        "source_type": "brownfield",
                        "asset": _make_brownfield_asset("Rooiberg Wind"),
                    },
                )
                asset_id = create_resp.get_json()["asset"]["id"]

                del_resp = c.delete(
                    f"/api/scouting/items/{asset_id}?type=brownfield"
                )
                assert del_resp.status_code == 200

                list_resp = c.get("/api/scouting/items?type=brownfield")
                items = list_resp.get_json()["items"]
                assert not any(item["id"] == asset_id for item in items), (
                    "Deleted item must not appear in subsequent list responses"
                )
        store.close()

    def test_multiple_types_are_isolated(self, tmp_path):
        """Brownfield and greenfield items must not appear in each other's lists."""
        from ui.web.app import app
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "integration.db"))
        store.upsert_pipeline_asset("brownfield", _make_brownfield_asset("Mosi oa Tunya Solar"))
        store.upsert_watchlist_site(_make_greenfield_site("Cuando Flats"))
        app.config["TESTING"] = True
        with patch("ui.web.app.ImagingDataStore", return_value=store):
            with app.test_client() as c:
                brownfield_resp = c.get("/api/scouting/items?type=brownfield")
                greenfield_resp = c.get("/api/scouting/items?type=greenfield")
        store.close()

        brownfield_ids = {item["id"] for item in brownfield_resp.get_json()["items"]}
        greenfield_ids = {item["id"] for item in greenfield_resp.get_json()["items"]}
        assert len(brownfield_ids) == 1
        assert len(greenfield_ids) == 1
        assert brownfield_ids.isdisjoint(greenfield_ids), (
            "Brownfield and greenfield lists must be mutually exclusive"
        )

    def test_unified_create_then_advance_through_kanban(self, tmp_path):
        """Create via POST /api/scouting/items, advance through stages, verify at each step."""
        from ui.web.app import app
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "integration.db"))
        app.config["TESTING"] = True
        with patch("ui.web.app.ImagingDataStore", return_value=store):
            with app.test_client() as c:
                # Create via unified endpoint
                create_resp = c.post(
                    "/api/scouting/items",
                    json={
                        "type": "brownfield",
                        "source_type": "generation",
                        "asset": _make_brownfield_asset("Cahora Bassa Extension"),
                    },
                )
                assert create_resp.status_code == 200, (
                    f"Unified create failed: {create_resp.get_json()}"
                )

                # Verify it appeared at 'identified'
                list_resp = c.get("/api/scouting/items?type=brownfield&stage=identified")
                assert list_resp.status_code == 200
                items = list_resp.get_json()["items"]
                assert len(items) == 1
                asset_id = items[0]["id"]

                # Advance to feasibility and verify
                put_resp = c.put(
                    f"/api/scouting/items/{asset_id}/stage",
                    json={"type": "brownfield", "stage": "feasibility"},
                )
                assert put_resp.status_code == 200
                assert put_resp.get_json()["item"]["scouting_stage"] == "feasibility"

                # Old stage must be empty
                old_resp = c.get("/api/scouting/items?type=brownfield&stage=identified")
                assert len(old_resp.get_json()["items"]) == 0

                # Delete via unified endpoint
                del_resp = c.delete(f"/api/scouting/items/{asset_id}?type=brownfield")
                assert del_resp.status_code == 200

                # Gone from all queries
                final_resp = c.get("/api/scouting/items?type=brownfield")
                assert len(final_resp.get_json()["items"]) == 0
        store.close()

    def test_api_returns_400_not_500_for_invalid_stage(self, tmp_path):
        """PUT with an invalid stage must return 400, not propagate as 500."""
        from ui.web.app import app
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "integration.db"))
        asset = store.upsert_pipeline_asset("brownfield", _make_brownfield_asset())
        app.config["TESTING"] = True
        with patch("ui.web.app.ImagingDataStore", return_value=store):
            with app.test_client() as c:
                resp = c.put(
                    f"/api/scouting/items/{asset['id']}/stage",
                    json={"type": "brownfield", "stage": "nonexistent_stage"},
                )
                assert resp.status_code == 400, (
                    f"Expected 400 for invalid stage, got {resp.status_code}"
                )
                # Verify stage was NOT changed
                check = c.get("/api/scouting/items?type=brownfield")
                items = check.get_json()["items"]
                assert items[0]["scouting_stage"] == "identified", (
                    "Invalid stage update must not mutate the record"
                )
        store.close()
