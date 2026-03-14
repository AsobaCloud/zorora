"""Tests for SEP-037: recurring digest alerts."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import importlib
from unittest.mock import MagicMock, patch

import pytest


def _import_app_module():
    return importlib.import_module("ui.web.app")


def test_config_has_alerts_block():
    import config

    assert hasattr(config, "ALERTS")
    assert config.ALERTS.get("enabled") is True


def test_digest_synthesis_module_filters_articles():
    from workflows.digest_synthesis import filter_newsroom_articles

    articles = [
        {"headline": "South Africa renewable regulation shifts", "date": "2026-03-09", "source": "Desk", "topic_tags": ["renewables", "regulation"]},
        {"headline": "Copper demand update", "date": "2026-03-09", "source": "Desk", "topic_tags": ["metals"]},
        {"headline": "South Africa auction update", "date": "2026-02-20", "source": "Desk", "topic_tags": ["renewables"]},
    ]

    filtered = filter_newsroom_articles(
        articles,
        topic="South Africa renewable",
        date_from="2026-03-01",
        date_to="2026-03-10",
        limit=20,
    )

    assert len(filtered) == 1
    assert filtered[0]["headline"] == "South Africa renewable regulation shifts"


def test_alert_store_crud_and_due_logic(tmp_path):
    from tools.alerts.store import AlertStore

    store = AlertStore(db_path=str(tmp_path / "alerts.db"))
    daily_id = store.create_alert(
        name="Daily watch",
        topic="south africa regulation",
        date_window_days=7,
        article_limit=50,
        staged_series=["DEXSFUS"],
        interval="daily",
    )
    weekly_id = store.create_alert(
        name="Weekly watch",
        topic="zim energy",
        date_window_days=14,
        article_limit=50,
        staged_series=[],
        interval="weekly",
    )

    now = datetime.now(timezone.utc)
    store.update_alert(daily_id, last_run_at=(now - timedelta(days=2)).isoformat())
    store.update_alert(weekly_id, last_run_at=(now - timedelta(days=2)).isoformat())

    due = store.get_due_alerts(now=now)
    due_ids = {alert["id"] for alert in due}
    assert daily_id in due_ids
    assert weekly_id not in due_ids

    store.store_result(
        alert_id=daily_id,
        synthesis="Digest output",
        article_count=3,
        articles=[{"headline": "A"}],
        market_snapshot={"DEXSFUS": {"latest_value": 18.1}},
    )

    alerts = store.list_alerts()
    alert_row = next(alert for alert in alerts if alert["id"] == daily_id)
    assert alert_row["unread_count"] == 1

    results = store.get_results(daily_id)
    assert len(results) == 1
    assert results[0]["synthesis"] == "Digest output"

    store.mark_all_read(daily_id)
    reread = store.get_results(daily_id)
    assert reread[0]["read"] == 1

    store.delete_alert(daily_id)
    remaining = {alert["id"] for alert in store.list_alerts()}
    assert daily_id not in remaining
    assert weekly_id in remaining
    store.close()


def test_execute_alert_reuses_shared_synthesis_and_stores_result(tmp_path):
    from tools.alerts.store import AlertStore
    from workflows.alert_runner import execute_alert

    store = AlertStore(db_path=str(tmp_path / "alerts.db"))
    alert_id = store.create_alert(
        name="Daily watch",
        topic="south africa regulation",
        date_window_days=7,
        article_limit=50,
        staged_series=["DCOILWTICO"],
        interval="daily",
    )
    alert = store.get_alert(alert_id)

    with patch("workflows.alert_runner.fetch_newsroom_cached", return_value=([
        {"headline": "South Africa renewable regulation shifts", "date": "2026-03-09", "source": "Desk", "url": "https://a", "topic_tags": ["renewables"]},
    ], None)), patch("workflows.alert_runner.filter_newsroom_articles", return_value=[
        {"headline": "South Africa renewable regulation shifts", "date": "2026-03-09", "source": "Desk", "url": "https://a", "topic_tags": ["renewables"]},
    ]) as mock_filter, patch("workflows.alert_runner.news_intel_synthesis", return_value="Synthesized digest") as mock_synth, patch("workflows.alert_runner.MarketDataStore") as mock_market_cls:
        market_store = MagicMock()
        market_store.get_latest_point.return_value = {"series_id": "DCOILWTICO", "latest_value": 72.4, "latest_date": "2026-03-10"}
        mock_market_cls.return_value = market_store
        execute_alert(alert, store)

    mock_filter.assert_called_once()
    mock_synth.assert_called_once()
    results = store.get_results(alert_id)
    assert len(results) == 1
    assert results[0]["synthesis"] == "Synthesized digest"
    assert results[0]["article_count"] == 1
    assert results[0]["market_snapshot"]["DCOILWTICO"]["latest_value"] == 72.4
    refreshed = store.get_alert(alert_id)
    assert refreshed["last_run_at"] is not None
    store.close()


def test_background_alert_check_thread_starts():
    from main import _start_alert_check_thread

    mock_store = MagicMock()
    mock_store.get_due_alerts.return_value = []

    with patch("main.AlertStore", return_value=mock_store), patch("main.execute_alert") as mock_execute:
        thread = _start_alert_check_thread()

    assert thread is not None
    assert thread.daemon is True
    assert thread.name == "alert-check"
    assert mock_execute.call_count == 0


class TestAlertsApi:
    @pytest.fixture
    def client(self):
        mod = _import_app_module()
        return mod.app.test_client()

    def test_create_and_list_alerts_endpoints(self, client):
        with patch("ui.web.app.AlertStore") as mock_store_cls:
            store = MagicMock()
            store.create_alert.return_value = "alert-1"
            store.list_alerts.return_value = [{"id": "alert-1", "name": "Daily watch", "unread_count": 2}]
            mock_store_cls.return_value = store

            created = client.post("/api/alerts", json={
                "name": "Daily watch",
                "topic": "south africa regulation",
                "date_window_days": 7,
                "article_limit": 50,
                "staged_series": ["DEXSFUS"],
                "interval": "daily",
            })
            listed = client.get("/api/alerts")

            assert created.status_code == 200
            assert created.get_json()["alert_id"] == "alert-1"
            assert listed.status_code == 200
            assert listed.get_json()["alerts"][0]["unread_count"] == 2

    def test_alert_results_and_read_endpoints(self, client):
        with patch("ui.web.app.AlertStore") as mock_store_cls:
            store = MagicMock()
            store.get_results.return_value = [{"id": "result-1", "synthesis": "Digest output", "read": 0}]
            mock_store_cls.return_value = store

            results = client.get("/api/alerts/alert-1/results?limit=10&offset=0")
            mark_read = client.post("/api/alerts/alert-1/read")

            assert results.status_code == 200
            assert results.get_json()["results"][0]["id"] == "result-1"
            assert mark_read.status_code == 200
            store.mark_all_read.assert_called_once_with("alert-1")


def test_template_has_alert_ui():
    mod = _import_app_module()
    client = mod.app.test_client()
    response = client.get("/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Save as Alert" in html
    assert "data-mode=\"alerts\"" in html
    assert "alertsSection" in html
