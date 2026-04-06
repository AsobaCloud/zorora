"""Greenfield and BESS site desk-screening scores.

This module implements a *prospecting / desk-screening* layer — not feasibility,
not IC-grade diligence, not a single investment label.

Public references for the dimension structure (resource, grid, siting, permitting
context) follow how major RE siting guides frame **early-stage** work: desk
review of resource potential, transmission / interconnect proximity, land and
site constraints, and regulatory / permitting context before full feasibility
(e.g. NREL renewable siting & procurement analysis programmes, DOE large-scale
solar siting resources, RE Data Explorer–style static geospatial screening).

Scoring rule: **regular rubric**. Every declared row has a max; missing or
unknown input is **0 points on that row**. The total is always
``sum(earned) / sum(max)`` over **all** rows — never renormalize to a subset
denominator. ``score_label`` is ``incomplete_desk`` until every row has known
inputs so the headline tier is not presented as a finalized grade.
"""

from __future__ import annotations

import math


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return radius_km * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _factor(
    key: str,
    label: str,
    max_score: float,
    status: str,
    score: float | None = None,
    value: float | None = None,
    unit: str | None = None,
    detail: str = "",
    source: str = "",
) -> dict:
    return {
        "key": key,
        "label": label,
        "status": status,
        "score": score,
        "max_score": max_score,
        "value": value,
        "unit": unit,
        "detail": detail,
        "source": source,
    }


def _aggregate_rubric_from_factors(factors: list[dict]) -> dict:
    """Full rubric: earned / sum(max). Unknown dimensions = 0 earned, full max counts."""
    if not factors:
        return {
            "overall_score": None,
            "strength_tier": None,
            "known_factor_count": 0,
            "unknown_factor_count": 0,
            "rubric_earned": 0.0,
            "rubric_possible": 0.0,
        }
    max_total = sum(float(f.get("max_score") or 0) for f in factors)
    earned = sum(
        float(f["score"])
        for f in factors
        if f.get("status") == "known" and f.get("score") is not None
    )
    known_factor_count = sum(
        1
        for f in factors
        if f.get("status") == "known" and f.get("score") is not None
    )
    unknown_factor_count = sum(1 for f in factors if f.get("status") == "unknown")

    overall_score = None
    strength_tier = None
    if max_total > 0:
        overall_score = round((earned / max_total) * 100, 1)
        if overall_score >= 75:
            strength_tier = "strong"
        elif overall_score >= 50:
            strength_tier = "moderate"
        else:
            strength_tier = "speculative"

    return {
        "overall_score": overall_score,
        "strength_tier": strength_tier,
        "known_factor_count": known_factor_count,
        "unknown_factor_count": unknown_factor_count,
        "rubric_earned": round(earned, 2),
        "rubric_possible": max_total,
    }


def _diligence_screening_ux(
    factors: list[dict],
    agg: dict,
    *,
    framework_key: str,
    framework_title: str,
) -> dict:
    """Build screening metadata + API ``score_label`` (incomplete vs final tier)."""
    pending = [f for f in factors if f.get("status") == "unknown"]
    total = len(factors)
    evaluated_n = total - len(pending)
    is_complete = not pending

    tier = agg.get("strength_tier")
    if is_complete:
        score_label = tier or "unknown"
    else:
        score_label = "incomplete_desk"

    return {
        "score_label": score_label,
        "diligence_screening": {
            "framework_key": framework_key,
            "framework_title": framework_title,
            "stage": "prospecting_desk",
            "dimensions_evaluated": evaluated_n,
            "dimensions_total": total,
            "is_complete": is_complete,
            "pending": [
                {"key": f["key"], "label": f.get("label"), "detail": f.get("detail", "")}
                for f in pending
            ],
            "caveat": (
                "Aligns with early-stage renewable development: desk review of resource, "
                "grid/transmission context, siting / co-location, and permitting before "
                "full feasibility (industry siting guides; NREL/DOE screening tools)."
            ),
            "strength_tier": tier,
        },
    }


