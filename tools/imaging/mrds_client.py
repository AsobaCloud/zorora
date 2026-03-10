"""USGS MRDS WFS client — fetches mineral deposit data as GeoJSON."""

from __future__ import annotations

import logging
from typing import Optional

import requests

import config

logger = logging.getLogger(__name__)


def fetch_deposits(
    bbox: Optional[list] = None,
    commodity: Optional[str] = None,
) -> dict:
    """Fetch mineral deposits from USGS MRDS WFS service.

    Returns a GeoJSON FeatureCollection with deposit properties:
    name, dep_type, commod1/2/3, dev_stat, work_type, latitude, longitude, country.
    """
    img_config = getattr(config, "IMAGING", {})
    endpoint = img_config.get("mrds_wfs_endpoint", "https://mrdata.usgs.gov/services/mrds")
    timeout = img_config.get("mrds_timeout", 60)
    if bbox is None:
        bbox = img_config.get("mrds_bbox", [15, -35, 40, -15])

    params = {
        "service": "WFS",
        "version": "1.1.0",
        "request": "GetFeature",
        "typeName": "mrds",
        "outputFormat": "application/json",
        "srsName": "EPSG:4326",
        "bbox": ",".join(str(v) for v in bbox),
    }

    if commodity:
        params["CQL_FILTER"] = f"commod1='{commodity}'"

    try:
        resp = requests.get(endpoint, params=params, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        logger.error("MRDS WFS request failed: %s", exc)
        return {"type": "FeatureCollection", "features": []}

    if data.get("type") != "FeatureCollection":
        logger.warning("Unexpected MRDS response format, returning empty")
        return {"type": "FeatureCollection", "features": []}

    return data
