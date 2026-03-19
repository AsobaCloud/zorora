"""Tests for SEP-043: Rename Imaging to Discovery + Grid Infrastructure Layers."""

from __future__ import annotations

from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


# ---------------------------------------------------------------------------
# Grid metrics unit tests
# ---------------------------------------------------------------------------

class TestSupplyAreaMapping:
    def test_covers_all_gcca_supply_areas(self):
        from tools.imaging.gcca_client import load_supply_areas
        from tools.imaging.grid_metrics import SUPPLY_AREA_DAM_NODE

        gpkg = str(DATA_DIR / "GCCA 2025 GIS" / "AREAS_GCCA2025.gpkg")
        fc = load_supply_areas(gpkg)
        gcca_areas = {f["properties"]["supplyarea"] for f in fc["features"]}
        for area in gcca_areas:
            assert area in SUPPLY_AREA_DAM_NODE, (
                f"Supply area '{area}' from GCCA has no DAM node mapping"
            )

    def test_all_nodes_are_rsan_or_rsas(self):
        from tools.imaging.grid_metrics import SUPPLY_AREA_DAM_NODE

        for area, node in SUPPLY_AREA_DAM_NODE.items():
            assert node in ("rsan", "rsas"), (
                f"Supply area '{area}' mapped to invalid node '{node}'"
            )


class TestPeakClassification:
    def test_peak_hours(self):
        from tools.imaging.grid_metrics import classify_peak_hours

        assert classify_peak_hours(6) == "peak"
        assert classify_peak_hours(7) == "peak"
        assert classify_peak_hours(8) == "peak"
        assert classify_peak_hours(17) == "peak"
        assert classify_peak_hours(18) == "peak"
        assert classify_peak_hours(19) == "peak"
        assert classify_peak_hours(20) == "peak"

    def test_offpeak_hours(self):
        from tools.imaging.grid_metrics import classify_peak_hours

        assert classify_peak_hours(0) == "offpeak"
        assert classify_peak_hours(5) == "offpeak"
        assert classify_peak_hours(9) == "offpeak"
        assert classify_peak_hours(12) == "offpeak"
        assert classify_peak_hours(16) == "offpeak"
        assert classify_peak_hours(21) == "offpeak"
        assert classify_peak_hours(23) == "offpeak"


class TestNodePriceStats:
    def test_compute_with_sample_data(self):
        from tools.imaging.grid_metrics import compute_node_price_stats

        dam_data = {
            "rsan": {
                "usd": [
                    ("2025-01-01 06:00", 50.0),  # peak
                    ("2025-01-01 07:00", 60.0),  # peak
                    ("2025-01-01 12:00", 30.0),  # offpeak
                    ("2025-01-01 13:00", 20.0),  # offpeak
                ],
            },
        }
        stats = compute_node_price_stats(dam_data)
        assert "rsan" in stats
        assert abs(stats["rsan"]["avg_peak_usd"] - 55.0) < 0.01
        assert abs(stats["rsan"]["avg_offpeak_usd"] - 25.0) < 0.01
        assert abs(stats["rsan"]["arbitrage_spread_usd"] - 30.0) < 0.01
        assert abs(stats["rsan"]["avg_dam_price_usd"] - 40.0) < 0.01


class TestPointInPolygon:
    def test_inside_triangle(self):
        from tools.imaging.grid_metrics import point_in_polygon

        # Triangle: (0,0), (10,0), (5,10)
        ring = [[0, 0], [10, 0], [5, 10], [0, 0]]
        assert point_in_polygon(3, 5, ring) is True

    def test_outside_triangle(self):
        from tools.imaging.grid_metrics import point_in_polygon

        ring = [[0, 0], [10, 0], [5, 10], [0, 0]]
        assert point_in_polygon(20, 20, ring) is False


class TestComputeZoneMetrics:
    def test_structure_with_real_data(self):
        from tools.imaging.gcca_client import load_mts_zones
        from tools.imaging.grid_metrics import compute_zone_metrics
        from tools.market.sapp_client import parse_all_dam_files

        gpkg = str(DATA_DIR / "GCCA 2025 GIS" / "AREAS_GCCA2025.gpkg")
        mts_zones = load_mts_zones(gpkg)
        dam_data = parse_all_dam_files(str(DATA_DIR))

        metrics = compute_zone_metrics(mts_zones, dam_data, [])
        assert len(metrics) == 159, f"Expected 159 zones, got {len(metrics)}"

        # Verify Acacia substation has expected keys
        acacia = metrics.get("Acacia")
        assert acacia is not None, "Acacia substation missing from metrics"
        assert "dam_node" in acacia
        assert "avg_peak_usd" in acacia
        assert "avg_offpeak_usd" in acacia
        assert "arbitrage_spread_usd" in acacia
        assert "re_asset_count" in acacia

        # Acacia is in Western Cape → RSAS
        assert acacia["dam_node"] == "rsas"
        # Prices should be positive
        assert acacia["avg_peak_usd"] > 0
        assert acacia["avg_offpeak_usd"] > 0
        assert acacia["arbitrage_spread_usd"] > 0


