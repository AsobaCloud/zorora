"""Tests for SEP-042: SAPP & Eskom Data Parsers."""

import os
import tempfile
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parent.parent / "data"


# ---------------------------------------------------------------------------
# SAPP DAM client tests
# ---------------------------------------------------------------------------

class TestSAPPClient:
    """Tests for tools/market/sapp_client.py."""

    def _rsan_path(self):
        return str(DATA_DIR / "DAM_RSAN_01-Jan-2025_To_31-Mar-2026_152.xlsx")

    def _rsas_path(self):
        return str(DATA_DIR / "DAM_RSAS_01-Jan-2025_To_31-Mar-2026_140.xlsx")

    def _zim_path(self):
        return str(DATA_DIR / "DAM_ZIM_01-Jan-2025_To_31-Mar-2026_109.xlsx")

    def test_parse_rsan_usd(self):
        from tools.market.sapp_client import fetch_observations

        obs = fetch_observations(self._rsan_path(), currency="usd")
        assert len(obs) > 10000, f"Expected >10000 rows, got {len(obs)}"
        # Each observation is (datetime_str, float)
        dt, val = obs[0]
        assert isinstance(dt, str)
        assert isinstance(val, float)
        # First row: 2025/01/01, 00-01, 31.85 USD
        assert dt == "2025-01-01 00:00"
        assert val == 31.85

    def test_parse_rsan_zar(self):
        from tools.market.sapp_client import fetch_observations

        obs = fetch_observations(self._rsan_path(), currency="zar")
        assert len(obs) > 10000
        dt, val = obs[0]
        assert dt == "2025-01-01 00:00"
        assert val == 554.06

    def test_parse_rsas(self):
        from tools.market.sapp_client import fetch_observations

        obs = fetch_observations(self._rsas_path(), currency="usd")
        assert len(obs) > 10000
        dt, _ = obs[0]
        assert dt == "2025-01-01 00:00"

    def test_parse_zim(self):
        from tools.market.sapp_client import fetch_observations

        obs = fetch_observations(self._zim_path(), currency="usd")
        assert len(obs) > 10000
        dt, val = obs[0]
        assert dt == "2025-01-01 00:00"
        assert val == 31.85

    def test_datetime_format(self):
        from tools.market.sapp_client import fetch_observations

        obs = fetch_observations(self._rsan_path(), currency="usd")
        for dt, _ in obs[:48]:
            # Format: "YYYY-MM-DD HH:00"
            assert len(dt) == 16, f"Bad datetime format: {dt}"
            assert dt[4] == "-" and dt[7] == "-" and dt[10] == " " and dt[13] == ":"

    def test_parse_all_dam_files(self):
        from tools.market.sapp_client import parse_all_dam_files

        result = parse_all_dam_files(str(DATA_DIR))
        assert "rsan" in result
        assert "rsas" in result
        assert "zim" in result
        for node in result.values():
            assert "usd" in node
            assert "zar" in node
            assert len(node["usd"]) > 10000

    def test_nonexistent_file(self):
        from tools.market.sapp_client import fetch_observations

        obs = fetch_observations("/nonexistent/file.xlsx", currency="usd")
        assert obs == []


# ---------------------------------------------------------------------------
# Eskom demand tests
# ---------------------------------------------------------------------------

class TestEskomDemand:
    """Tests for Eskom demand CSV parsing."""

    def _path(self):
        return str(DATA_DIR / "System_hourly_actual_and_forecasted_demand.csv")

    def test_parse_demand_values(self):
        from tools.market.eskom_client import fetch_demand_observations

        result = fetch_demand_observations(self._path())
        assert "residual_demand" in result
        assert "rsa_contracted_demand" in result
        assert len(result["residual_demand"]) > 100
        # Verify first row against known data:
        # 2026-03-11 00:00, Residual Demand = 18663.896
        dt, val = result["residual_demand"][0]
        assert dt == "2026-03-11 00:00"
        assert abs(val - 18663.896) < 1.0, f"Expected ~18663.896, got {val}"
        # RSA Contracted Demand first row = 20187.914
        dt2, val2 = result["rsa_contracted_demand"][0]
        assert dt2 == "2026-03-11 00:00"
        assert abs(val2 - 20187.914) < 1.0, f"Expected ~20187.914, got {val2}"

    def test_sparse_columns_have_different_counts(self):
        from tools.market.eskom_client import fetch_demand_observations

        result = fetch_demand_observations(self._path())
        # The CSV has 336 rows total. Demand columns are populated for 144
        # (actuals only), forecast columns for 192 (forecast extends beyond).
        # Each column should only contain entries where data exists.
        demand_count = len(result["residual_demand"])
        forecast_count = len(result.get("residual_forecast", []))
        assert demand_count == 144, f"Expected 144 demand rows, got {demand_count}"
        assert forecast_count == 192, f"Expected 192 forecast rows, got {forecast_count}"
        assert demand_count != forecast_count, (
            "Demand and forecast should have different counts proving "
            "empty cells are skipped rather than stored as zeros"
        )
        # No None values in parsed data
        for dt, val in result.get("residual_forecast", []):
            assert isinstance(val, float)


