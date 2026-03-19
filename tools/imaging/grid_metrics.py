"""Grid infrastructure metrics for BESS site selection.

Computes per-zone DAM price statistics and RE asset counts by combining
GCCA substation zone data with SAPP Day-Ahead Market prices.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)

# Eskom supply areas mapped to SAPP DAM nodes.
# Verified against GCCA GeoPackage supply area names (2026-03-18).
SUPPLY_AREA_DAM_NODE: Dict[str, str] = {
    "Eastern Cape": "rsas",
    "Free State": "rsan",
    "Gauteng": "rsan",
    "Hydra Central": "rsas",
    "KwaZulu Natal": "rsas",
    "Limpopo": "rsan",
    "Mpumalanga": "rsan",
    "North West": "rsan",
    "Northern Cape": "rsas",
    "Western Cape": "rsas",
}


def classify_peak_hours(hour: int) -> str:
    """Classify hour (0-23) as peak or offpeak per Eskom TOU schedule.

    Peak: 06-08 (inclusive) and 17-20 (inclusive).
    Simplified: applies to all days (actual TOU varies by weekday/season).
    """
    if 6 <= hour <= 8 or 17 <= hour <= 20:
        return "peak"
    return "offpeak"


def compute_node_price_stats(
    dam_data: Dict[str, Dict[str, List[Tuple[str, float]]]],
) -> Dict[str, Dict[str, float]]:
    """Aggregate per-node peak/offpeak/average DAM prices.

    Args:
        dam_data: ``{node: {"usd": [(datetime_str, price), ...]}}``

    Returns:
        ``{node: {"avg_peak_usd", "avg_offpeak_usd", "arbitrage_spread_usd", "avg_dam_price_usd"}}``
    """
    stats: Dict[str, Dict[str, float]] = {}

    for node, currencies in dam_data.items():
        usd_obs = currencies.get("usd", [])
        if not usd_obs:
            continue

        peak_prices: List[float] = []
        offpeak_prices: List[float] = []
        all_prices: List[float] = []

        for dt_str, price in usd_obs:
            all_prices.append(price)
            # Extract hour from "YYYY-MM-DD HH:00"
            try:
                hour = int(dt_str[11:13])
            except (ValueError, IndexError):
                continue
            if classify_peak_hours(hour) == "peak":
                peak_prices.append(price)
            else:
                offpeak_prices.append(price)

        avg_peak = sum(peak_prices) / len(peak_prices) if peak_prices else 0.0
        avg_offpeak = sum(offpeak_prices) / len(offpeak_prices) if offpeak_prices else 0.0
        avg_all = sum(all_prices) / len(all_prices) if all_prices else 0.0

        stats[node] = {
            "avg_peak_usd": round(avg_peak, 2),
            "avg_offpeak_usd": round(avg_offpeak, 2),
            "arbitrage_spread_usd": round(avg_peak - avg_offpeak, 2),
            "avg_dam_price_usd": round(avg_all, 2),
        }

    return stats


def point_in_polygon(lat: float, lon: float, ring: List[List[float]]) -> bool:
    """Ray-casting point-in-polygon test.

    Args:
        lat: point latitude (y)
        lon: point longitude (x)
        ring: list of [x, y] coordinates forming a closed polygon ring
    """
    n = len(ring)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if ((yi > lat) != (yj > lat)) and (lon < (xj - xi) * (lat - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def _point_in_multipolygon(
    lat: float, lon: float, coordinates: List[Any],
) -> bool:
    """Test if a point is inside a MultiPolygon geometry."""
    for polygon in coordinates:
        if not polygon:
            continue
        outer_ring = polygon[0]
        if point_in_polygon(lat, lon, outer_ring):
            return True
    return False


def count_re_assets_in_zone(
    zone_feature: dict,
    generation_features: List[dict],
) -> Tuple[int, float]:
    """Count RE generation assets inside a zone polygon.

    Returns:
        ``(asset_count, total_capacity_mw)``
    """
    geom = zone_feature.get("geometry")
    if not geom or not geom.get("coordinates"):
        return 0, 0.0

    coords = geom["coordinates"]
    count = 0
    total_mw = 0.0

    for feat in generation_features:
        feat_geom = feat.get("geometry")
        if not feat_geom or feat_geom.get("type") != "Point":
            continue
        feat_coords = feat_geom.get("coordinates", [])
        if len(feat_coords) < 2:
            continue
        lon, lat = feat_coords[0], feat_coords[1]

        if _point_in_multipolygon(lat, lon, coords):
            count += 1
            props = feat.get("properties", {})
            cap = props.get("capacity_mw", 0)
            try:
                total_mw += float(cap)
            except (ValueError, TypeError):
                pass

    return count, round(total_mw, 1)


def compute_zone_metrics(
    mts_zones: dict,
    dam_data: Dict[str, Dict[str, List[Tuple[str, float]]]],
    generation_features: List[dict],
) -> Dict[str, Dict[str, Any]]:
    """Compute per-zone DAM price metrics and RE asset counts.

    Args:
        mts_zones: GeoJSON FeatureCollection from ``gcca_client.load_mts_zones()``.
        dam_data: ``{node: {"usd": [...]}}`` from ``sapp_client.parse_all_dam_files()``.
        generation_features: list of GeoJSON features for generation assets.

    Returns:
        ``{substation_name: {dam_node, supply_area, local_area, avg_peak_usd,
        avg_offpeak_usd, arbitrage_spread_usd, avg_dam_price_usd,
        re_asset_count, re_capacity_mw}}``
    """
    node_stats = compute_node_price_stats(dam_data)
    metrics: Dict[str, Dict[str, Any]] = {}

    for feature in mts_zones.get("features", []):
        props = feature.get("properties", {})
        substation = props.get("substation", props.get("mts_1", ""))
        supply_area = props.get("supplyarea", "")
        local_area = props.get("localarea", "")
        dam_node = SUPPLY_AREA_DAM_NODE.get(supply_area, "rsan")

        node_price = node_stats.get(dam_node, {})

        re_count, re_mw = count_re_assets_in_zone(feature, generation_features)

        metrics[substation] = {
            "dam_node": dam_node,
            "supply_area": supply_area,
            "local_area": local_area,
            "avg_peak_usd": node_price.get("avg_peak_usd", 0.0),
            "avg_offpeak_usd": node_price.get("avg_offpeak_usd", 0.0),
            "arbitrage_spread_usd": node_price.get("arbitrage_spread_usd", 0.0),
            "avg_dam_price_usd": node_price.get("avg_dam_price_usd", 0.0),
            "re_asset_count": re_count,
            "re_capacity_mw": re_mw,
        }

    return metrics
