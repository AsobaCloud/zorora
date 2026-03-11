"""Tests for SEP-036: regulatory ingest, store, workflow, API, and UI."""

from __future__ import annotations

import importlib
from pathlib import Path
import tempfile
import time
from unittest.mock import MagicMock, patch

import pytest


def _make_json_response(payload: dict, status_code: int = 200):
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = payload
    response.raise_for_status = MagicMock()
    return response


def _import_app_module():
    return importlib.import_module("ui.web.app")


def _write_rps_workbooks(workbook_dir: Path) -> None:
    from openpyxl import Workbook

    workbook_dir.mkdir(parents=True, exist_ok=True)

    targets_path = workbook_dir / "RPS-CES-Targets-and-Demand-August-2025.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "Statewide Sales"
    headers = ["State", "Special Notes", "RPS Tier or Carve Out", 2025, 2026]
    for col, value in enumerate(headers, start=1):
        ws.cell(row=25, column=col, value=value)
    ws.cell(row=26, column=1, value="CA")
    ws.cell(row=26, column=2, value="Large market")
    ws.cell(row=26, column=3, value="Total RPS")
    ws.cell(row=26, column=4, value=285000)
    ws.cell(row=26, column=5, value=290000)

    ws = wb.create_sheet("RPS-Applicable Sales")
    for col, value in enumerate(headers, start=1):
        ws.cell(row=25, column=col, value=value)
    ws.cell(row=26, column=1, value="CA")
    ws.cell(row=26, column=2, value="Large market")
    ws.cell(row=26, column=3, value="Total RPS")
    ws.cell(row=26, column=4, value=250000)
    ws.cell(row=26, column=5, value=255000)

    ws = wb.create_sheet("RPS & CES Targets (%)")
    for col, value in enumerate(headers, start=1):
        ws.cell(row=25, column=col, value=value)
    ws.cell(row=26, column=1, value="CA")
    ws.cell(row=26, column=2, value="Large market")
    ws.cell(row=26, column=3, value="Total RPS")
    ws.cell(row=26, column=4, value=0.60)
    ws.cell(row=26, column=5, value=0.65)

    ws = wb.create_sheet("RPS & CES Demand (GWh)")
    for col, value in enumerate(headers, start=1):
        ws.cell(row=25, column=col, value=value)
    ws.cell(row=26, column=1, value="CA")
    ws.cell(row=26, column=2, value="Large market")
    ws.cell(row=26, column=3, value="Total RPS")
    ws.cell(row=26, column=4, value=150000)
    ws.cell(row=26, column=5, value=165750)
    wb.save(targets_path)

    additions_path = workbook_dir / "RPS-CES-Capacity-Additions-August-2025.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "RPS & CES Capacity Additions"
    headers = ["State", "Technology", 2025, 2026]
    for col, value in enumerate(headers, start=1):
        ws.cell(row=25, column=col, value=value)
    ws.cell(row=26, column=1, value="CA")
    ws.cell(row=26, column=2, value="Solar")
    ws.cell(row=26, column=3, value=4200)
    ws.cell(row=26, column=4, value=4500)
    wb.save(additions_path)

    costs_path = workbook_dir / "RPS-CES-Compliance-Costs-August-2025.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "Target Achievement"
    headers = ["State", "Notes", "Data Source(s)", "Total RPS or Tier", 2025, 2026]
    for col, value in enumerate(headers, start=1):
        ws.cell(row=29, column=col, value=value)
    ws.cell(row=30, column=1, value="CA")
    ws.cell(row=30, column=2, value="On track")
    ws.cell(row=30, column=3, value="Example")
    ws.cell(row=30, column=4, value="Total RPS")
    ws.cell(row=30, column=5, value=0.98)
    ws.cell(row=30, column=6, value=1.02)

    ws = wb.create_sheet("Compliance Costs")
    for col, value in enumerate(headers, start=1):
        ws.cell(row=24, column=col, value=value)
    ws.cell(row=25, column=1, value="CA")
    ws.cell(row=25, column=2, value="On track")
    ws.cell(row=25, column=3, value="Example")
    ws.cell(row=25, column=4, value="Total RPS")
    ws.cell(row=25, column=5, value=0.012)
    ws.cell(row=25, column=6, value=0.011)
    wb.save(costs_path)


def test_config_has_sep036_blocks():
    import config

    assert hasattr(config, "EIA")
    assert hasattr(config, "OPENEI")
    assert hasattr(config, "REGULATORY")


