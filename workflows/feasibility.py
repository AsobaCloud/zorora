"""Feasibility study workflow — 5-tab analysis for scouting pipeline assets.

Each tab gathers data from real local data sources, builds a context string,
calls the LLM for synthesis, and returns a structured result dict.
"""

from __future__ import annotations

import base64
import io
import logging
import math
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

FEASIBILITY_TABS = {"production", "trading", "grid", "regulatory", "financial"}

# ---------------------------------------------------------------------------
# Public dispatcher
# ---------------------------------------------------------------------------


def run_feasibility_tab(
    item_id: str,
    item_type: str,
    tab: str,
    item_data: dict,
) -> dict:
    """Dispatch to per-tab analysis function.

    Returns dict with: conclusion, confidence, key_finding, risks, gaps, sources,
    and optionally chart_b64.
    """
    if tab not in FEASIBILITY_TABS:
        raise ValueError(f"Invalid tab: {tab!r}. Must be one of {sorted(FEASIBILITY_TABS)}")

    dispatch = {
        "production": _analyze_production,
        "trading": _analyze_trading,
        "grid": _analyze_grid,
        "regulatory": _analyze_regulatory,
        "financial": _analyze_financial,
    }
    return dispatch[tab](item_data=item_data)


# ---------------------------------------------------------------------------
# LLM helper
# ---------------------------------------------------------------------------


def _call_llm(system_prompt: str, context: str) -> str:
    """Call the reasoning LLM and return the raw text response."""
    try:
        from tools.specialist.client import create_specialist_client
        import config

        client = create_specialist_client("reasoning", config.SPECIALIZED_MODELS["reasoning"])
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": context},
        ]
        response = client.chat_complete(messages, tools=None)
        content = client.extract_content(response)
        return content if isinstance(content, str) else str(content or "")
    except Exception as exc:
        logger.warning("LLM call failed: %s", exc)
        return ""


def _parse_llm_response(text: str) -> dict:
    """Parse structured LLM response text into conclusion/confidence/etc.

    Expected format:
        Key Finding: <text>
        Conclusion: Favorable|Marginal|Unfavorable
        Confidence: High|Medium|Low
        Risks:
        - <risk1>
        Gaps:
        - <gap1>
    """
    conclusion = "marginal"
    confidence = "medium"
    key_finding = ""
    risks: List[str] = []
    gaps: List[str] = []

    if not text or not isinstance(text, str):
        return {
            "conclusion": conclusion,
            "confidence": confidence,
            "key_finding": key_finding,
            "risks": risks,
            "gaps": gaps,
        }

    lines = text.splitlines()
    section = None

    for line in lines:
        stripped = line.strip()
        lower = stripped.lower()

        # Key finding
        if lower.startswith("key finding:"):
            key_finding = stripped[len("key finding:"):].strip()
            section = None
            continue

        # Conclusion mapping
        if lower.startswith("conclusion:"):
            val = stripped[len("conclusion:"):].strip().lower()
            if "favorable" in val and "un" not in val:
                conclusion = "favorable"
            elif "unfavorable" in val:
                conclusion = "unfavorable"
            else:
                conclusion = "marginal"
            section = None
            continue

        # Confidence mapping
        if lower.startswith("confidence:"):
            val = stripped[len("confidence:"):].strip().lower()
            if "high" in val:
                confidence = "high"
            elif "low" in val:
                confidence = "low"
            else:
                confidence = "medium"
            section = None
            continue

        # Section headers
        if lower.startswith("risks:"):
            section = "risks"
            continue
        if lower.startswith("gaps:"):
            section = "gaps"
            continue

        # Bullet items
        if stripped.startswith("-") and section in ("risks", "gaps"):
            item = stripped.lstrip("-").strip()
            if item:
                if section == "risks":
                    risks.append(item)
                else:
                    gaps.append(item)
            continue

        # First non-empty line becomes key_finding if not already set
        if stripped and not key_finding and section is None:
            key_finding = stripped

    return {
        "conclusion": conclusion,
        "confidence": confidence,
        "key_finding": key_finding,
        "risks": risks,
        "gaps": gaps,
    }


