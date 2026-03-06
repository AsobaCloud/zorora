"""Thin World Bank Indicators API client — matches fred_client.py signature."""

from __future__ import annotations

import logging
from typing import List, Optional, Tuple

import requests

import config

logger = logging.getLogger(__name__)


def fetch_observations(
    indicator_id: str,
    country: Optional[str] = None,
    start_year: Optional[int] = None,
) -> List[Tuple[str, float]]:
    """Fetch indicator observations from the World Bank API.

    Returns list of (date_str, value) tuples sorted ascending by date.
    Year-only dates are normalized to "YYYY-01-01" for store consistency.
    """
    wb_config = getattr(config, "WORLD_BANK_INDICATORS", {})
    if not wb_config.get("enabled", True):
        return []

    endpoint = wb_config.get("endpoint", "https://api.worldbank.org/v2")
    # 45s default: World Bank API observed at ~0.44s for all-country GDP (2026-03-06).
    # 45s is a conservative margin for API variability; no SLA published.
    timeout = wb_config.get("timeout", 45)
    if country is None:
        country = wb_config.get("default_country", "all")

    url = f"{endpoint}/country/{country}/indicator/{indicator_id}"
    params = {
        "format": "json",
        "per_page": 1000,
    }
    if start_year:
        params["date"] = f"{start_year}:2099"

    try:
        resp = requests.get(url, params=params, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        logger.error("World Bank API request failed for %s: %s", indicator_id, exc)
        return []

    # Response is [metadata, data_array] — validate structure
    if not isinstance(data, list) or len(data) < 2 or not isinstance(data[1], list):
        logger.warning("Unexpected World Bank response format for %s", indicator_id)
        return []

    observations: List[Tuple[str, float]] = []
    for record in data[1]:
        value = record.get("value")
        if value is None:
            continue
        date_str = record.get("date", "")
        if not date_str:
            continue
        try:
            fval = float(value)
        except (ValueError, TypeError):
            continue
        # Normalize year-only dates to YYYY-01-01
        if len(date_str) == 4 and date_str.isdigit():
            date_str = f"{date_str}-01-01"
        observations.append((date_str, fval))

    # Sort ascending by date
    observations.sort(key=lambda x: x[0])

    logger.info("Fetched %d observations for %s", len(observations), indicator_id)
    return observations