def test_eia_client_fetch_generator_capacity_paginates_and_normalizes():
    from tools.regulatory import eia_client

    page_1 = {
        "response": {
            "total": "3",
            "data": [
                {
                    "period": "2025-12",
                    "stateid": "CA",
                    "stateName": "California",
                    "energy_source_code": "SUN",
                    "net-summer-capacity-mw": "20",
                    "net-summer-capacity-mw-units": "MW",
                    "plantName": "Sunray 2",
                },
                {
                    "period": "2025-12",
                    "stateid": "CA",
                    "stateName": "California",
                    "energy_source_code": "SUN",
                    "net-summer-capacity-mw": "13.8",
                    "net-summer-capacity-mw-units": "MW",
                    "plantName": "Sunray 3",
                },
            ],
        }
    }
    page_2 = {
        "response": {
            "total": "3",
            "data": [
                {
                    "period": "2025-12",
                    "stateid": "CA",
                    "stateName": "California",
                    "energy_source_code": "SUN",
                    "net-summer-capacity-mw": "11.1",
                    "net-summer-capacity-mw-units": "MW",
                    "plantName": "Sunray 4",
                }
            ],
        }
    }

    with patch.object(eia_client.config, "EIA", {
        "api_key": "demo",
        "base_url": "https://api.eia.gov/v2",
        "timeout": 30,
        "enabled": True,
        "max_rows_per_request": 2,
    }), patch("tools.regulatory.eia_client.requests.get", side_effect=[
        _make_json_response(page_1),
        _make_json_response(page_2),
    ]) as mock_get:
        records = eia_client.fetch_generator_capacity(state="CA", fuel_type="SUN")

    assert len(records) == 3
    assert records[0]["endpoint"] == "operating-generator-capacity"
    assert records[0]["state"] == "CA"
    assert records[0]["fuel_type"] == "SUN"
    assert records[0]["value"] == 20.0
    assert records[0]["unit"] == "MW"
    assert records[0]["properties"]["plantName"] == "Sunray 2"
    assert mock_get.call_count == 2
    first_params = mock_get.call_args_list[0].kwargs["params"]
    second_params = mock_get.call_args_list[1].kwargs["params"]
    assert first_params["facets[stateid][]"] == "CA"
    assert first_params["facets[energy_source_code][]"] == "SUN"
    assert first_params["data[0]"] == "net-summer-capacity-mw"
    assert second_params["offset"] == 2


def test_eia_client_fetch_operational_data_uses_location_and_generation():
    from tools.regulatory import eia_client

    payload = {
        "response": {
            "total": "1",
            "data": [
                {
                    "period": "2025-12",
                    "location": "CA",
                    "stateDescription": "California",
                    "fueltypeid": "SUN",
                    "generation": "2536.06808",
                    "generation-units": "thousand megawatthours",
                }
            ],
        }
    }

    with patch.object(eia_client.config, "EIA", {
        "api_key": "demo",
        "base_url": "https://api.eia.gov/v2",
        "timeout": 30,
        "enabled": True,
        "max_rows_per_request": 5000,
    }), patch("tools.regulatory.eia_client.requests.get", return_value=_make_json_response(payload)) as mock_get:
        records = eia_client.fetch_operational_data(state="CA", fuel_type="SUN")

    assert len(records) == 1
    assert records[0]["endpoint"] == "electric-power-operational-data"
    assert records[0]["state"] == "CA"
    assert records[0]["fuel_type"] == "SUN"
    assert records[0]["value"] == 2536.06808
    params = mock_get.call_args.kwargs["params"]
    assert params["facets[location][]"] == "CA"
    assert params["facets[fueltypeid][]"] == "SUN"
    assert params["data[0]"] == "generation"


def test_openei_client_summarizes_sector_rates():
    from tools.regulatory import openei_client

    search_payload = {
        "items": [
            {"label": "res-1", "utility": "Public Service Co of Colorado", "sector": "Residential", "uri": "https://example.com/res"},
            {"label": "com-1", "utility": "Public Service Co of Colorado", "sector": "Commercial", "uri": "https://example.com/com"},
            {"label": "ind-1", "utility": "Public Service Co of Colorado", "sector": "Industrial", "uri": "https://example.com/ind"},
        ]
    }
    detail_payloads = [
        {"items": [{"sector": "Residential", "energyratestructure": [[{"rate": 0.05951}]], "country": "USA"}]},
        {"items": [{"sector": "Commercial", "energyratestructure": [[{"rate": 0.08123}]], "country": "USA"}]},
        {"items": [{"sector": "Industrial", "energyratestructure": [[{"rate": 0.07111}]], "country": "USA"}]},
    ]

    with patch.object(openei_client.config, "OPENEI", {
        "api_key": "demo",
        "base_url": "https://api.openei.org",
        "timeout": 30,
        "enabled": True,
    }), patch("tools.regulatory.openei_client.requests.get", side_effect=[
        _make_json_response(search_payload),
        _make_json_response(detail_payloads[0]),
        _make_json_response(detail_payloads[1]),
        _make_json_response(detail_payloads[2]),
    ]):
        summary = openei_client.fetch_utility_rates(39.7392, -104.9903)

    assert summary["utility_name"] == "Public Service Co of Colorado"
    assert summary["lat"] == 39.7392
    assert summary["lon"] == -104.9903
    assert summary["rates"]["residential"] == 0.05951
    assert summary["rates"]["commercial"] == 0.08123
    assert summary["rates"]["industrial"] == 0.07111