# ---------------------------------------------------------------------------
# Haversine distance helper
# ---------------------------------------------------------------------------


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance in km between two points."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _polygon_centroid(coords_list: list) -> Optional[tuple]:
    """Return approximate centroid (lat, lon) of a MultiPolygon/Polygon coordinates."""
    try:
        lats, lons = [], []
        for polygon in coords_list:
            ring = polygon[0] if polygon else []
            for pt in ring:
                if len(pt) >= 2:
                    lons.append(pt[0])
                    lats.append(pt[1])
        if lats and lons:
            return sum(lats) / len(lats), sum(lons) / len(lons)
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Per-tab analysis functions
# ---------------------------------------------------------------------------


def _analyze_production(item_data: dict, **kwargs) -> dict:
    """Analyze solar/wind resource quality and comparable generation assets."""
    lat = item_data.get("lat") or 0.0
    lon = item_data.get("lon") or 0.0
    technology = item_data.get("technology", "solar")
    country = item_data.get("country", "")
    capacity_mw = item_data.get("capacity_mw", 0)

    context_parts = [
        f"Asset: {item_data.get('asset_name', 'Unknown')}",
        f"Technology: {technology}, Capacity: {capacity_mw} MW",
        f"Country: {country}, Location: {lat:.4f}, {lon:.4f}",
    ]
    sources = ["NASA POWER", "GEM Generation Assets"]

    # Gather NASA POWER resource data
    resource = {}
    try:
        from tools.imaging.resource_client import fetch_resource_summary
        resource = fetch_resource_summary(lat, lon)
        solar = resource.get("solar") or {}
        wind = resource.get("wind") or {}
        if solar.get("annual"):
            context_parts.append(
                f"Solar irradiance (annual): {solar['annual']:.2f} {solar.get('unit', 'kWh/m2/day')}"
            )
        if wind.get("annual"):
            context_parts.append(
                f"Wind speed at 50m (annual): {wind['annual']:.2f} {wind.get('unit', 'm/s')}"
            )
        if resource.get("elevation_m") is not None:
            context_parts.append(f"Elevation: {resource['elevation_m']} m")
    except Exception as exc:
        logger.warning("Resource data unavailable: %s", exc)
        context_parts.append("Note: NASA POWER resource data unavailable.")

    # Gather comparable generation assets from store
    try:
        from tools.imaging.store import ImagingDataStore
        store = ImagingDataStore()
        fc = store.get_generation_assets(technology=technology, country=country)
        store.close()
        assets = fc.get("features", [])
        if assets:
            capacities = [
                float(a["properties"].get("capacity_mw") or 0)
                for a in assets
                if a.get("properties")
            ]
            capacities = [c for c in capacities if c > 0]
            if capacities:
                avg_cap = sum(capacities) / len(capacities)
                context_parts.append(
                    f"Comparable {technology} assets in {country}: "
                    f"{len(assets)} found, avg capacity {avg_cap:.0f} MW"
                )
    except Exception as exc:
        logger.warning("Comparable assets unavailable: %s", exc)

    system_prompt = (
        "You are an energy project analyst specialising in renewable resource assessment. "
        "Evaluate the production feasibility of this energy asset based on the data provided. "
        "Respond in this exact format:\n"
        "Key Finding: <one sentence summary>\n"
        "Conclusion: Favorable|Marginal|Unfavorable\n"
        "Confidence: High|Medium|Low\n"
        "Risks:\n- <risk>\nGaps:\n- <gap>"
    )
    context = "\n".join(context_parts)
    llm_text = _call_llm(system_prompt, context)
    parsed = _parse_llm_response(llm_text)

    return {
        "conclusion": parsed["conclusion"],
        "confidence": parsed["confidence"],
        "key_finding": parsed["key_finding"] or f"Resource analysis for {technology} site at {lat:.2f}, {lon:.2f}",
        "risks": parsed["risks"],
        "gaps": parsed["gaps"],
        "sources": sources,
        "chart_b64": None,
    }


