"""Regulatory data refresh workflow."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import config
from tools.regulatory.africa_client import (
    fetch_ippo_press_releases,
    fetch_nersa_events,
    fetch_zera_events,
)
from tools.regulatory.eia_client import (
    fetch_generator_capacity,
    fetch_operational_data,
    fetch_retail_sales,
)
from tools.regulatory.openei_client import fetch_utility_rates
from tools.regulatory.rps_client import latest_workbook_mtime, load_rps_data
from tools.regulatory.store import RegulatoryDataStore


class RegulatoryWorkflow:
    """Refreshes quantitative US sources and normalized ZA/ZW event sources."""

    def __init__(self, store: Optional[RegulatoryDataStore] = None):
        self.store = store or RegulatoryDataStore()
        reg_cfg = getattr(config, "REGULATORY", {})
        self.stale_hours = float(reg_cfg.get("stale_threshold_hours", 168) or 168)
        self.rps_workbook_dir = reg_cfg.get("rps_workbook_dir", "data")
        self.utility_rate_locations = reg_cfg.get(
            "utility_rate_locations",
            [{"name": "Denver", "state": "CO", "lat": 39.7392, "lon": -104.9903}],
        )

    def _store_event_bundle(self, bundle: dict[str, list[dict]]) -> bool:
        events = bundle.get("events") or []
        raw_documents = bundle.get("raw_documents") or []
        transform_runs = bundle.get("transform_runs") or []
        if not events:
            return False
        if raw_documents:
            self.store.upsert_raw_documents(raw_documents)
        if transform_runs:
            self.store.upsert_transform_runs(transform_runs)
        self.store.upsert_regulatory_events(events)
        return True

    def _should_refresh(self, source: str, force: bool) -> bool:
        if force:
            return True
        staleness = self.store.get_staleness(source)
        return staleness is None or staleness >= self.stale_hours

    def _should_refresh_rps(self, force: bool) -> bool:
        if force:
            return True
        last_fetched = self.store.get_last_fetched_at("rps_targets")
        mtime = latest_workbook_mtime(self.rps_workbook_dir)
        if mtime is None:
            return False
        if last_fetched is None:
            return True
        return datetime.fromtimestamp(mtime, tz=timezone.utc) > last_fetched

    def update_all(self, force: bool = False) -> int:
        """Refresh all configured regulatory sources."""
        updated = 0

        if self._should_refresh("operating-generator-capacity", force):
            rows = fetch_generator_capacity()
            if rows:
                self.store.upsert_eia_series(rows, endpoint="operating-generator-capacity")
                updated += 1

        if self._should_refresh("electric-power-operational-data", force):
            rows = fetch_operational_data()
            if rows:
                self.store.upsert_eia_series(rows, endpoint="electric-power-operational-data")
                updated += 1

        if self._should_refresh("retail-sales", force):
            rows = fetch_retail_sales()
            if rows:
                self.store.upsert_eia_series(rows, endpoint="retail-sales")
                updated += 1

        if self._should_refresh("utility_rates", force):
            rate_rows = []
            for location in self.utility_rate_locations:
                summary = fetch_utility_rates(location["lat"], location["lon"])
                for sector, rate in (summary.get("rates") or {}).items():
                    rate_rows.append(
                        {
                            "utility_name": summary.get("utility_name"),
                            "state": summary.get("state") or location.get("state"),
                            "sector": sector,
                            "rate_kwh": rate,
                            "lat": summary.get("lat"),
                            "lon": summary.get("lon"),
                            "properties": summary.get("properties", {}),
                        }
                    )
            if rate_rows:
                self.store.upsert_utility_rates(rate_rows)
                updated += 1

        if self._should_refresh_rps(force):
            rows = load_rps_data(workbook_dir=self.rps_workbook_dir)
            if rows:
                self.store.upsert_rps_targets(rows)
                updated += 1

        if self._should_refresh("nersa_recent_decisions", force):
            if self._store_event_bundle(fetch_nersa_events()):
                updated += 1

        if self._should_refresh("ippo_oldnews", force):
            if self._store_event_bundle(fetch_ippo_press_releases()):
                updated += 1

        if self._should_refresh("zera_seed_catalog", force):
            if self._store_event_bundle(fetch_zera_events()):
                updated += 1

        return updated
