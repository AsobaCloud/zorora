"""Recurring digest alert execution helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from tools.alerts.store import AlertStore
from tools.market.store import MarketDataStore
from tools.research.newsroom import fetch_newsroom_cached
from workflows.digest_synthesis import filter_newsroom_articles, news_intel_synthesis


def execute_alert(alert: dict, store: AlertStore, now: datetime | None = None):
    """Execute one saved alert and persist the synthesized result."""
    now = now or datetime.now(timezone.utc)
    today = now.date()
    date_from = (today - timedelta(days=int(alert.get("date_window_days", 7)))).isoformat()
    articles, _warning = fetch_newsroom_cached(max_results=500)
    filtered = filter_newsroom_articles(
        articles,
        topic=alert.get("topic", ""),
        date_from=date_from,
        date_to=today.isoformat(),
        limit=int(alert.get("article_limit", 100)),
    )
    synthesis = news_intel_synthesis(
        filtered,
        topic=alert.get("topic", ""),
        date_from=date_from,
        date_to=today.isoformat(),
    )

    market_snapshot = {}
    series_ids = list(alert.get("staged_series") or [])
    if series_ids:
        market_store = MarketDataStore()
        try:
            for series_id in series_ids:
                point = market_store.get_latest_point(series_id)
                if point:
                    market_snapshot[series_id] = point
        finally:
            market_store.close()

    store.store_result(
        alert_id=alert["id"],
        synthesis=synthesis,
        article_count=len(filtered),
        articles=filtered,
        market_snapshot=market_snapshot,
    )
    store.update_alert(alert["id"], last_run_at=now.isoformat())