def _analyze_trading(item_data: dict, **kwargs) -> dict:
    """Analyze market trading conditions using SAPP DAM prices and Eskom TOU rates."""
    lat = item_data.get("lat") or 0.0
    lon = item_data.get("lon") or 0.0
    country = item_data.get("country", "")
    technology = item_data.get("technology", "solar")
    capacity_mw = item_data.get("capacity_mw", 0)

    context_parts = [
        f"Asset: {item_data.get('asset_name', 'Unknown')}",
        f"Technology: {technology}, Capacity: {capacity_mw} MW",
        f"Country: {country}, Location: {lat:.4f}, {lon:.4f}",
    ]
    sources = ["SAPP DAM Prices", "Eskom TOU Tariffs"]
    chart_b64 = None

    # Determine DAM node from country/lat
    dam_node = "rsan"
    if country.lower() in ("south africa", "za"):
        dam_node = "rsan" if lat > -29.0 else "rsas"
    elif country.lower() in ("zimbabwe", "zw"):
        dam_node = "zim"

    # Load SAPP DAM price data
    hourly_avg: List[float] = []
    try:
        from tools.market.sapp_client import parse_all_dam_files
        dam_data = parse_all_dam_files()
        node_data = dam_data.get(dam_node, {})
        usd_prices = node_data.get("usd", [])
        if not usd_prices and dam_data:
            # fallback to first available node
            first_node = next(iter(dam_data))
            usd_prices = dam_data[first_node].get("usd", [])
            dam_node = first_node

        if usd_prices:
            # Compute 24-hour average price profile
            hour_buckets: Dict[int, List[float]] = {h: [] for h in range(24)}
            for dt_str, price in usd_prices:
                try:
                    hour = int(dt_str.split(" ")[1].split(":")[0])
                    hour_buckets[hour].append(price)
                except (IndexError, ValueError):
                    continue

            hourly_avg = [
                sum(v) / len(v) if v else 0.0
                for h, v in sorted(hour_buckets.items())
            ]
            overall_avg = sum(hourly_avg) / len(hourly_avg) if hourly_avg else 0
            peak_hour = hourly_avg.index(max(hourly_avg)) if hourly_avg else 0
            context_parts.append(
                f"SAPP DAM node: {dam_node.upper()}, "
                f"{len(usd_prices)} hourly observations, "
                f"avg price: ${overall_avg:.2f}/MWh, "
                f"peak hour: {peak_hour:02d}:00"
            )
    except Exception as exc:
        logger.warning("SAPP DAM data unavailable: %s", exc)
        context_parts.append("Note: SAPP DAM price data unavailable.")

    # Load Eskom TOU tariffs
    try:
        from tools.regulatory.eskom_tariff_client import get_tariff_rates
        rates = get_tariff_rates()
        if rates:
            context_parts.append(f"Eskom TOU tariff schedules available: {len(rates)} entries")
    except Exception as exc:
        logger.warning("Eskom tariff data unavailable: %s", exc)

    # Generate 24h price chart
    if hourly_avg:
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            hours = list(range(24))
            fig, ax = plt.subplots(figsize=(8, 4))
            ax.plot(hours, hourly_avg, linewidth=2, color="#2563eb")
            ax.fill_between(hours, hourly_avg, alpha=0.15, color="#2563eb")
            ax.set_xlabel("Hour of Day")
            ax.set_ylabel("Avg Price (USD/MWh)")
            ax.set_title(f"24h DAM Price Profile — {dam_node.upper()}")
            ax.set_xticks(range(0, 24, 3))
            ax.grid(True, alpha=0.3)
            fig.tight_layout()

            buf = io.BytesIO()
            fig.savefig(buf, format="png", bbox_inches="tight", dpi=100)
            plt.close(fig)
            chart_b64 = base64.b64encode(buf.getvalue()).decode()
        except Exception as exc:
            logger.warning("Chart generation failed: %s", exc)

    system_prompt = (
        "You are an energy trading analyst for southern Africa power markets. "
        "Evaluate the trading feasibility of this energy asset. "
        "Respond in this exact format:\n"
        "Key Finding: <one sentence summary>\n"
        "Conclusion: Favorable|Marginal|Unfavorable\n"
        "Confidence: High|Medium|Low\n"
        "Risks:\n- <risk>\nGaps:\n- <gap>"
    )
    context = "\n".join(context_parts)
    llm_text = _call_llm(system_prompt, context)
    parsed = _parse_llm_response(llm_text)

    return {
        "conclusion": parsed["conclusion"],
        "confidence": parsed["confidence"],
        "key_finding": parsed["key_finding"] or f"DAM price analysis for node {dam_node.upper()}",
        "risks": parsed["risks"],
        "gaps": parsed["gaps"],
        "sources": sources,
        "chart_b64": chart_b64,
    }