def _nearest_distance_km(lat: float, lon: float, candidates: list[dict]) -> float | None:
    distances = []
    for candidate in candidates:
        if "geometry" in candidate:
            coords = candidate.get("geometry", {}).get("coordinates", [])
            if len(coords) < 2:
                continue
            cand_lon, cand_lat = coords[0], coords[1]
        else:
            cand_lat = candidate.get("lat")
            cand_lon = candidate.get("lon")
        if cand_lat is None or cand_lon is None:
            continue
        distances.append(_haversine_km(lat, lon, float(cand_lat), float(cand_lon)))
    return min(distances) if distances else None


def _score_resource(technology: str, resource_summary: dict) -> dict:
    if technology == "solar":
        solar = resource_summary.get("solar")
        if solar and solar.get("annual") is not None:
            annual = float(solar["annual"])
            if annual >= 6.0:
                score = 40
            elif annual >= 5.0:
                score = 33
            elif annual >= 4.0:
                score = 24
            else:
                score = 14
            return _factor(
                "resource_quality",
                "Solar resource (desk screen)",
                40,
                status="known",
                score=score,
                value=annual,
                unit=solar.get("unit"),
                detail="Long-avg irradiance / climatology — not on-site resource campaign",
                source=solar.get("source", ""),
            )
    if technology == "wind":
        wind = resource_summary.get("wind")
        if wind and wind.get("annual") is not None:
            annual = float(wind["annual"])
            if annual >= 8.0:
                score = 40
            elif annual >= 6.5:
                score = 30
            elif annual >= 5.0:
                score = 20
            else:
                score = 10
            return _factor(
                "resource_quality",
                "Wind resource (desk screen)",
                40,
                status="known",
                score=score,
                value=annual,
                unit=wind.get("unit"),
                detail="Long-avg wind resource — not met mast campaign",
                source=wind.get("source", ""),
            )
    return _factor(
        "resource_quality",
        "Renewable resource (desk screen)",
        40,
        status="unknown",
        detail="No resource series for this technology in the screening payload",
    )


def score_site(
    lat: float,
    lon: float,
    technology: str,
    resource_summary: dict,
    generation_assets: list[dict],
    pipeline_assets: list[dict],
    name: str | None = None,
    country: str | None = None,
) -> dict:
    """Desk-screen a greenfield site; see module docstring for diligence framing."""
    technology = str(technology or "").strip().lower()
    factors = [_score_resource(technology, resource_summary or {})]

    nearest_generation = _nearest_distance_km(lat, lon, generation_assets or [])
    if nearest_generation is None:
        factors.append(
            _factor(
                "grid_access",
                "Grid & interconnect proximity (desk)",
                30,
                status="unknown",
                detail="No generation layer to infer transmission / pooling proximity",
            )
        )
    else:
        if nearest_generation <= 25:
            score = 30
        elif nearest_generation <= 75:
            score = 22
        elif nearest_generation <= 150:
            score = 13
        else:
            score = 6
        factors.append(
            _factor(
                "grid_access",
                "Grid & interconnect proximity (desk)",
                30,
                status="known",
                score=score,
                value=round(nearest_generation, 1),
                unit="km",
                detail="Distance to nearest known operating asset (proxy for grid context)",
                source="Imaging generation asset cache",
            )
        )

    nearest_pipeline = _nearest_distance_km(lat, lon, pipeline_assets or [])
    if nearest_pipeline is None:
        factors.append(
            _factor(
                "brownfield_synergy",
                "Siting & brownfield / co-location (desk)",
                20,
                status="unknown",
                detail="No pipeline / candidate layer in this build to score co-location",
            )
        )
    else:
        if nearest_pipeline <= 25:
            score = 20
        elif nearest_pipeline <= 80:
            score = 14
        else:
            score = 7
        factors.append(
            _factor(
                "brownfield_synergy",
                "Siting & brownfield / co-location (desk)",
                20,
                status="known",
                score=score,
                value=round(nearest_pipeline, 1),
                unit="km",
                detail="Distance to nearest brownfield / pipeline candidate",
                source="Brownfield pipeline",
            )
        )

    factors.append(
        _factor(
            "policy_signal",
            "Permitting & regulatory context (desk)",
            10,
            status="unknown",
            detail='Not evaluated in Zorora yet — not a score of "good" or "bad" policy',
        )
    )

    agg = _aggregate_rubric_from_factors(factors)
    ux = _diligence_screening_ux(
        factors,
        agg,
        framework_key="greenfield_pv_wind",
        framework_title="Solar / wind prospecting desk screen",
    )

    site_name = name or f"{technology.title() or 'Candidate'} site @ {lat:.3f}, {lon:.3f}"
    return {
        "name": site_name,
        "technology": technology,
        "lat": lat,
        "lon": lon,
        "country": country or "",
        "overall_score": agg["overall_score"],
        "score_label": ux["score_label"],
        "strength_tier": agg["strength_tier"],
        "factors": factors,
        "resource_summary": resource_summary or {},
        "known_factor_count": agg["known_factor_count"],
        "unknown_factor_count": agg["unknown_factor_count"],
        "rubric_earned": agg["rubric_earned"],
        "rubric_possible": agg["rubric_possible"],
        "diligence_screening": ux["diligence_screening"],
    }


