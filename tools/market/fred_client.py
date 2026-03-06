"""Thin FRED API client — uses raw requests (no fredapi dependency)."""

from __future__ import annotations

import logging
from typing import List, Optional, Tuple

import requests

import config

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"


def fetch_observations(
    series_id: str,
    observation_start: Optional[str] = None,
    observation_end: Optional[str] = None,
) -> List[Tuple[str, float]]:
    """Fetch observations from FRED API.

    Returns list of (date_str, value) tuples. Skips FRED's "." marker values.
    """
    api_key = config.FRED.get("api_key", "")
    timeout = config.FRED.get("timeout", 30)

    if not api_key:
        logger.error("FRED API key not configured")
        return []

    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
    }
    if observation_start:
        params["observation_start"] = observation_start
    if observation_end:
        params["observation_end"] = observation_end

    try:
        resp = requests.get(_BASE_URL, params=params, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        logger.error("FRED API request failed for %s: %s", series_id, exc)
        return []

    observations: List[Tuple[str, float]] = []
    for obs in data.get("observations", []):
        val = obs.get("value", ".")
        if val == ".":
            continue
        try:
            observations.append((obs["date"], float(val)))
        except (ValueError, KeyError):
            continue

    logger.info("Fetched %d observations for %s", len(observations), series_id)
    return observations