def _analyze_grid(item_data: dict, **kwargs) -> dict:
    """Analyze grid connection using GCCA MTS zone data."""
    lat = item_data.get("lat") or 0.0
    lon = item_data.get("lon") or 0.0
    country = item_data.get("country", "")
    technology = item_data.get("technology", "solar")
    capacity_mw = item_data.get("capacity_mw", 0)

    context_parts = [
        f"Asset: {item_data.get('asset_name', 'Unknown')}",
        f"Technology: {technology}, Capacity: {capacity_mw} MW",
        f"Country: {country}, Location: {lat:.4f}, {lon:.4f}",
    ]
    sources = ["GCCA MTS Zones 2025"]

    # Load GCCA MTS zone data and find nearest substation
    nearest_substation = None
    nearest_distance_km = None

    try:
        from tools.imaging.gcca_client import load_mts_zones
        mts = load_mts_zones()
        features = mts.get("features", [])

        best_dist = float("inf")
        best_sub = None

        for feat in features:
            geom = feat.get("geometry")
            if not geom:
                continue
            coords = geom.get("coordinates", [])
            centroid = _polygon_centroid(coords)
            if centroid is None:
                continue
            clat, clon = centroid
            dist = _haversine_km(lat, lon, clat, clon)
            if dist < best_dist:
                best_dist = dist
                props = feat.get("properties", {})
                best_sub = props.get("substation") or props.get("mts_1") or "Unknown substation"

        if best_sub:
            nearest_substation = best_sub
            nearest_distance_km = best_dist
            context_parts.append(
                f"Nearest GCCA MTS substation: {nearest_substation} "
                f"({nearest_distance_km:.1f} km away)"
            )
            context_parts.append(f"Total MTS zones loaded: {len(features)}")
    except Exception as exc:
        logger.warning("GCCA data unavailable: %s", exc)
        context_parts.append("Note: GCCA MTS zone data unavailable.")

    system_prompt = (
        "You are a power systems engineer specialising in grid connection assessments. "
        "Evaluate the grid connection feasibility for this energy asset based on the substation data. "
        "Respond in this exact format:\n"
        "Key Finding: <one sentence summary>\n"
        "Conclusion: Favorable|Marginal|Unfavorable\n"
        "Confidence: High|Medium|Low\n"
        "Risks:\n- <risk>\nGaps:\n- <gap>"
    )
    context = "\n".join(context_parts)
    llm_text = _call_llm(system_prompt, context)
    parsed = _parse_llm_response(llm_text)

    sub_info = (
        f"{nearest_substation} ({nearest_distance_km:.1f} km)"
        if nearest_substation
        else "substation data unavailable"
    )

    return {
        "conclusion": parsed["conclusion"],
        "confidence": parsed["confidence"],
        "key_finding": parsed["key_finding"] or f"Nearest GCCA substation: {sub_info}",
        "risks": parsed["risks"],
        "gaps": parsed["gaps"],
        "sources": sources,
        "chart_b64": None,
    }


