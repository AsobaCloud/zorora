"""Tests for scouting Score phase: score-preview, apply-score, pipeline scouting_score."""

from __future__ import annotations

import pathlib
import sys
from urllib.parse import quote
from unittest.mock import patch

import pytest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _make_imaging_store(tmp_path):
    from tools.imaging.store import ImagingDataStore

    return ImagingDataStore(db_path=str(tmp_path / "imaging.db"))


@pytest.fixture
def flask_client(tmp_path):
    pytest.importorskip("rich", reason="importing ui.web.app loads ui/__init__.py")
    with patch(
        "tools.imaging.store.ImagingDataStore._default_db_path",
        return_value=str(tmp_path / "app_imaging.db"),
    ):
        import importlib

        mod = importlib.import_module("ui.web.app")
        mod.app.config["TESTING"] = True
        with mod.app.test_client() as client:
            yield client, tmp_path


class TestPipelineScoutingScoreStore:
    def test_save_pipeline_scouting_score_denormalizes_list(self, tmp_path):
        store = _make_imaging_store(tmp_path)
        asset = {
            "type": "Feature",
            "properties": {
                "site_id": "bess-unit-test",
                "name": "Test BESS",
                "technology": "Storage",
                "capacity_mw": 10,
                "country": "ZA",
            },
            "geometry": {"type": "Point", "coordinates": [28.0, -25.0]},
        }
        saved = store.upsert_pipeline_asset("bess", asset)
        aid = saved["id"]
        snapshot = {
            "overall_score": 42.0,
            "score_label": "moderate",
            "factors": [
                {
                    "key": "k1",
                    "label": "Factor one",
                    "status": "known",
                    "score": 5,
                    "max_score": 10,
                    "detail": "test",
                }
            ],
            "resource_summary": {"x": 1},
        }
        store.save_pipeline_scouting_score(aid, snapshot)
        items = store.list_scouting_items("bess")
        row = next((i for i in items if i["id"] == aid), None)
        store.close()
        assert row is not None
        assert row["overall_score"] == 42.0
        assert row["score_label"] == "moderate"
        assert len(row["factors"]) == 1
        assert row["factors"][0]["key"] == "k1"

    def test_upsert_watchlist_preserves_scouting_stage(self, tmp_path):
        store = _make_imaging_store(tmp_path)
        store.upsert_watchlist_site(
            {
                "id": "gf:test",
                "name": "Site A",
                "technology": "solar",
                "lat": -25.0,
                "lon": 28.0,
                "country": "ZA",
                "scouting_stage": "identified",
            }
        )
        store.upsert_watchlist_site(
            {
                "id": "gf:test",
                "name": "Site A",
                "technology": "solar",
                "lat": -25.0,
                "lon": 28.0,
                "country": "ZA",
                "overall_score": 50.0,
                "score_label": "moderate",
                "factors": [],
                "resource_summary": {},
                "notes": "n",
                "scouting_stage": "scored",
            }
        )
        row = store.get_watchlist_site("gf:test")
        store.close()
        assert row["scouting_stage"] == "scored"
        assert row["overall_score"] == 50.0


class TestScoutingScoreApi:
    def test_score_preview_greenfield_merges_id_and_notes(self, flask_client):
        from tools.imaging.store import ImagingDataStore

        client, tmp_path = flask_client
        db_path = tmp_path / "app_imaging.db"
        store = ImagingDataStore(db_path=str(db_path))
        store.upsert_watchlist_site(
            {
                "id": "gf:api",
                "name": "API Site",
                "technology": "solar",
                "lat": -25.5,
                "lon": 28.5,
                "country": "ZA",
                "notes": "keep me",
                "scouting_stage": "identified",
            }
        )
        store.close()

        solar_summary = {
            "solar": {
                "annual": 5.5,
                "unit": "kWh/kWp/day",
                "source": "test",
            }
        }
        with patch(
            "ui.web.app.fetch_resource_summary",
            return_value=solar_summary,
        ):
            resp = client.post(
                "/api/scouting/items/gf%3Aapi/score-preview",
                json={"type": "greenfield"},
            )
        assert resp.status_code == 200, resp.get_data(as_text=True)
        data = resp.get_json()
        assert data["site"]["id"] == "gf:api"
        assert data["site"]["notes"] == "keep me"
        assert data["site"]["factors"]
        assert "overall_score" in data["site"]

    def test_apply_score_greenfield_sets_scored(self, flask_client):
        client, tmp_path = flask_client
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "app_imaging.db"))
        store.upsert_watchlist_site(
            {
                "id": "gf:apply",
                "name": "Apply Site",
                "technology": "solar",
                "lat": -26.0,
                "lon": 27.0,
                "country": "NA",
                "scouting_stage": "identified",
            }
        )
        store.close()

        site = {
            "id": "gf:apply",
            "name": "Apply Site",
            "technology": "solar",
            "lat": -26.0,
            "lon": 27.0,
            "country": "NA",
            "overall_score": 60.0,
            "score_label": "moderate",
            "factors": [
                {
                    "key": "resource_quality",
                    "label": "Resource quality",
                    "status": "known",
                    "score": 20,
                    "max_score": 40,
                }
            ],
            "resource_summary": {},
            "notes": "",
        }
        resp = client.post(
            "/api/scouting/items/gf%3Aapply/apply-score",
            json={"type": "greenfield", "site": site},
        )
        assert resp.status_code == 200, resp.get_data(as_text=True)
        store = ImagingDataStore(db_path=str(tmp_path / "app_imaging.db"))
        row = store.get_watchlist_site("gf:apply")
        store.close()
        assert row["scouting_stage"] == "scored"
        assert row["overall_score"] == 60.0

    def test_score_preview_bess_patches_score_bess_site(self, flask_client):
        client, tmp_path = flask_client
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "app_imaging.db"))
        asset = {
            "type": "Feature",
            "properties": {
                "site_id": "bess-api",
                "name": "BESS X",
                "technology": "Storage",
                "capacity_mw": 5,
                "country": "ZA",
            },
            "geometry": {"type": "Point", "coordinates": [29.0, -26.0]},
        }
        saved = store.upsert_pipeline_asset("bess", asset)
        aid = saved["id"]
        store.update_scouting_stage("bess", aid, "identified")
        store.close()

        fake = {
            "name": "BESS X",
            "technology": "bess",
            "lat": -26.0,
            "lon": 29.0,
            "country": "ZA",
            "overall_score": 70.0,
            "score_label": "strong",
            "factors": [{"key": "z", "label": "Z", "status": "known", "score": 7, "max_score": 10}],
            "resource_summary": {},
        }
        with patch("ui.web.app.score_bess_site", return_value=fake):
            resp = client.post(
                f"/api/scouting/items/{quote(aid, safe='')}/score-preview",
                json={"type": "bess"},
            )

        assert resp.status_code == 200, resp.get_data(as_text=True)
        body = resp.get_json()
        assert body["site"]["id"] == aid
        assert body["site"]["overall_score"] == 70.0
