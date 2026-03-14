"""Resource quality point fetcher for greenfield scouting."""

from __future__ import annotations

import logging

import requests

import config

logger = logging.getLogger(__name__)


def fetch_resource_summary(lat: float, lon: float) -> dict:
    """Fetch solar and wind climatology for a point, returning partial data on failure."""
    endpoint = config.IMAGING.get(
        "resource_point_endpoint",
        "https://power.larc.nasa.gov/api/temporal/climatology/point",
    )
    timeout = config.IMAGING.get("resource_timeout_seconds", 30)
    params = {
        "parameters": "ALLSKY_SFC_SW_DWN,WS50M",
        "community": "RE",
        "longitude": lon,
        "latitude": lat,
        "format": "JSON",
    }
    fallback = {"solar": None, "wind": None}

    try:
        response = requests.get(endpoint, params=params, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
        parameter_data = payload.get("properties", {}).get("parameter", {})
        parameter_meta = payload.get("parameters", {})

        solar = parameter_data.get("ALLSKY_SFC_SW_DWN")
        wind = parameter_data.get("WS50M")
        result = {
            "solar": None,
            "wind": None,
        }
        if solar:
            result["solar"] = {
                "annual": solar.get("ANN"),
                "unit": parameter_meta.get("ALLSKY_SFC_SW_DWN", {}).get("units", "kWh/m^2/day"),
                "source": "NASA POWER ALLSKY_SFC_SW_DWN",
            }
        if wind:
            result["wind"] = {
                "annual": wind.get("ANN"),
                "unit": parameter_meta.get("WS50M", {}).get("units", "m/s"),
                "source": "NASA POWER WS50M",
            }
        elevation = payload.get("geometry", {}).get("coordinates", [None, None, None])
        if len(elevation) > 2 and elevation[2] is not None:
            result["elevation_m"] = elevation[2]
        return result
    except Exception as exc:
        logger.warning("Resource summary fetch failed for %.4f, %.4f: %s", lat, lon, exc)
        fallback["error"] = str(exc)
        return fallback