def _analyze_regulatory(item_data: dict, **kwargs) -> dict:
    """Analyze regulatory environment using the regulatory data store."""
    country = item_data.get("country", "")
    technology = item_data.get("technology", "solar")
    capacity_mw = item_data.get("capacity_mw", 0)

    context_parts = [
        f"Asset: {item_data.get('asset_name', 'Unknown')}",
        f"Technology: {technology}, Capacity: {capacity_mw} MW",
        f"Country: {country}",
    ]
    sources = ["Regulatory research"]

    try:
        from tools.regulatory.store import RegulatoryDataStore
        reg_store = RegulatoryDataStore()
        cur = reg_store.conn.cursor()
        cur.execute(
            "SELECT title, event_type, published_date FROM regulatory_events "
            "WHERE jurisdiction LIKE ? ORDER BY published_date DESC LIMIT 10",
            (f"%{country}%",),
        )
        events = cur.fetchall()
        reg_store.close()
        if events:
            sources = ["NERSA Regulatory Events"]
            context_parts.append(f"Recent regulatory events for {country}: {len(events)}")
            for ev in events[:5]:
                context_parts.append(
                    f"  - [{ev['event_type']}] {ev['title']} ({ev['published_date']})"
                )
        else:
            context_parts.append(f"No regulatory events found for {country} in local store.")
    except Exception as exc:
        logger.warning("Regulatory data unavailable: %s", exc)
        context_parts.append("Note: Regulatory data store unavailable.")

    system_prompt = (
        "You are a regulatory affairs expert specialising in African energy markets. "
        "Evaluate the regulatory feasibility for this energy project based on available data. "
        "Respond in this exact format:\n"
        "Key Finding: <one sentence summary>\n"
        "Conclusion: Favorable|Marginal|Unfavorable\n"
        "Confidence: High|Medium|Low\n"
        "Risks:\n- <risk>\nGaps:\n- <gap>"
    )
    context = "\n".join(context_parts)
    llm_text = _call_llm(system_prompt, context)
    parsed = _parse_llm_response(llm_text)

    return {
        "conclusion": parsed["conclusion"],
        "confidence": parsed["confidence"],
        "key_finding": parsed["key_finding"] or f"Regulatory review for {country}",
        "risks": parsed["risks"],
        "gaps": parsed["gaps"],
        "sources": sources,
        "chart_b64": None,
    }


def _analyze_financial(item_data: dict, prior_results: List[dict] = None, **kwargs) -> dict:
    """Synthesize financial feasibility from prior tab results and macro data."""
    if prior_results is None:
        prior_results = []

    country = item_data.get("country", "")
    technology = item_data.get("technology", "solar")
    capacity_mw = item_data.get("capacity_mw", 0)

    context_parts = [
        f"Asset: {item_data.get('asset_name', 'Unknown')}",
        f"Technology: {technology}, Capacity: {capacity_mw} MW",
        f"Country: {country}",
        f"Prior completed tabs: {len(prior_results)} of 4",
    ]
    sources = []

    # Include prior tab findings
    for r in prior_results:
        tab = r.get("tab", "?")
        conclusion = r.get("conclusion", "?")
        key_finding = r.get("key_finding") or r.get("findings", {}).get("key_finding", "")
        context_parts.append(
            f"  [{tab.upper()}] Conclusion: {conclusion} — {key_finding}"
        )

    # Try FRED/market store for FX rates
    try:
        from tools.market.store import MarketDataStore
        mkt_store = MarketDataStore()
        # ZAR/USD is series DEXSFUS in FRED catalog
        obs = mkt_store.get_observations("DEXSFUS", limit=5)
        mkt_store.close()
        if obs:
            latest_date, latest_val = obs[-1]
            context_parts.append(f"ZAR/USD FX rate (latest {latest_date}): {latest_val:.4f}")
            sources.append("FRED FX Rates")
    except Exception:
        pass

    if not sources:
        sources = ["Prior tab results", "World Bank"]

    system_prompt = (
        "You are a financial analyst specialising in energy project investment in Africa. "
        "Synthesise the financial feasibility of this energy project based on prior study results "
        "and any available macro data. "
        "Respond in this exact format:\n"
        "Key Finding: <one sentence summary>\n"
        "Conclusion: Favorable|Marginal|Unfavorable\n"
        "Confidence: High|Medium|Low\n"
        "Risks:\n- <risk>\nGaps:\n- <gap>"
    )
    context = "\n".join(context_parts)
    llm_text = _call_llm(system_prompt, context)
    parsed = _parse_llm_response(llm_text)

    # Override confidence based on completeness of prior data
    n = len(prior_results)
    if n == 0:
        confidence = "low"
    elif n < 3:
        # cap at medium
        confidence = "medium" if parsed["confidence"] == "high" else parsed["confidence"]
    else:
        confidence = parsed["confidence"]

    return {
        "conclusion": parsed["conclusion"],
        "confidence": confidence,
        "key_finding": parsed["key_finding"] or (
            f"Financial synthesis based on {n}/4 completed prior tabs"
        ),
        "risks": parsed["risks"],
        "gaps": parsed["gaps"],
        "sources": sources,
        "chart_b64": None,
    }