# ---------------------------------------------------------------------------
# Eskom generation tests
# ---------------------------------------------------------------------------

class TestEskomGeneration:
    """Tests for Eskom RE generation CSV parsing."""

    def _path(self):
        return str(DATA_DIR / "Hourly_Generation.csv")

    def test_parse_generation_values(self):
        from tools.market.eskom_client import fetch_generation_observations

        result = fetch_generation_observations(self._path())
        assert "wind" in result
        assert "pv" in result
        assert "csp" in result
        assert "other_re" in result
        # Verify first row against known data:
        # 2026-02-01 00:00, Wind=1375.799, PV=0, CSP=33.299, Other RE=42.181
        dt, wind_val = result["wind"][0]
        assert dt == "2026-02-01 00:00"
        assert abs(wind_val - 1375.799) < 0.01, f"Expected ~1375.799, got {wind_val}"
        _, pv_val = result["pv"][0]
        assert pv_val == 0.0
        _, csp_val = result["csp"][0]
        assert abs(csp_val - 33.299) < 0.01

    def test_row_count_matches_file(self):
        from tools.market.eskom_client import fetch_generation_observations

        result = fetch_generation_observations(self._path())
        # File has ~1416 data rows (Feb 1 through mid-Mar hourly)
        assert len(result["wind"]) > 1000, f"Expected >1000 rows, got {len(result['wind'])}"
        # All columns should have same number of non-empty rows
        # (PV has zeros at night but they're still valid values, not empty)
        assert len(result["wind"]) == len(result["pv"])


# ---------------------------------------------------------------------------
# Eskom station build-up tests
# ---------------------------------------------------------------------------

class TestEskomStationBuildUp:
    """Tests for Eskom station build-up CSV parsing."""

    def _path(self):
        return str(DATA_DIR / "Station_Build_Up.csv")

    def test_parse_station_buildup_values(self):
        from tools.market.eskom_client import fetch_station_buildup_observations

        result = fetch_station_buildup_observations(self._path())
        assert len(result) >= 15, f"Expected >=15 columns, got {len(result)}"
        # Verify first row against known data:
        # 2026-03-10 00:00, Thermal_Generation=17049.279, Nuclear=1888.155, Wind=1556.182
        dt, thermal = result["thermal_generation"][0]
        assert dt == "2026-03-10 00:00"
        assert abs(thermal - 17049.279) < 1.0, f"Expected ~17049.279, got {thermal}"
        _, nuclear = result["nuclear_generation"][0]
        assert abs(nuclear - 1888.155) < 0.01, f"Expected ~1888.155, got {nuclear}"
        _, wind = result["wind"][0]
        assert abs(wind - 1556.182) < 0.01, f"Expected ~1556.182, got {wind}"

    def test_expected_columns(self):
        from tools.market.eskom_client import fetch_station_buildup_observations

        result = fetch_station_buildup_observations(self._path())
        expected = [
            "thermal_gen_excl_pumping_and_sco",
            "thermal_generation",
            "nuclear_generation",
            "international_imports",
            "wind",
            "pv",
            "csp",
        ]
        for col in expected:
            assert col in result, f"Missing column: {col}"

    def test_skips_empty_forecast_rows(self):
        from tools.market.eskom_client import fetch_station_buildup_observations

        result = fetch_station_buildup_observations(self._path())
        # Station_Build_Up.csv rows 23-25 are empty forecast placeholders
        # (2026-03-16 15:00 through 17:00 with all-null values).
        # These should be excluded. Verify no None values AND that
        # the empty-row datetimes don't appear.
        thermal_dates = {dt for dt, _ in result["thermal_generation"]}
        assert "2026-03-16 15:00" not in thermal_dates, (
            "Empty forecast row 2026-03-16 15:00 should have been skipped"
        )
        for col_obs in result.values():
            for dt, val in col_obs:
                assert isinstance(val, float)


# ---------------------------------------------------------------------------
# Eskom tariff tests
# ---------------------------------------------------------------------------

