"""Tests for SEP-034: Imaging tab — OSINT mineral intelligence map."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Sample data fixtures
# ---------------------------------------------------------------------------

SAMPLE_MRDS_GEOJSON = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [28.5, -25.7]},
            "properties": {
                "dep_id": "10001",
                "name": "Bushveld Complex North",
                "dep_type": "Igneous",
                "commod1": "Platinum",
                "commod2": "Chromium",
                "commod3": "",
                "dev_stat": "Producer",
                "work_type": "Open pit",
                "country": "South Africa",
                "latitude": -25.7,
                "longitude": 28.5,
            },
        },
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [30.1, -20.3]},
            "properties": {
                "dep_id": "10002",
                "name": "Dorowa Carbonatite",
                "dep_type": "Carbonatite",
                "commod1": "Rare earths",
                "commod2": "",
                "commod3": "",
                "dev_stat": "Occurrence",
                "work_type": "Unknown",
                "country": "Zimbabwe",
                "latitude": -20.3,
                "longitude": 30.1,
            },
        },
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [29.0, -26.2]},
            "properties": {
                "dep_id": "10003",
                "name": "Witwatersrand Basin",
                "dep_type": "Sedimentary",
                "commod1": "Gold",
                "commod2": "",
                "commod3": "",
                "dev_stat": "Past producer",
                "work_type": "Underground",
                "country": "South Africa",
                "latitude": -26.2,
                "longitude": 29.0,
            },
        },
    ],
}

SAMPLE_CONCESSION_CSV = (
    "mine_name,operator,mineral_type,status,latitude,longitude\n"
    "Mogalakwena,Anglo American Platinum,PGM,Operating,-23.68,28.73\n"
    "Sishen,Kumba Iron Ore,Iron Ore,Operating,-27.73,22.98\n"
)


# ===========================================================================
# 1. MRDS client tests
# ===========================================================================


class TestMRDSClient:
    """Tests for tools/imaging/mrds_client.py."""

    @patch("tools.imaging.mrds_client.requests.get")
    def test_mrds_client_parses_geojson(self, mock_get):
        """Verify fetch_deposits returns FeatureCollection with expected properties."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = SAMPLE_MRDS_GEOJSON
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        from tools.imaging.mrds_client import fetch_deposits

        result = fetch_deposits()
        assert result["type"] == "FeatureCollection"
        assert len(result["features"]) == 3
        props = result["features"][0]["properties"]
        assert "name" in props
        assert "dep_type" in props
        assert "commod1" in props
        assert "dev_stat" in props
        assert "country" in props

    @patch("tools.imaging.mrds_client.requests.get")
    def test_mrds_client_filters_by_commodity(self, mock_get):
        """Verify commodity filter is passed in WFS request params."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"type": "FeatureCollection", "features": []}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        from tools.imaging.mrds_client import fetch_deposits

        fetch_deposits(commodity="Rare earths")
        call_kwargs = mock_get.call_args
        # Commodity filter should appear in params or URL
        call_str = str(call_kwargs)
        assert "Rare earths" in call_str


# ===========================================================================
# 2. Concessions client tests
# ===========================================================================


class TestConcessionsClient:
    """Tests for tools/imaging/concessions_client.py."""

    @patch("tools.imaging.concessions_client.requests.get")
    def test_concessions_client_parses_response(self, mock_get):
        """Mock openAFRICA CSV and verify GeoJSON output."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = SAMPLE_CONCESSION_CSV
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        from tools.imaging.concessions_client import fetch_concessions_sa

        result = fetch_concessions_sa()
        assert result["type"] == "FeatureCollection"
        assert len(result["features"]) == 2
        props = result["features"][0]["properties"]
        assert props["name"] == "Mogalakwena"
        assert props["operator"] == "Anglo American Platinum"
        assert props["mineral_type"] == "PGM"
        assert props["country"] == "South Africa"


# ===========================================================================
# 3. Viability scorer tests
# ===========================================================================


