"""Tests for SEP-038: Brownfield acquisition pipeline."""

from __future__ import annotations

from unittest.mock import patch

import pytest


SAMPLE_GENERATION_FEATURE = {
    "type": "Feature",
    "geometry": {"type": "Point", "coordinates": [22.5, -27.1]},
    "properties": {
        "site_id": "solar:L1001",
        "gem_location_id": "L1001",
        "name": "Kathu Solar Park",
        "technology": "solar",
        "capacity_mw": 150.0,
        "status": "operating",
        "operator": "ACME Operations",
        "owner": "ACME Owner",
        "country": "South Africa",
        "location_accuracy": "exact",
        "source_sheet": "Solar",
        "wiki_url": "https://www.gem.wiki/Kathu_Solar_Park",
    },
}


class TestBrownfieldPipelineStore:
    def test_pipeline_store_round_trip(self, tmp_path):
        """Pipeline assets should persist, dedupe by source asset, and list cleanly."""
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "pipeline.db"))
        created = store.upsert_pipeline_asset(
            source_type="generation_asset",
            asset=SAMPLE_GENERATION_FEATURE,
        )
        store.upsert_pipeline_asset(
            source_type="generation_asset",
            asset=SAMPLE_GENERATION_FEATURE,
        )

        items = store.list_pipeline_assets()
        assert created["source_type"] == "generation_asset"
        assert created["source_asset_id"] == "solar:L1001"
        assert len(items) == 1
        assert items[0]["asset_name"] == "Kathu Solar Park"
        assert items[0]["research_query"].lower().startswith("brownfield acquisition")

        store.delete_pipeline_asset(created["id"])
        assert store.list_pipeline_assets() == []
        store.close()


class TestBrownfieldPipelineApi:
    @pytest.fixture
    def client(self):
        from ui.web.app import app

        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client

    def test_pipeline_api_round_trip(self, client, tmp_path):
        """Pipeline API should persist generation assets and support deletion."""
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "pipeline_api.db"))
        with patch("ui.web.app.ImagingDataStore", return_value=store):
            created = client.post(
                "/api/pipeline/assets",
                json={"source_type": "generation_asset", "asset": SAMPLE_GENERATION_FEATURE},
            )
            assert created.status_code == 200
            payload = created.get_json()
            assert payload["asset"]["source_asset_id"] == "solar:L1001"

            listed = client.get("/api/pipeline/assets")
            assert listed.status_code == 200
            items = listed.get_json()["items"]
            assert len(items) == 1
            assert items[0]["asset_name"] == "Kathu Solar Park"

            deleted = client.delete(f"/api/pipeline/assets/{payload['asset']['id']}")
            assert deleted.status_code == 200
            assert deleted.get_json()["status"] == "deleted"

            assert client.get("/api/pipeline/assets").get_json()["items"] == []
        store.close()

    def test_imaging_ui_includes_pipeline_controls(self, client):
        """Imaging UI should expose research and pipeline actions for brownfield work."""
        resp = client.get("/")
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert "/api/pipeline/assets" in html
        assert "prefillBrownfieldResearch" in html
        assert "addGenerationToPipeline" in html
        assert "brownfieldPipelineList" in html
        assert "Brownfield Pipeline" in html