def test_rps_parser_combines_workbooks():
    from tools.regulatory.rps_client import load_rps_data

    with tempfile.TemporaryDirectory() as tmpdir:
        workbook_dir = Path(tmpdir)
        _write_rps_workbooks(workbook_dir)
        records = load_rps_data(workbook_dir=str(workbook_dir))

    row_2025 = next(
        record for record in records
        if record["state"] == "CA" and record["tier"] == "Total RPS" and record["year"] == 2025
    )
    assert row_2025["standard_type"] == "RPS"
    assert row_2025["target_pct"] == 0.60
    assert row_2025["demand_gwh"] == 150000.0
    assert row_2025["applicable_sales_gwh"] == 250000.0
    assert row_2025["statewide_sales_gwh"] == 285000.0
    assert row_2025["achievement_ratio"] == 0.98
    assert row_2025["compliance_cost_per_kwh"] == 0.012
    assert row_2025["capacity_additions_mw"] == 4200.0


def test_regulatory_store_upsert_and_query(tmp_path):
    from tools.regulatory.store import RegulatoryDataStore

    store = RegulatoryDataStore(db_path=str(tmp_path / "regulatory.db"))
    store.upsert_rps_targets([
        {
            "state": "CA",
            "standard_type": "RPS",
            "tier": "Total RPS",
            "year": 2025,
            "target_pct": 0.60,
            "demand_gwh": 150000.0,
            "applicable_sales_gwh": 250000.0,
            "statewide_sales_gwh": 285000.0,
            "achievement_ratio": 0.98,
            "compliance_cost_per_kwh": 0.012,
            "capacity_additions_mw": 4200.0,
            "notes": "On track",
            "properties": {"source": "test"},
        }
    ])
    store.upsert_eia_series([
        {
            "endpoint": "operating-generator-capacity",
            "period": "2025-12",
            "state": "CA",
            "fuel_type": "SUN",
            "value": 20.0,
            "unit": "MW",
            "properties": {"plantName": "Sunray 2"},
        }
    ], endpoint="operating-generator-capacity")
    store.upsert_utility_rates([
        {
            "utility_name": "Public Service Co of Colorado",
            "state": "CO",
            "sector": "residential",
            "rate_kwh": 0.05951,
            "lat": 39.7392,
            "lon": -104.9903,
            "properties": {"label": "res-1"},
        }
    ])
    store.upsert_regulatory_events([
        {
            "jurisdiction": "US",
            "regulator": "FERC",
            "event_type": "rulemaking",
            "title": "Example Order",
            "summary": "A test event",
            "published_date": "2026-03-01",
            "effective_date": "2026-04-01",
            "deadline_date": None,
            "source_url": "https://example.com/order",
            "properties": {"docket": "RM-1"},
        }
    ])

    rps = store.get_rps_targets(state="CA", year=2025)
    capacity = store.get_eia_series("operating-generator-capacity", state="CA", fuel_type="SUN")
    rates = store.get_utility_rates(state="CO", sector="residential")
    events = store.get_regulatory_events(jurisdiction="US", event_type="rulemaking")

    assert len(rps) == 1
    assert rps[0]["capacity_additions_mw"] == 4200.0
    assert len(capacity) == 1
    assert capacity[0]["value"] == 20.0
    assert len(rates) == 1
    assert rates[0]["rate_kwh"] == 0.05951
    assert len(events) == 1
    assert events[0]["title"] == "Example Order"
    assert store.get_staleness("rps_targets") is not None
    store.close()