class TestViabilityScorer:
    """Tests for tools/imaging/viability.py."""

    def _make_feature(self, commod1="Gold", dev_stat="Occurrence",
                      work_type="Unknown", country="South Africa"):
        return {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [28.5, -25.7]},
            "properties": {
                "commod1": commod1,
                "commod2": "",
                "commod3": "",
                "dev_stat": dev_stat,
                "work_type": work_type,
                "country": country,
            },
        }

    def test_viability_score_ree_producer_high_power(self):
        """REE + Producer + open pit + SA should score high tier."""
        from tools.imaging.viability import score_deposit

        feature = self._make_feature(
            commod1="Rare earths", dev_stat="Producer",
            work_type="Open pit", country="South Africa",
        )
        result = score_deposit(feature, viirs_radiance=15.0)
        assert result["score"] >= 65, f"Expected high tier, got {result['score']}"
        assert result["tier"] == "high"
        assert result["commodity_pts"] >= 18
        assert result["status_pts"] == 25
        assert result["processing_pts"] == 15
        assert result["power_pts"] == 20
        assert result["regulatory_pts"] == 10

    def test_viability_score_occurrence_no_power(self):
        """Unknown mineral + Occurrence + underground + no VIIRS + ZW = low tier."""
        from tools.imaging.viability import score_deposit

        feature = self._make_feature(
            commod1="Other", dev_stat="Occurrence",
            work_type="Underground", country="Zimbabwe",
        )
        result = score_deposit(feature, viirs_radiance=0.0)
        assert result["score"] <= 34, f"Expected low tier, got {result['score']}"
        assert result["tier"] == "low"

    def test_viability_price_signal_integration(self):
        """Verify price signal bonus uses market data."""
        from tools.imaging.viability import score_deposit

        feature = self._make_feature(commod1="Platinum", dev_stat="Producer",
                                     work_type="Open pit")
        # With positive price trend
        result_up = score_deposit(feature, viirs_radiance=5.0,
                                  price_trends={"Platinum": 2.5})
        # Without price data
        result_none = score_deposit(feature, viirs_radiance=5.0,
                                    price_trends={})
        assert result_up["price_signal"] == 5
        assert result_none["price_signal"] == 0
        assert result_up["score"] > result_none["score"]

    def test_viability_score_all_components_independent(self):
        """Each of the 5 components should be scored independently."""
        from tools.imaging.viability import score_deposit

        base = self._make_feature(commod1="Gold", dev_stat="Prospect",
                                  work_type="Open pit", country="South Africa")
        result = score_deposit(base, viirs_radiance=3.0)
        # Verify all component keys present
        for key in ["commodity_pts", "price_signal", "status_pts",
                     "processing_pts", "power_pts", "regulatory_pts"]:
            assert key in result, f"Missing component: {key}"
        # Verify score equals sum of components
        component_sum = (
            result["commodity_pts"] + result["price_signal"] +
            result["status_pts"] + result["processing_pts"] +
            result["power_pts"] + result["regulatory_pts"]
        )
        assert result["score"] == component_sum


# ===========================================================================
# 4. Imaging store tests
# ===========================================================================


class TestImagingStore:
    """Tests for tools/imaging/store.py."""

    def test_imaging_store_upsert_and_query(self, tmp_path):
        """Round-trip: upsert GeoJSON features, query back."""
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "test.db"))
        store.upsert_deposits(SAMPLE_MRDS_GEOJSON["features"])
        result = store.get_deposits()
        assert result["type"] == "FeatureCollection"
        assert len(result["features"]) == 3
        store.close()

    def test_imaging_store_staleness(self, tmp_path):
        """Insert old fetch timestamp, verify staleness > threshold."""
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "test.db"))
        store.upsert_deposits(SAMPLE_MRDS_GEOJSON["features"])
        # Manually backdate the fetch timestamp
        store.conn.execute(
            "UPDATE fetch_metadata SET last_fetched_at = '2020-01-01T00:00:00+00:00' "
            "WHERE layer = 'deposits'"
        )
        store.conn.commit()
        staleness = store.get_staleness("deposits")
        assert staleness > 1000, f"Expected stale, got {staleness}h"
        store.close()

    def test_imaging_store_country_filter(self, tmp_path):
        """Filter deposits by country returns correct subset."""
        from tools.imaging.store import ImagingDataStore

        store = ImagingDataStore(db_path=str(tmp_path / "test.db"))
        store.upsert_deposits(SAMPLE_MRDS_GEOJSON["features"])
        result = store.get_deposits(country="Zimbabwe")
        assert len(result["features"]) == 1
        assert result["features"][0]["properties"]["country"] == "Zimbabwe"
        store.close()


# ===========================================================================
# 5. API endpoint tests
# ===========================================================================


class TestImagingEndpoints:
    """Tests for Flask imaging API endpoints."""

    @pytest.fixture
    def client(self, tmp_path):
        """Create Flask test client with temp imaging DB."""
        with patch("tools.imaging.store.ImagingDataStore._default_db_path",
                    return_value=str(tmp_path / "test.db")):
            from ui.web.app import app
            app.config["TESTING"] = True
            with app.test_client() as client:
                yield client

    def test_deposits_api_endpoint(self, client, tmp_path):
        """GET /api/imaging/deposits returns 200 with GeoJSON structure."""
        with patch("ui.web.app.ImagingDataStore") as MockStore:
            mock_instance = MagicMock()
            mock_instance.get_deposits.return_value = SAMPLE_MRDS_GEOJSON
            mock_instance.get_staleness.return_value = 0.5
            MockStore.return_value = mock_instance

            resp = client.get("/api/imaging/deposits")
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["type"] == "FeatureCollection"
            # Viability scores should be injected
            for feat in data["features"]:
                assert "viability" in feat["properties"]

    def test_concessions_api_endpoint(self, client, tmp_path):
        """GET /api/imaging/concessions returns 200 with GeoJSON."""
        with patch("ui.web.app.ImagingDataStore") as MockStore:
            mock_instance = MagicMock()
            mock_instance.get_concessions.return_value = {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [28.73, -23.68]},
                        "properties": {
                            "name": "Mogalakwena",
                            "operator": "Anglo American Platinum",
                            "mineral_type": "PGM",
                            "status": "Operating",
                            "country": "South Africa",
                        },
                    }
                ],
            }
            mock_instance.get_staleness.return_value = 0.5
            MockStore.return_value = mock_instance

            resp = client.get("/api/imaging/concessions")
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["type"] == "FeatureCollection"
            assert len(data["features"]) >= 1
