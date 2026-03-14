"""USGS MRDS WFS client — fetches mineral deposit data as GeoJSON.

The MRDS WFS endpoint only supports GML 3.1.1 output (no GeoJSON).
This client fetches GML, parses it with ElementTree, and converts to GeoJSON.

WFS field mapping (verified against live endpoint 2026-03-10):
  ms:site_name  -> name
  ms:dep_id     -> dep_id
  ms:dev_stat   -> dev_stat
  ms:code_list  -> commod1, commod2, commod3 (space-separated commodity codes)
  ms:fips_code  -> country (FIPS code mapped to country name)
  gml:pos       -> latitude, longitude (from Point geometry)
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from typing import Optional

import requests

import config

logger = logging.getLogger(__name__)

# USGS MRDS commodity codes -> human-readable names
# Source: MRDS detail pages (e.g. dep_id=10038814)
_COMMODITY_CODES = {
    "PGE_PT": "Platinum", "PGE_PD": "Palladium", "PGE": "Platinum",
    "AU": "Gold", "AG": "Silver", "CU": "Copper", "NI": "Nickel",
    "CO": "Cobalt", "CR": "Chromium", "MN": "Manganese", "V": "Vanadium",
    "FE": "Iron Ore", "TI": "Titanium", "ZR": "Zirconium",
    "LI": "Lithium", "SN": "Tin", "W": "Tungsten", "MO": "Molybdenum",
    "ZN": "Zinc", "PB": "Lead", "U": "Uranium", "F": "Fluorite",
    "REE": "Rare earths", "NB": "Niobium", "TA": "Tantalum",
    "COAL": "Coal", "DIAMOND": "Diamond", "KAOL": "Kaolin",
    "ITE": "Ilmenite", "PHOS": "Phosphate", "ITE_RUT": "Rutile",
    "ASB": "Asbestos", "ITE_ZR": "Zirconium",
}

# FIPS country codes -> country names (SA/ZW region)
# MRDS returns codes prefixed with 'f' (e.g. "fSF")
_FIPS_COUNTRIES = {
    "SF": "South Africa", "ZI": "Zimbabwe", "MZ": "Mozambique",
    "BC": "Botswana", "WA": "Namibia", "LT": "Lesotho", "WZ": "Eswatini",
    "ZA": "Zambia", "CG": "Democratic Republic of the Congo",
    "MI": "Malawi", "TZ": "Tanzania", "AO": "Angola",
}

# GML namespaces used in MRDS WFS responses
_NS = {
    "gml": "http://www.opengis.net/gml",
    "ms": "http://mapserver.gis.umn.edu/mapserver",
    "wfs": "http://www.opengis.net/wfs",
}


def _parse_commodity_codes(code_list: str) -> list[str]:
    """Convert space-separated MRDS commodity codes to human names."""
    if not code_list:
        return []
    names = []
    for code in code_list.strip().split():
        name = _COMMODITY_CODES.get(code, code)
        if name not in names:
            names.append(name)
    return names


def _parse_fips_code(fips: str) -> str:
    """Convert MRDS FIPS code (e.g. 'fSF') to country name."""
    if not fips:
        return "Unknown"
    code = fips.lstrip("f")
    return _FIPS_COUNTRIES.get(code, fips)


def _parse_gml_features(xml_text: str) -> list[dict]:
    """Parse GML WFS response into list of GeoJSON Feature dicts."""
    features = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        logger.error("Failed to parse MRDS GML response: %s", exc)
        return []

    for member in root.findall(".//gml:featureMember", _NS):
        feature_el = member.find("ms:mrds", _NS)
        if feature_el is None:
            continue

        site_name = (feature_el.findtext("ms:site_name", "", _NS) or "").strip()
        dep_id = (feature_el.findtext("ms:dep_id", "", _NS) or "").strip()
        dev_stat = (feature_el.findtext("ms:dev_stat", "", _NS) or "").strip()
        code_list = (feature_el.findtext("ms:code_list", "", _NS) or "").strip()
        fips_code = (feature_el.findtext("ms:fips_code", "", _NS) or "").strip()

        pos_el = feature_el.find(".//gml:pos", _NS)
        if pos_el is None or not pos_el.text:
            continue
        parts = pos_el.text.strip().split()
        if len(parts) != 2:
            continue
        try:
            # EPSG:4326 with WFS 1.1.0: pos is "lat lon"
            lat = float(parts[0])
            lon = float(parts[1])
        except ValueError:
            continue

        commodities = _parse_commodity_codes(code_list)
        commod1 = commodities[0] if len(commodities) > 0 else ""
        commod2 = commodities[1] if len(commodities) > 1 else ""
        commod3 = commodities[2] if len(commodities) > 2 else ""

        country = _parse_fips_code(fips_code)

        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {
                "dep_id": dep_id,
                "name": site_name,
                "commod1": commod1,
                "commod2": commod2,
                "commod3": commod3,
                "dev_stat": dev_stat,
                "country": country,
                "latitude": lat,
                "longitude": lon,
                "code_list": code_list,
            },
        })

    return features


def fetch_deposits(
    bbox: Optional[list] = None,
    commodity: Optional[str] = None,
    max_features: int = 5000,
) -> dict:
    """Fetch mineral deposits from USGS MRDS WFS service.

    Returns a GeoJSON FeatureCollection with deposit properties:
    name, dep_id, commod1/2/3, dev_stat, country, latitude, longitude.
    """
    img_config = getattr(config, "IMAGING", {})
    endpoint = img_config.get(
        "mrds_wfs_endpoint", "https://mrdata.usgs.gov/services/wfs/mrds"
    )
    timeout = img_config.get("mrds_timeout", 60)
    if bbox is None:
        bbox = img_config.get("mrds_bbox", [15, -35, 40, -15])

    params = {
        "service": "WFS",
        "version": "1.1.0",
        "request": "GetFeature",
        "typeName": "mrds",
        "srsName": "EPSG:4326",
        "bbox": ",".join(str(v) for v in bbox),
        "maxFeatures": str(max_features),
    }

    if commodity:
        reverse_codes = {v: k for k, v in _COMMODITY_CODES.items()}
        code = reverse_codes.get(commodity, commodity)
        params["CQL_FILTER"] = f"code_list LIKE '%{code}%'"

    try:
        resp = requests.get(endpoint, params=params, timeout=timeout)
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.error("MRDS WFS request failed: %s", exc)
        return {"type": "FeatureCollection", "features": []}

    features = _parse_gml_features(resp.text)
    logger.info("Fetched %d deposits from MRDS WFS", len(features))
    return {"type": "FeatureCollection", "features": features}
