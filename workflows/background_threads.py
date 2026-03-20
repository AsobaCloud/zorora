"""Shared background refresh threads for market, regulatory, and alert data.

Used by both main.py (REPL) and web_main.py (Flask) to keep data current.
"""

from __future__ import annotations

import logging
import threading
import time

logger = logging.getLogger(__name__)


def start_market_refresh_thread():
    """Start a daemon thread that incrementally updates stale market series."""
    def _refresh_loop():
        import config
        from workflows.market_workflow import MarketWorkflow

        while True:
            try:
                wf = MarketWorkflow()
                updated = wf.update_all()
                if updated:
                    logger.info("Background refresh: updated %d series", updated)
            except Exception as e:
                logger.debug("Background refresh failed: %s", e)
            time.sleep(config.MARKET_DATA.get("stale_threshold_hours", 24) * 3600)

    t = threading.Thread(target=_refresh_loop, daemon=True, name="market-refresh")
    t.start()
    return t


def start_regulatory_refresh_thread():
    """Start a daemon thread that incrementally updates stale regulatory sources."""
    def _refresh_loop():
        import config
        from workflows.regulatory_workflow import RegulatoryWorkflow

        while True:
            try:
                workflow = RegulatoryWorkflow()
                updated = workflow.update_all()
                if updated:
                    logger.info("Background regulatory refresh: updated %d sources", updated)
            except Exception as e:
                logger.debug("Background regulatory refresh failed: %s", e)
            time.sleep(config.REGULATORY.get("stale_threshold_hours", 168) * 3600)

    t = threading.Thread(target=_refresh_loop, daemon=True, name="regulatory-refresh")
    t.start()
    return t


def start_alert_check_thread():
    """Start a daemon thread that checks and executes due alerts."""
    def _alert_loop():
        from tools.alerts.store import AlertStore
        from workflows.alert_runner import execute_alert

        while True:
            try:
                store = AlertStore()
                due = store.get_due_alerts()
                for alert in due:
                    try:
                        execute_alert(alert)
                    except Exception as e:
                        logger.debug("Alert execution failed for %s: %s", alert.get("id"), e)
                store.close()
            except Exception as e:
                logger.debug("Alert check failed: %s", e)
            time.sleep(300)

    t = threading.Thread(target=_alert_loop, daemon=True, name="alert-check")
    t.start()
    return t


def start_all_background_threads():
    """Start all background refresh threads. Safe to call from any entry point."""
    start_market_refresh_thread()
    start_regulatory_refresh_thread()
    start_alert_check_thread()
