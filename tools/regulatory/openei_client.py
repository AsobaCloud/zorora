"""Thin OpenEI utility-rates client."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import requests

import config

logger = logging.getLogger(__name__)

_SECTOR_MAP = {
    "residential": "residential",
    "commercial": "commercial",
    "industrial": "industrial",
}


def _get_config() -> dict:
    return getattr(config, "OPENEI", {})


def _extract_first_rate(node: Any) -> Optional[float]:
    if isinstance(node, dict):
        rate = node.get("rate")
        if rate not in (None, ""):
            try:
                return float(rate)
            except (TypeError, ValueError):
                return None
        for value in node.values():
            result = _extract_first_rate(value)
            if result is not None:
                return result
        return None
    if isinstance(node, list):
        for value in node:
            result = _extract_first_rate(value)
            if result is not None:
                return result
    return None


def fetch_utility_rates(lat: float, lon: float) -> Dict[str, Any]:
    """Fetch the nearest utility tariffs and summarize one sectoral rate each."""
    cfg = _get_config()
    if not cfg.get("enabled", True):
        return {"lat": lat, "lon": lon, "rates": {}, "properties": {}}

    api_key = cfg.get("api_key") or ""
    if not api_key:
        logger.info("OpenEI client disabled: missing api_key")
        return {"lat": lat, "lon": lon, "rates": {}, "properties": {}}

    base_url = cfg.get("base_url", "https://api.openei.org").rstrip("/")
    timeout = cfg.get("timeout", 30)
    url = f"{base_url}/utility_rates"

    try:
        search = requests.get(
            url,
            params={
                "version": "latest",
                "format": "json",
                "api_key": api_key,
                "lat": lat,
                "lon": lon,
            },
            timeout=timeout,
        )
        search.raise_for_status()
        items = search.json().get("items", []) or []
    except Exception as exc:
        logger.warning("OpenEI search failed for %.4f, %.4f: %s", lat, lon, exc)
        return {"lat": lat, "lon": lon, "rates": {}, "properties": {}}

    summary: Dict[str, Any] = {
        "utility_name": items[0].get("utility") if items else None,
        "state": None,
        "lat": lat,
        "lon": lon,
        "rates": {},
        "properties": {"items": items},
    }

    seen = set()
    for item in items:
        sector = _SECTOR_MAP.get(str(item.get("sector", "")).strip().lower())
        label = item.get("label")
        if not sector or not label or sector in seen:
            continue
        seen.add(sector)
        try:
            detail = requests.get(
                url,
                params={
                    "version": "latest",
                    "format": "json",
                    "detail": "full",
                    "getpage": label,
                    "api_key": api_key,
                },
                timeout=timeout,
            )
            detail.raise_for_status()
            detail_items = detail.json().get("items", []) or []
            detail_item = detail_items[0] if detail_items else {}
            rate = _extract_first_rate(detail_item.get("energyratestructure"))
            if rate is not None:
                summary["rates"][sector] = rate
            if not summary.get("utility_name"):
                summary["utility_name"] = detail_item.get("utility")
        except Exception as exc:
            logger.warning("OpenEI detail request failed for %s: %s", label, exc)

        if len(seen) == len(_SECTOR_MAP):
            break

    return summary


def fetch_rate_by_utility(utility_name: str) -> list[dict]:
    """Search minimal utility-rate entries for a named utility."""
    cfg = _get_config()
    if not cfg.get("enabled", True):
        return []

    api_key = cfg.get("api_key") or ""
    if not api_key:
        logger.info("OpenEI client disabled: missing api_key")
        return []

    base_url = cfg.get("base_url", "https://api.openei.org").rstrip("/")
    timeout = cfg.get("timeout", 30)
    try:
        response = requests.get(
            f"{base_url}/utility_rates",
            params={
                "version": "latest",
                "format": "json",
                "detail": "minimal",
                "api_key": api_key,
                "ratesforutility": utility_name,
            },
            timeout=timeout,
        )
        response.raise_for_status()
        return response.json().get("items", []) or []
    except Exception as exc:
        logger.warning("OpenEI utility search failed for %s: %s", utility_name, exc)
        return []
