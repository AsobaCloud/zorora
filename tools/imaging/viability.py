"""Viability scorer for mineral deposits — 5-factor model (0-100)."""

from __future__ import annotations

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# --- Factor 1: Commodity demand base scores (0-20) ---
_COMMODITY_SCORES: Dict[str, int] = {
    "Rare earths": 20, "Lithium": 20, "Cobalt": 20, "Niobium": 18, "Tantalum": 18,
    "Platinum": 15, "Palladium": 15,
    "Chromium": 10, "Manganese": 10, "Vanadium": 10,
    "Gold": 8, "Copper": 8, "Nickel": 8,
    "Iron Ore": 6, "Coal": 4,
}

# Commodity-to-market-series mapping for price signal
_COMMODITY_SERIES: Dict[str, str] = {
    "Platinum": "PL=F",
    "Gold": "GC=F",
    "Lithium": "LIT",
    "Copper": "HG=F",
}

# --- Factor 2: Development status scores (0-25) ---
_STATUS_SCORES: Dict[str, int] = {
    "Producer": 25, "Past producer": 18, "Prospect": 10,
    "Resource": 10, "Occurrence": 3,
}

# --- Factor 3: Processing feasibility by work type (0-15) ---
_WORK_TYPE_SCORES: Dict[str, int] = {
    "Open pit": 15, "Surface": 12, "Placer": 12,
    "Underground": 8,
}

# --- Factor 5: Regulatory environment by country (0-15) ---
_REGULATORY_SCORES: Dict[str, int] = {
    "South Africa": 10,
    "Zimbabwe": 5,
}


def score_deposit(
    feature: dict,
    viirs_radiance: Optional[float] = None,
    price_trends: Optional[Dict[str, float]] = None,
) -> dict:
    """Compute viability score (0-100) for a single deposit feature.

    Args:
        feature: GeoJSON Feature with properties (commod1, dev_stat, work_type, country).
        viirs_radiance: VIIRS nightlight radiance at deposit location (nW/cm2/sr).
        price_trends: Dict mapping commodity name to recent price change percentage.

    Returns:
        Dict with score, max, tier, and per-component points.
    """
    props = feature.get("properties", {})
    commod1 = props.get("commod1", "")
    dev_stat = props.get("dev_stat", "")
    work_type = props.get("work_type", "")
    country = props.get("country", "")

    # Factor 1: Commodity demand (0-20)
    commodity_pts = _COMMODITY_SCORES.get(commod1, 5)

    # Price signal bonus (0 or +5)
    price_signal = 0
    if price_trends and commod1 in price_trends:
        if price_trends[commod1] > 0:
            price_signal = 5

    # Factor 2: Development status (0-25)
    status_pts = _STATUS_SCORES.get(dev_stat, 3)

    # Factor 3: Processing feasibility (0-15)
    processing_pts = _WORK_TYPE_SCORES.get(work_type, 5)

    # Factor 4: Power proximity from VIIRS (0-20)
    if viirs_radiance is None:
        power_pts = 2  # unknown
    elif viirs_radiance > 10:
        power_pts = 20
    elif viirs_radiance > 2:
        power_pts = 14
    elif viirs_radiance > 0.5:
        power_pts = 8
    else:
        power_pts = 2

    # Factor 5: Regulatory environment (0-15)
    regulatory_pts = _REGULATORY_SCORES.get(country, 3)

    total = commodity_pts + price_signal + status_pts + processing_pts + power_pts + regulatory_pts

    if total >= 65:
        tier = "high"
    elif total >= 35:
        tier = "medium"
    else:
        tier = "low"

    return {
        "score": total,
        "max": 100,
        "tier": tier,
        "commodity_pts": commodity_pts,
        "price_signal": price_signal,
        "status_pts": status_pts,
        "processing_pts": processing_pts,
        "power_pts": power_pts,
        "regulatory_pts": regulatory_pts,
    }


def score_all_deposits(
    features: list,
    price_trends: Optional[Dict[str, float]] = None,
) -> list:
    """Score all deposits, injecting viability into each feature's properties."""
    scored = []
    for feat in features:
        result = score_deposit(feat, viirs_radiance=None, price_trends=price_trends)
        feat_copy = {
            "type": feat.get("type", "Feature"),
            "geometry": feat.get("geometry"),
            "properties": {**feat.get("properties", {}), "viability": result},
        }
        scored.append(feat_copy)
    return scored
