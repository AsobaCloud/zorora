"""Greenfield site scoring utilities."""

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
                "Resource quality",
                40,
                status="known",
                score=score,
                value=annual,
                unit=solar.get("unit"),
                detail="Annual solar resource from climatology",
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
                "Resource quality",
                40,
                status="known",
                score=score,
                value=annual,
                unit=wind.get("unit"),
                detail="Annual wind resource from climatology",
                source=wind.get("source", ""),
            )
    return _factor(
        "resource_quality",
        "Resource quality",
        40,
        status="unknown",
        detail="Resource data unavailable for the selected technology",
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
    """Score a greenfield site using available resource and nearby infrastructure signals."""
    technology = str(technology or "").strip().lower()
    factors = [_score_resource(technology, resource_summary or {})]

    nearest_generation = _nearest_distance_km(lat, lon, generation_assets or [])
    if nearest_generation is None:
        factors.append(
            _factor(
                "grid_access",
                "Grid access",
                30,
                status="unknown",
                detail="No generation asset distance baseline available",
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
                "Grid access",
                30,
                status="known",
                score=score,
                value=round(nearest_generation, 1),
                unit="km",
                detail="Nearest known generation asset distance",
                source="Imaging generation asset cache",
            )
        )

    nearest_pipeline = _nearest_distance_km(lat, lon, pipeline_assets or [])
    if nearest_pipeline is None:
        factors.append(
            _factor(
                "brownfield_synergy",
                "Brownfield synergy",
                20,
                status="unknown",
                detail="No brownfield pipeline assets tracked nearby yet",
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
                "Brownfield synergy",
                20,
                status="known",
                score=score,
                value=round(nearest_pipeline, 1),
                unit="km",
                detail="Nearest brownfield candidate distance",
                source="Brownfield pipeline",
            )
        )

    factors.append(
        _factor(
            "policy_signal",
            "Policy signal",
            10,
            status="unknown",
            detail="No country policy model is configured for this scouting surface yet",
        )
    )

    known_factors = [factor for factor in factors if factor["status"] == "known" and factor["score"] is not None]
    overall_score = None
    score_label = "unknown"
    if known_factors:
        max_known = sum(float(factor["max_score"]) for factor in known_factors)
        total_known = sum(float(factor["score"]) for factor in known_factors)
        overall_score = round((total_known / max_known) * 100, 1) if max_known else None
        if overall_score is not None:
            if overall_score >= 75:
                score_label = "strong"
            elif overall_score >= 50:
                score_label = "moderate"
            else:
                score_label = "speculative"

    site_name = name or f"{technology.title() or 'Candidate'} site @ {lat:.3f}, {lon:.3f}"
    return {
        "name": site_name,
        "technology": technology,
        "lat": lat,
        "lon": lon,
        "country": country or "",
        "overall_score": overall_score,
        "score_label": score_label,
        "factors": factors,
        "resource_summary": resource_summary or {},
        "known_factor_count": len(known_factors),
        "unknown_factor_count": len([factor for factor in factors if factor["status"] == "unknown"]),
    }
