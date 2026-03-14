"""Tests for SEP-039: Greenfield site scouting."""

from __future__ import annotations

from unittest.mock import patch

import pytest


class TestGreenfieldScoring:
    def test_site_score_marks_unavailable_factors_unknown(self):
        """Unavailable inputs should remain explicitly unknown instead of synthetic scores."""
        from tools.imaging.site_score import score_site

        evaluation = score_site(
            lat=-25.7,
            lon=28.2,
            technology="solar",
            resource_summary={
                "solar": {
                    "annual": 5.68,
                    "unit": "kWh/m2/day",
                    "source": "NASA POWER",
                },
                "wind": None,
            },
            generation_assets=[],
            pipeline_assets=[],
        )

        factors = {factor["key"]: factor for factor in evaluation["factors"]}
        assert evaluation["technology"] == "solar"
        assert evaluation["overall_score"] is not None
        assert factors["resource_quality"]["status"] == "known"
        assert factors["policy_signal"]["status"] == "unknown"
        assert factors["brownfield_synergy"]["status"] == "unknown"


class TestGreenfieldWatchlistStore:
    def test_watchlist_store_round_trip(self, tmp_path):
        """Scouted sites should persist for compare/watchlist workflows."""
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "scouting.db"))
        created = store.upsert_watchlist_site(
            {
                "name": "Bushveld Ridge",
                "technology": "solar",
                "lat": -25.7,
                "lon": 28.2,
                "overall_score": 74.0,
                "score_label": "strong",
                "factors": [
                    {"key": "resource_quality", "status": "known", "score": 35},
                    {"key": "policy_signal", "status": "unknown", "score": None},
                ],
            }
        )

        items = store.list_watchlist_sites()
        compared = store.get_watchlist_sites_by_ids([created["id"]])
        assert len(items) == 1
        assert items[0]["name"] == "Bushveld Ridge"
        assert compared[0]["technology"] == "solar"

        store.delete_watchlist_site(created["id"])
        assert store.list_watchlist_sites() == []
        store.close()


class TestGreenfieldScoutingApi:
    @pytest.fixture
    def client(self):
        from ui.web.app import app

        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client

    def test_scouting_api_score_watchlist_and_compare(self, client, tmp_path):
        """Scouting API should score sites, persist watchlist entries, and compare them."""
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "scouting_api.db"))
        resource_summary = {
            "solar": {"annual": 5.68, "unit": "kWh/m2/day", "source": "NASA POWER"},
            "wind": {"annual": 4.55, "unit": "m/s", "source": "NASA POWER"},
        }
        with patch("ui.web.app.ImagingDataStore", return_value=store), \
             patch("ui.web.app.fetch_resource_summary", return_value=resource_summary):
            scored = client.post(
                "/api/scouting/score",
                json={
                    "name": "Bushveld Ridge",
                    "lat": -25.7,
                    "lon": 28.2,
                    "technology": "solar",
                },
            )
            assert scored.status_code == 200
            site = scored.get_json()["site"]
            factors = {factor["key"]: factor for factor in site["factors"]}
            assert factors["policy_signal"]["status"] == "unknown"

            saved = client.post("/api/scouting/watchlist", json={"site": site})
            assert saved.status_code == 200
            saved_site = saved.get_json()["site"]
            assert saved_site["name"] == "Bushveld Ridge"

            listed = client.get("/api/scouting/watchlist")
            assert listed.status_code == 200
            assert len(listed.get_json()["items"]) == 1

            compared = client.get(f"/api/scouting/compare?ids={saved_site['id']}")
            assert compared.status_code == 200
            assert compared.get_json()["items"][0]["id"] == saved_site["id"]
        store.close()

    def test_imaging_ui_includes_scouting_controls(self, client):
        """Imaging UI should expose click-to-score, watchlist, compare, and resource overlay controls."""
        resp = client.get("/")
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert "/api/scouting/score" in html
        assert "/api/scouting/watchlist" in html
        assert "imgScoutTechnology" in html
        assert "Scout Watchlist" in html
        assert "Solar Resource" in html
        assert "scoutCompareList" in html