def test_regulatory_workflow_updates_all_sources(tmp_path):
    from workflows.regulatory_workflow import RegulatoryWorkflow
    from tools.regulatory.store import RegulatoryDataStore

    store = RegulatoryDataStore(db_path=str(tmp_path / "regulatory.db"))
    workflow = RegulatoryWorkflow(store=store)

    with patch("workflows.regulatory_workflow.fetch_generator_capacity", return_value=[
        {"endpoint": "operating-generator-capacity", "period": "2025-12", "state": "CA", "fuel_type": "SUN", "value": 20.0, "unit": "MW", "properties": {"plantName": "Sunray 2"}}
    ]), patch("workflows.regulatory_workflow.fetch_operational_data", return_value=[
        {"endpoint": "electric-power-operational-data", "period": "2025-12", "state": "CA", "fuel_type": "SUN", "value": 2536.0, "unit": "thousand megawatthours", "properties": {"stateDescription": "California"}}
    ]), patch("workflows.regulatory_workflow.fetch_retail_sales", return_value=[
        {"endpoint": "retail-sales", "period": "2025-12", "state": "CA", "fuel_type": "RES", "value": 15555.0, "unit": "million kilowatt hours", "properties": {"stateDescription": "California"}}
    ]), patch("workflows.regulatory_workflow.fetch_utility_rates", return_value={
        "utility_name": "Public Service Co of Colorado",
        "state": "CO",
        "lat": 39.7392,
        "lon": -104.9903,
        "rates": {"residential": 0.05951, "commercial": 0.08123},
        "properties": {"source": "OpenEI"},
    }), patch("workflows.regulatory_workflow.load_rps_data", return_value=[
        {"state": "CA", "standard_type": "RPS", "tier": "Total RPS", "year": 2025, "target_pct": 0.60,
         "demand_gwh": 150000.0, "applicable_sales_gwh": 250000.0, "statewide_sales_gwh": 285000.0,
         "achievement_ratio": 0.98, "compliance_cost_per_kwh": 0.012, "capacity_additions_mw": 4200.0,
         "notes": "On track", "properties": {"source": "test"}}
    ]):
        updated = workflow.update_all(force=True)

    assert updated >= 4
    assert len(store.get_rps_targets(state="CA")) == 1
    assert len(store.get_eia_series("operating-generator-capacity", state="CA")) == 1
    assert len(store.get_utility_rates(state="CO")) == 2
    store.close()


def test_background_regulatory_refresh_thread_starts():
    from main import _start_regulatory_refresh_thread

    mock_workflow = MagicMock()
    mock_workflow.update_all.return_value = 4

    with patch("main.RegulatoryWorkflow", return_value=mock_workflow):
        thread = _start_regulatory_refresh_thread()

    assert thread is not None
    assert thread.daemon is True
    assert thread.name == "regulatory-refresh"
    time.sleep(0.2)
    assert mock_workflow.update_all.called


class TestRegulatoryApi:
    @pytest.fixture
    def client(self):
        mod = _import_app_module()
        return mod.app.test_client()

    def test_rps_endpoint_returns_filtered_targets(self, client):
        with patch("ui.web.app.RegulatoryDataStore") as mock_store_cls:
            mock_store = MagicMock()
            mock_store.get_rps_targets.return_value = [{"state": "CA", "year": 2025, "target_pct": 0.60}]
            mock_store_cls.return_value = mock_store

            response = client.get("/api/regulatory/rps?state=CA&year=2025")
            assert response.status_code == 200
            payload = response.get_json()
            assert payload["count"] == 1
            mock_store.get_rps_targets.assert_called_once_with(state="CA", year=2025, standard_type=None)

    def test_capacity_endpoint_returns_eia_data(self, client):
        with patch("ui.web.app.RegulatoryDataStore") as mock_store_cls:
            mock_store = MagicMock()
            mock_store.get_eia_series.return_value = [{"state": "CA", "fuel_type": "SUN", "value": 20.0}]
            mock_store_cls.return_value = mock_store

            response = client.get("/api/regulatory/eia/capacity?state=CA&fuel_type=SUN")
            assert response.status_code == 200
            payload = response.get_json()
            assert payload["count"] == 1
            mock_store.get_eia_series.assert_called_once_with("operating-generator-capacity", state="CA", fuel_type="SUN")

    def test_rates_endpoint_returns_rate_records(self, client):
        with patch("ui.web.app.RegulatoryDataStore") as mock_store_cls:
            mock_store = MagicMock()
            mock_store.get_utility_rates.return_value = [{"state": "CO", "sector": "residential", "rate_kwh": 0.05951}]
            mock_store_cls.return_value = mock_store

            response = client.get("/api/regulatory/rates?state=CO&sector=residential")
            assert response.status_code == 200
            payload = response.get_json()
            assert payload["count"] == 1
            mock_store.get_utility_rates.assert_called_once_with(state="CO", sector="residential")

    def test_refresh_endpoint_runs_workflow(self, client):
        with patch("ui.web.app.RegulatoryWorkflow") as mock_workflow_cls:
            mock_workflow = MagicMock()
            mock_workflow.update_all.return_value = 6
            mock_workflow_cls.return_value = mock_workflow

            response = client.post("/api/regulatory/refresh")
            assert response.status_code == 200
            payload = response.get_json()
            assert payload["updated_sources"] == 6
            mock_workflow.update_all.assert_called_once_with(force=True)


def test_template_has_regulatory_mode():
    mod = _import_app_module()
    client = mod.app.test_client()
    response = client.get("/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "data-mode=\"regulatory\"" in html
    assert "Regulatory" in html
    assert "regulatorySection" in html
