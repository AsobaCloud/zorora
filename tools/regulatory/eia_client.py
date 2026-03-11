"""Thin EIA v2 client for regulatory ingest."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import requests

import config

logger = logging.getLogger(__name__)


def _get_config() -> dict:
    return getattr(config, "EIA", {})


def _fetch_paginated(
    path: str,
    value_field: str,
    endpoint_name: str,
    *,
    frequency: str = "monthly",
    facets: Optional[dict[str, str]] = None,
    extra_data_fields: Optional[list[str]] = None,
) -> List[Dict[str, Any]]:
    cfg = _get_config()
    if not cfg.get("enabled", True):
        return []

    api_key = cfg.get("api_key") or ""
    if not api_key:
        logger.info("EIA client disabled: missing api_key")
        return []

    base_url = cfg.get("base_url", "https://api.eia.gov/v2").rstrip("/")
    timeout = cfg.get("timeout", 30)
    length = int(cfg.get("max_rows_per_request", 5000) or 5000)
    url = f"{base_url}/{path.lstrip('/')}"
    records: List[Dict[str, Any]] = []
    offset = 0

    try:
        while True:
            params: dict[str, Any] = {
                "api_key": api_key,
                "frequency": frequency,
                "data[0]": value_field,
                "length": length,
                "offset": offset,
                "sort[0][column]": "period",
                "sort[0][direction]": "desc",
            }
            for idx, field in enumerate(extra_data_fields or [], start=1):
                params[f"data[{idx}]"] = field
            for key, value in (facets or {}).items():
                if value:
                    params[f"facets[{key}][]"] = value

            response = requests.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            payload = response.json()
            response_data = payload.get("response", {})
            batch = response_data.get("data", []) or []
            total = int(response_data.get("total", 0) or 0)
            if not batch:
                break

            unit = batch[0].get(f"{value_field}-units")
            for row in batch:
                raw_value = row.get(value_field)
                try:
                    value = float(raw_value) if raw_value not in (None, "") else None
                except (TypeError, ValueError):
                    value = None
                records.append(
                    {
                        "endpoint": endpoint_name,
                        "period": row.get("period"),
                        "state": row.get("stateid") or row.get("location"),
                        "fuel_type": row.get("energy_source_code") or row.get("fueltypeid") or row.get("sectorid"),
                        "value": value,
                        "unit": row.get(f"{value_field}-units") or unit,
                        "properties": row,
                    }
                )

            offset += len(batch)
            if total and offset >= total:
                break
            if len(batch) < length:
                break
    except Exception as exc:
        logger.warning("EIA request failed for %s: %s", endpoint_name, exc)
        return []

    return records


def fetch_generator_capacity(state: Optional[str] = None, fuel_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fetch installed generator capacity rows."""
    return _fetch_paginated(
        "electricity/operating-generator-capacity/data",
        "net-summer-capacity-mw",
        "operating-generator-capacity",
        facets={
            "stateid": state or "",
            "energy_source_code": fuel_type or "",
        },
    )


def fetch_operational_data(
    state: Optional[str] = None,
    fuel_type: Optional[str] = None,
    frequency: str = "monthly",
) -> List[Dict[str, Any]]:
    """Fetch generation rows from electric power operational data."""
    return _fetch_paginated(
        "electricity/electric-power-operational-data/data",
        "generation",
        "electric-power-operational-data",
        frequency=frequency,
        facets={
            "location": state or "",
            "fueltypeid": fuel_type or "",
        },
    )


def fetch_retail_sales(
    state: Optional[str] = None,
    sector: Optional[str] = None,
    frequency: str = "monthly",
) -> List[Dict[str, Any]]:
    """Fetch retail electricity sales rows."""
    return _fetch_paginated(
        "electricity/retail-sales/data",
        "sales",
        "retail-sales",
        frequency=frequency,
        facets={
            "stateid": state or "",
            "sectorid": sector or "",
        },
        extra_data_fields=["price"],
    )