class TestEskomTariff:
    """Tests for Eskom tariff schedule parsing."""

    def _path(self):
        return str(DATA_DIR / "Eskom-tariffs-1-April-2025-ver-2.xlsm")

    def test_list_tariff_names(self):
        from tools.regulatory.eskom_tariff_client import list_tariff_names

        names = list_tariff_names(self._path())
        assert len(names) >= 5
        assert "Megaflex" in names

    def test_get_rate_megaflex_hd_peak(self):
        from tools.regulatory.eskom_tariff_client import get_rate

        rate = get_rate("Megaflex", tx_zone=0, voltage=1,
                        season="high", period="peak", file_path=self._path())
        assert rate == 684.59

    def test_get_rate_megaflex_ld_offpeak(self):
        from tools.regulatory.eskom_tariff_client import get_rate

        rate = get_rate("Megaflex", tx_zone=0, voltage=1,
                        season="low", period="offpeak", file_path=self._path())
        assert rate == 114.09

    def test_get_tariff_rates_filtering(self):
        from tools.regulatory.eskom_tariff_client import get_tariff_rates

        rates = get_tariff_rates("Megaflex", tx_zone=0, file_path=self._path())
        assert len(rates) >= 4  # 4 voltage levels for zone 0
        for r in rates:
            assert r["tx_zone"] == 0

    def test_cache_reuse(self):
        from tools.regulatory.eskom_tariff_client import get_rate, _cache

        # First call populates cache
        get_rate("Megaflex", 0, 1, "high", "peak", file_path=self._path())
        assert len(_cache) > 0
        # Second call should use cache (same result)
        rate = get_rate("Megaflex", 0, 1, "high", "peak", file_path=self._path())
        assert rate == 684.59


# ---------------------------------------------------------------------------
# GCCA GeoPackage tests
# ---------------------------------------------------------------------------

class TestGCCAClient:
    """Tests for GCCA GeoPackage → GeoJSON parsing."""

    def _path(self):
        return str(DATA_DIR / "GCCA 2025 GIS" / "AREAS_GCCA2025.gpkg")

    def test_mts_zones_count(self):
        from tools.imaging.gcca_client import load_mts_zones

        fc = load_mts_zones(self._path())
        assert fc["type"] == "FeatureCollection"
        assert len(fc["features"]) == 159

    def test_supply_areas_count(self):
        from tools.imaging.gcca_client import load_supply_areas

        fc = load_supply_areas(self._path())
        assert fc["type"] == "FeatureCollection"
        assert len(fc["features"]) == 10

    def test_local_areas_count(self):
        from tools.imaging.gcca_client import load_local_areas

        fc = load_local_areas(self._path())
        assert fc["type"] == "FeatureCollection"
        assert len(fc["features"]) == 34

    def test_geometry_type(self):
        from tools.imaging.gcca_client import load_mts_zones

        fc = load_mts_zones(self._path())
        for feature in fc["features"][:5]:
            assert feature["geometry"]["type"] == "MultiPolygon"
            coords = feature["geometry"]["coordinates"]
            assert isinstance(coords, list)
            assert len(coords) > 0

    def test_acacia_substation(self):
        from tools.imaging.gcca_client import load_mts_zones

        fc = load_mts_zones(self._path())
        names = [f["properties"]["substation"] for f in fc["features"]]
        assert "Acacia" in names

    def test_feature_properties(self):
        from tools.imaging.gcca_client import load_mts_zones

        fc = load_mts_zones(self._path())
        f = fc["features"][0]
        props = f["properties"]
        assert "substation" in props
        assert "supplyarea" in props
        assert "localarea" in props


# ---------------------------------------------------------------------------
# Store round-trip tests
# ---------------------------------------------------------------------------

class TestStoreRoundTrip:
    """Test that parsed data can be stored and retrieved via MarketDataStore."""

    def test_sapp_store_roundtrip(self):
        from tools.market.sapp_client import fetch_observations
        from tools.market.store import MarketDataStore

        obs = fetch_observations(
            str(DATA_DIR / "DAM_RSAN_01-Jan-2025_To_31-Mar-2026_152.xlsx"),
            currency="usd",
        )
        assert len(obs) > 0

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            store = MarketDataStore(db_path)
            store.upsert_observations("sapp_dam_rsan_usd", obs[:100], provider="sapp")
            # Verify values survive the round-trip, not just metadata
            import sqlite3
            conn = sqlite3.connect(db_path)
            rows = conn.execute(
                "SELECT date, value FROM observations "
                "WHERE provider='sapp' AND series_id='sapp_dam_rsan_usd' "
                "ORDER BY date LIMIT 1"
            ).fetchall()
            conn.close()
            assert len(rows) == 1
            assert rows[0][0] == "2025-01-01 00:00"
            assert rows[0][1] == 31.85
        finally:
            os.unlink(db_path)

    def test_eskom_store_roundtrip(self):
        from tools.market.eskom_client import fetch_generation_observations
        from tools.market.store import MarketDataStore

        result = fetch_generation_observations(str(DATA_DIR / "Hourly_Generation.csv"))
        wind_obs = result["wind"]
        assert len(wind_obs) > 0

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            store = MarketDataStore(db_path)
            store.upsert_observations("eskom_re_wind", wind_obs[:100], provider="eskom")
            # Verify first stored value matches parsed input
            import sqlite3
            conn = sqlite3.connect(db_path)
            rows = conn.execute(
                "SELECT date, value FROM observations "
                "WHERE provider='eskom' AND series_id='eskom_re_wind' "
                "ORDER BY date LIMIT 1"
            ).fetchall()
            conn.close()
            assert len(rows) == 1
            assert rows[0][0] == "2026-02-01 00:00"
            assert abs(rows[0][1] - 1375.799) < 0.01
        finally:
            os.unlink(db_path)
