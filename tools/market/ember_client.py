"""Ember Energy API client — monthly electricity data for SADC countries."""

from __future__ import annotations

import logging
import os
from typing import List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)


def fetch_observations(
    dataset: str,
    entity_code: str = "ZAF",
    series_filter: Optional[str] = None,
) -> List[Tuple[str, float]]:
    """Fetch monthly electricity data from Ember Energy API.

    Args:
        dataset: One of ``electricity-generation``, ``electricity-demand``,
                 ``installed-capacity``, ``carbon-intensity``.
        entity_code: ISO 3166-1 alpha-3 country code (e.g. ``ZAF``, ``ZWE``).
        series_filter: Optional series name to filter (e.g. ``Coal``, ``Wind``).
                       If None, returns the ``Total generation`` series.

    Returns:
        Sorted list of ``("YYYY-MM-01", value)`` tuples.
    """
    try:
        import config
        ember_cfg = getattr(config, "EMBER", {})
    except ImportError:
        ember_cfg = {}

    api_key = ember_cfg.get("api_key") or os.environ.get("EMBER_API_KEY", "")
    endpoint = ember_cfg.get("endpoint", "https://api.ember-energy.org/v1")
    timeout = ember_cfg.get("timeout", 30)

    if not api_key:
        logger.warning("No Ember API key configured (set EMBER_API_KEY env var)")
        return []

    url = f"{endpoint}/{dataset}/monthly"
    params = {
        "entity_code": entity_code,
        "api_key": api_key,
    }

    try:
        resp = requests.get(url, params=params, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.error("Ember API request failed for %s/%s: %s", dataset, entity_code, exc)
        return []

    records = data.get("data", data) if isinstance(data, dict) else data
    if not isinstance(records, list):
        return []

    target_series = series_filter or "Total generation"
    value_field = _value_field_for_dataset(dataset)

    observations: List[Tuple[str, float]] = []
    for rec in records:
        if rec.get("series") != target_series:
            continue
        date_str = rec.get("date", "")
        value = rec.get(value_field)
        if date_str and value is not None:
            try:
                observations.append((date_str, float(value)))
            except (ValueError, TypeError):
                continue

    observations.sort(key=lambda x: x[0])
    return observations


def _value_field_for_dataset(dataset: str) -> str:
    """Return the JSON field name that contains the numeric value."""
    mapping = {
        "electricity-generation": "generation_twh",
        "electricity-demand": "demand_twh",
        "installed-capacity": "capacity_gw",
        "carbon-intensity": "emissions_intensity_gco2_per_kwh",
    }
    return mapping.get(dataset, "generation_twh")