# ---------------------------------------------------------------------------
# UI rename test
# ---------------------------------------------------------------------------

class TestDiscoveryRename:
    def test_nav_button_says_discovery(self):
        html_path = Path(__file__).resolve().parent.parent / "ui" / "web" / "templates" / "index.html"
        html = html_path.read_text()
        # The data-mode="imaging" button should have text "Discovery"
        import re
        # Find the imaging mode button and check its text
        match = re.search(
            r'data-mode="imaging"[^>]*>([^<]+)<',
            html,
        )
        assert match is not None, "Could not find data-mode='imaging' button"
        button_text = match.group(1).strip()
        assert button_text == "Discovery", (
            f"Expected 'Discovery', got '{button_text}'"
        )


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------

class TestDiscoveryEndpoints:
    def _get_app(self):
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from ui.web.app import app
        app.config["TESTING"] = True
        return app

    def test_mts_zones_endpoint(self):
        app = self._get_app()
        with app.test_client() as client:
            resp = client.get("/api/discovery/gcca/mts-zones")
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["type"] == "FeatureCollection"
            assert len(data["features"]) == 159
            # Each feature should have dam_node annotation
            for f in data["features"][:5]:
                assert "dam_node" in f["properties"]
                assert f["properties"]["dam_node"] in ("rsan", "rsas")

    def test_supply_areas_endpoint(self):
        app = self._get_app()
        with app.test_client() as client:
            resp = client.get("/api/discovery/gcca/supply-areas")
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["type"] == "FeatureCollection"
            assert len(data["features"]) == 10
            for f in data["features"]:
                assert "dam_node" in f["properties"]

    def test_zone_metrics_endpoint(self):
        app = self._get_app()
        with app.test_client() as client:
            resp = client.get("/api/discovery/zone-metrics")
            assert resp.status_code == 200
            data = resp.get_json()
            assert "Acacia" in data
            acacia = data["Acacia"]
            assert acacia["dam_node"] in ("rsan", "rsas")
            assert acacia["avg_peak_usd"] > 0
            assert acacia["arbitrage_spread_usd"] > 0

    def test_single_zone_metrics_endpoint(self):
        app = self._get_app()
        with app.test_client() as client:
            resp = client.get("/api/discovery/zone-metrics/Acacia")
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["dam_node"] in ("rsan", "rsas")
            assert "avg_peak_usd" in data

    def test_substations_endpoint(self):
        app = self._get_app()
        with app.test_client() as client:
            resp = client.get("/api/discovery/gcca/substations")
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["type"] == "FeatureCollection"
            assert len(data["features"]) > 50
            for f in data["features"][:5]:
                assert f["geometry"]["type"] == "Point"
                assert "dam_node" in f["properties"]
                assert f["properties"]["dam_node"] in ("rsan", "rsas")
            import json
            response_size = len(json.dumps(data))
            assert response_size < 100_000, (
                f"Response is {response_size} bytes — should be <100KB"
            )


class TestSubstationPoints:

    def test_load_substations_returns_features(self):
        from tools.imaging.gcca_client import load_substations

        fc = load_substations()
        assert fc["type"] == "FeatureCollection"
        assert len(fc["features"]) > 50

    def test_substation_has_point_geometry(self):
        from tools.imaging.gcca_client import load_substations

        fc = load_substations()
        for f in fc["features"][:10]:
            assert f["geometry"]["type"] == "Point"
            coords = f["geometry"]["coordinates"]
            assert len(coords) == 2
            lon, lat = coords
            assert 14 < lon < 35, f"Longitude {lon} outside SA range"
            assert -36 < lat < -20, f"Latitude {lat} outside SA range"

    def test_substation_has_transformer_data(self):
        from tools.imaging.gcca_client import load_substations

        fc = load_substations()
        has_voltage = 0
        for f in fc["features"]:
            props = f["properties"]
            assert "substation" in props
            assert "supply_area" in props
            if props.get("transformer_voltage") or props.get("transformers"):
                has_voltage += 1
        assert has_voltage > len(fc["features"]) * 0.5

    def test_deduplication_by_coordinates(self):
        from tools.imaging.gcca_client import load_substations

        fc = load_substations()
        coord_set = set()
        for f in fc["features"]:
            coords = tuple(f["geometry"]["coordinates"])
            assert coords not in coord_set, (
                f"Duplicate coordinates {coords} — deduplication failed"
            )
            coord_set.add(coords)