# ---------------------------------------------------------------------------
# BESS site scoring
# ---------------------------------------------------------------------------

def _find_nearest_mts_zone(lat, lon, mts_zones):
    """Find the MTS zone containing the point, or the nearest one.

    Returns (substation_name, supply_area, distance_km, is_inside).
    """
    from tools.imaging.grid_metrics import point_in_polygon

    best_name = None
    best_area = None
    best_dist = float("inf")
    is_inside = False

    for feature in mts_zones.get("features", []):
        props = feature.get("properties", {})
        geom = feature.get("geometry", {})
        coords = geom.get("coordinates", [])
        sub_name = props.get("substation", props.get("mts_1", ""))
        supply_area = props.get("supplyarea", "")

        # Check containment in any polygon
        for polygon in coords:
            if polygon and point_in_polygon(lat, lon, polygon[0]):
                return sub_name, supply_area, 0.0, True

        # Approximate centroid from first polygon's first ring
        if coords and coords[0] and coords[0][0]:
            ring = coords[0][0]
            cx = sum(p[0] for p in ring) / len(ring)
            cy = sum(p[1] for p in ring) / len(ring)
            dist = _haversine_km(lat, lon, cy, cx)
            if dist < best_dist:
                best_dist = dist
                best_name = sub_name
                best_area = supply_area

    return best_name, best_area, best_dist, is_inside


