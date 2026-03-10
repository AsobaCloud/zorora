"""Mining concessions client — fetches operating mine data from openAFRICA DMRE."""

from __future__ import annotations

import csv
import io
import logging
from typing import Optional

import requests

import config

logger = logging.getLogger(__name__)

_SA_DMRE_URL = (
    "https://open.africa/en_AU/dataset/"
    "mines-quarries-agents-and-mineral-processing-plants-officially-operating-in-south-africa"
)


def fetch_concessions_sa(url: Optional[str] = None) -> dict:
    """Fetch South Africa DMRE operating mines as GeoJSON FeatureCollection.

    Expects CSV with columns: mine_name, operator, mineral_type, status, latitude, longitude.
    """
    img_config = getattr(config, "IMAGING", {})
    timeout = img_config.get("mrds_timeout", 60)
    target_url = url or _SA_DMRE_URL

    try:
        resp = requests.get(target_url, timeout=timeout)
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.error("Concessions SA request failed: %s", exc)
        return {"type": "FeatureCollection", "features": []}

    features = []
    reader = csv.DictReader(io.StringIO(resp.text))
    for row in reader:
        try:
            lat = float(row.get("latitude", 0))
            lon = float(row.get("longitude", 0))
        except (ValueError, TypeError):
            continue
        if lat == 0 and lon == 0:
            continue
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {
                "name": row.get("mine_name", "Unknown"),
                "operator": row.get("operator", "Unknown"),
                "mineral_type": row.get("mineral_type", "Unknown"),
                "status": row.get("status", "Unknown"),
                "country": "South Africa",
            },
        })

    logger.info("Parsed %d SA concessions", len(features))
    return {"type": "FeatureCollection", "features": features}


def merge_concessions(*collections: dict) -> dict:
    """Merge multiple GeoJSON FeatureCollections into one."""
    features = []
    for col in collections:
        features.extend(col.get("features", []))
    return {"type": "FeatureCollection", "features": features}