def score_bess_site(
    lat: float,
    lon: float,
    name: str | None = None,
    country: str | None = None,
) -> dict:
    """BESS prospecting desk screen using SAPP DAM, Eskom tariffs, GCCA zones.

    Same API shape as ``score_site()`` (factors, full rubric, ``diligence_screening``)."""
    import logging

    logger = logging.getLogger(__name__)
    factors = []

    # --- Load data sources (cached at module level by each client) ---
    try:
        from tools.imaging.gcca_client import load_mts_zones
        from tools.imaging.grid_metrics import SUPPLY_AREA_DAM_NODE, compute_node_price_stats
        from tools.market.sapp_client import parse_all_dam_files

        mts_zones = load_mts_zones()
        dam_data = parse_all_dam_files()
        node_stats = compute_node_price_stats(dam_data)
    except Exception as exc:
        logger.warning("BESS scoring data load failed: %s", exc)
        mts_zones = {"features": []}
        dam_data = {}
        node_stats = {}

    # --- Determine DAM node from location ---
    sub_name, supply_area, zone_dist, inside_zone = _find_nearest_mts_zone(lat, lon, mts_zones)
    dam_node = SUPPLY_AREA_DAM_NODE.get(supply_area, "")
    if not dam_node:
        # Fallback: latitude-based
        dam_node = "rsan" if lat > -29.0 else "rsas"

    stats = node_stats.get(dam_node, {})

    # --- Factor 1: Arbitrage Spread (max 25) ---
    spread = stats.get("arbitrage_spread_usd")
    if spread is not None:
        if spread > 10:
            arb_score = 25
        elif spread > 6:
            arb_score = 18
        elif spread > 3:
            arb_score = 10
        else:
            arb_score = 4
        factors.append(_factor(
            "arbitrage_spread", "Revenue spread — day-ahead market (desk)", 25, "known",
            score=arb_score, value=round(spread, 1), unit="USD/MWh",
            detail=f"SAPP DAM peak-offpeak spread for {dam_node.upper()}",
            source="SAPP Day-Ahead Market data",
        ))
    else:
        factors.append(_factor(
            "arbitrage_spread", "Revenue spread — day-ahead market (desk)", 25, "unknown",
            detail="No SAPP DAM price data available",
        ))

    # --- Factor 2: TOU Spread (max 25) ---
    try:
        from tools.regulatory.eskom_tariff_client import get_rate
        hd_peak = get_rate("Megaflex", tx_zone=0, voltage=1, season="high", period="peak")
        hd_offpeak = get_rate("Megaflex", tx_zone=0, voltage=1, season="high", period="offpeak")
        if hd_peak is not None and hd_offpeak is not None:
            tou_val = hd_peak - hd_offpeak
            if tou_val > 400:
                tou_score = 25
            elif tou_val > 250:
                tou_score = 18
            elif tou_val > 100:
                tou_score = 10
            else:
                tou_score = 4
            factors.append(_factor(
                "tou_spread", "Retail tariff shape / TOU (desk)", 25, "known",
                score=tou_score, value=round(tou_val, 1), unit="c/kWh",
                detail=f"Megaflex HD peak ({hd_peak:.0f}) minus off-peak ({hd_offpeak:.0f})",
                source="Eskom tariff schedule 2025/26",
            ))
        else:
            factors.append(_factor(
                "tou_spread", "Retail tariff shape / TOU (desk)", 25, "unknown",
                detail="Could not retrieve Eskom Megaflex tariff rates",
            ))
    except Exception as exc:
        logger.warning("TOU spread scoring failed: %s", exc)
        factors.append(_factor(
            "tou_spread", "Retail tariff shape / TOU (desk)", 25, "unknown",
            detail=f"Eskom tariff data unavailable: {exc}",
        ))

    # --- Factor 3: Grid Proximity (max 20) ---
    if inside_zone:
        factors.append(_factor(
            "grid_proximity", "Transmission / MTS zone (desk)", 20, "known",
            score=20, value=0.0, unit="km",
            detail=f"Inside {sub_name} MTS zone",
            source="GCCA 2025 GeoPackage",
        ))
    elif zone_dist < float("inf"):
        if zone_dist <= 25:
            gp_score = 15
        elif zone_dist <= 75:
            gp_score = 8
        else:
            gp_score = 3
        factors.append(_factor(
            "grid_proximity", "Transmission / MTS zone (desk)", 20, "known",
            score=gp_score, value=round(zone_dist, 1), unit="km",
            detail=f"Nearest MTS zone: {sub_name} ({zone_dist:.0f} km)",
            source="GCCA 2025 GeoPackage",
        ))
    else:
        factors.append(_factor(
            "grid_proximity", "Transmission / MTS zone (desk)", 20, "unknown",
            detail="No GCCA MTS zone data available",
        ))

    # --- Factor 4: RE Penetration (max 15) ---
    try:
        from tools.imaging.grid_metrics import compute_zone_metrics
        zone_metrics = compute_zone_metrics(mts_zones, dam_data, [])
        zone_m = zone_metrics.get(sub_name, {}) if sub_name else {}
        re_mw = zone_m.get("re_capacity_mw", 0)
        if re_mw > 200:
            re_score = 15
        elif re_mw > 50:
            re_score = 11
        elif re_mw > 0:
            re_score = 6
        else:
            re_score = 2
        factors.append(_factor(
            "re_penetration", "Zone renewable penetration (desk)", 15, "known",
            score=re_score, value=re_mw, unit="MW",
            detail=f"RE capacity in {sub_name or 'nearest'} zone",
            source="GEM Africa Energy Tracker + GCCA",
        ))
    except Exception:
        factors.append(_factor(
            "re_penetration", "Zone renewable penetration (desk)", 15, "known",
            score=2, value=0, unit="MW",
            detail="No RE asset data available for zone",
            source="GEM Africa Energy Tracker",
        ))

    # --- Factor 5: Demand Level (max 10) ---
    if dam_node == "rsan":
        factors.append(_factor(
            "demand_level", "Demand & load context (desk)", 10, "known",
            score=10, value=None, unit=None,
            detail="RSAN (northern grid) — high industrial demand (Gauteng, Mpumalanga)",
            source="Eskom supply area mapping",
        ))
    else:
        factors.append(_factor(
            "demand_level", "Demand & load context (desk)", 10, "known",
            score=6, value=None, unit=None,
            detail="RSAS (southern grid) — lower demand density",
            source="Eskom supply area mapping",
        ))

    # --- Factor 6: Peaker Competition (max 5) ---
    # Fewer OCGT dispatch hours = less competition = better for BESS
    try:
        from tools.market.eskom_client import fetch_station_buildup_observations
        buildup = fetch_station_buildup_observations()
        ocgt_obs = buildup.get("eskom_ocgt_generation", [])
        if ocgt_obs:
            ocgt_hours = sum(1 for _, v in ocgt_obs if v > 10)
            total_hours = len(ocgt_obs)
            ocgt_pct = (ocgt_hours / total_hours * 100) if total_hours else 0
            pk_score = 5 if ocgt_pct < 10 else 3 if ocgt_pct < 30 else 2
            factors.append(_factor(
                "peaker_competition", "Flexibility & peaker context (desk)", 5, "known",
                score=pk_score, value=round(ocgt_pct, 1), unit="%",
                detail=f"OCGT dispatched {ocgt_hours}/{total_hours} hours ({ocgt_pct:.0f}%)",
                source="Eskom Station Build Up data",
            ))
        else:
            factors.append(_factor(
                "peaker_competition", "Flexibility & peaker context (desk)", 5, "unknown",
                detail="No OCGT dispatch data available",
            ))
    except Exception:
        factors.append(_factor(
            "peaker_competition", "Flexibility & peaker context (desk)", 5, "unknown",
            detail="Eskom station build-up data unavailable",
        ))

    agg = _aggregate_rubric_from_factors(factors)
    ux = _diligence_screening_ux(
        factors,
        agg,
        framework_key="bess_southern_africa_desk",
        framework_title="BESS prospecting desk screen (Southern Africa)",
    )

    site_name = name or f"BESS site @ {lat:.3f}, {lon:.3f}"
    return {
        "name": site_name,
        "technology": "bess",
        "lat": lat,
        "lon": lon,
        "country": country or "",
        "overall_score": agg["overall_score"],
        "score_label": ux["score_label"],
        "strength_tier": agg["strength_tier"],
        "factors": factors,
        "known_factor_count": agg["known_factor_count"],
        "unknown_factor_count": agg["unknown_factor_count"],
        "rubric_earned": agg["rubric_earned"],
        "rubric_possible": agg["rubric_possible"],
        "diligence_screening": ux["diligence_screening"],
    }
