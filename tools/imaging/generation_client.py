"""Renewable generation workbook loader for GEM Africa Energy Tracker."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Iterable, Optional
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import config

logger = logging.getLogger(__name__)

_NS = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "pkgrel": "http://schemas.openxmlformats.org/package/2006/relationships",
}

_RENEWABLE_SHEETS = {
    "Solar": "solar",
    "Wind": "wind",
    "Hydropower": "hydropower",
    "Bioenergy": "bioenergy",
    "Geothermal": "geothermal",
}

_STATUS_PRIORITY = [
    "operating",
    "construction",
    "mothballed",
    "pre-construction",
    "permitted",
    "pre-permit",
    "announced",
    "shelved",
    "shelved - inferred 2 y",
    "cancelled",
    "cancelled - inferred 4 y",
    "retired",
]


def _col_to_idx(ref: str) -> int:
    letters = "".join(ch for ch in ref if ch.isalpha())
    value = 0
    for ch in letters:
        value = (value * 26) + (ord(ch.upper()) - 64)
    return value - 1


def _cell_text(cell, shared_strings: list[str]) -> str:
    cell_type = cell.attrib.get("t")
    value_el = cell.find("main:v", _NS)
    if cell_type == "s" and value_el is not None:
        idx = int(value_el.text)
        return shared_strings[idx] if idx < len(shared_strings) else ""
    if cell_type == "inlineStr":
        inline = cell.find("main:is", _NS)
        if inline is None:
            return ""
        return "".join(part.text or "" for part in inline.iterfind(".//main:t", _NS))
    return value_el.text if value_el is not None and value_el.text is not None else ""


def _load_shared_strings(zf: ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []
    root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    values = []
    for si in root.findall("main:si", _NS):
        values.append("".join(part.text or "" for part in si.iterfind(".//main:t", _NS)))
    return values


def _resolve_sheet_targets(zf: ZipFile) -> Dict[str, str]:
    wb = ET.fromstring(zf.read("xl/workbook.xml"))
    rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    relmap = {
        rel.attrib["Id"]: rel.attrib["Target"]
        for rel in rels.findall("pkgrel:Relationship", _NS)
    }
    targets = {}
    for sheet in wb.findall("main:sheets/main:sheet", _NS):
        name = sheet.attrib["name"]
        rel_id = sheet.attrib[
            "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
        ]
        target = relmap.get(rel_id, "")
        if target and not target.startswith("xl/"):
            target = f"xl/{target}"
        if target:
            targets[name] = target
    return targets


def _iter_sheet_rows(zf: ZipFile, sheet_target: str, shared_strings: list[str]):
    root = ET.fromstring(zf.read(sheet_target))
    rows = root.findall("main:sheetData/main:row", _NS)
    if not rows:
        return

    header_map: Dict[int, str] = {}
    for cell in rows[0].findall("main:c", _NS):
        header_map[_col_to_idx(cell.attrib["r"])] = _cell_text(cell, shared_strings)

    max_idx = max(header_map) if header_map else -1
    headers = [header_map.get(i, "") for i in range(max_idx + 1)]
    for row in rows[1:]:
        values = {}
        for cell in row.findall("main:c", _NS):
            values[_col_to_idx(cell.attrib["r"])] = _cell_text(cell, shared_strings)
        yield {
            header: values.get(idx, "")
            for idx, header in enumerate(headers)
            if header
        }


def _pick(row: dict, *headers: str) -> str:
    for header in headers:
        value = str(row.get(header, "") or "").strip()
        if value:
            return value
    return ""


def _to_float(value: str) -> Optional[float]:
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _resolve_status(statuses: Iterable[str]) -> str:
    normalized = {str(status).strip().lower() for status in statuses if str(status).strip()}
    for candidate in _STATUS_PRIORITY:
        if candidate in normalized:
            return candidate
    return sorted(normalized)[0] if normalized else ""


def _default_bbox() -> list:
    img_config = getattr(config, "IMAGING", {})
    return img_config.get("mrds_bbox", [15, -35, 40, -15])


def _in_bbox(lat: float, lon: float, bbox: list) -> bool:
    lon_min, lat_min, lon_max, lat_max = bbox
    return lon_min <= lon <= lon_max and lat_min <= lat <= lat_max


def _default_workbook_path() -> Optional[Path]:
    img_config = getattr(config, "IMAGING", {})
    configured = str(img_config.get("generation_workbook_path", "") or "").strip()
    if configured:
        candidate = Path(configured).expanduser()
        return candidate if candidate.exists() else None

    data_dir = Path(__file__).resolve().parents[2] / "data"
    candidates = sorted(data_dir.glob("Africa-Energy-Tracker-*.xlsx"))
    return candidates[-1] if candidates else None


def load_generation_assets(
    workbook_path: Optional[str] = None,
    bbox: Optional[list] = None,
) -> dict:
    """Load renewable generation assets from the GEM Africa Energy Tracker workbook."""
    bbox = bbox or _default_bbox()
    workbook = Path(workbook_path).expanduser() if workbook_path else _default_workbook_path()
    if workbook is None or not workbook.exists():
        logger.warning("Generation workbook not found: %s", workbook_path or "<auto>")
        return {"type": "FeatureCollection", "features": []}

    try:
        with ZipFile(workbook) as zf:
            shared_strings = _load_shared_strings(zf)
            sheet_targets = _resolve_sheet_targets(zf)
            aggregated: Dict[str, dict] = {}

            for sheet_name, technology in _RENEWABLE_SHEETS.items():
                sheet_target = sheet_targets.get(sheet_name)
                if not sheet_target:
                    continue

                for row in _iter_sheet_rows(zf, sheet_target, shared_strings) or []:
                    lat = _to_float(_pick(row, "Latitude"))
                    lon = _to_float(_pick(row, "Longitude"))
                    if lat is None or lon is None or not _in_bbox(lat, lon, bbox):
                        continue

                    name = _pick(row, "Project Name", "Plant name")
                    location_id = _pick(row, "GEM location ID")
                    phase_name = _pick(row, "Phase Name", "Unit Name") or "--"
                    site_id = f"{technology}:{location_id or f'{name}:{lat}:{lon}'}"
                    capacity = _to_float(_pick(row, "Capacity (MW)", "Unit Capacity (MW)")) or 0.0

                    record = aggregated.setdefault(
                        site_id,
                        {
                            "type": "Feature",
                            "geometry": {"type": "Point", "coordinates": [lon, lat]},
                            "properties": {
                                "site_id": site_id,
                                "gem_location_id": location_id,
                                "name": name,
                                "technology": technology,
                                "capacity_mw": 0.0,
                                "status": "",
                                "operator": _pick(row, "Operator", "Operator(s)"),
                                "owner": _pick(row, "Owner", "Owner(s)"),
                                "country": _pick(row, "Country/Area", "Country/Area 1"),
                                "location_accuracy": _pick(row, "Location accuracy", "Location Accuracy"),
                                "source_sheet": sheet_name,
                                "wiki_url": _pick(row, "Wiki URL"),
                                "unit_count": 0,
                                "phase_names": set(),
                                "statuses": set(),
                            },
                        },
                    )

                    props = record["properties"]
                    props["capacity_mw"] += capacity
                    props["unit_count"] += 1
                    props["phase_names"].add(phase_name)
                    status = _pick(row, "Status")
                    if status:
                        props["statuses"].add(status)
                    if not props.get("operator"):
                        props["operator"] = _pick(row, "Operator", "Operator(s)")
                    if not props.get("owner"):
                        props["owner"] = _pick(row, "Owner", "Owner(s)")
                    if not props.get("wiki_url"):
                        props["wiki_url"] = _pick(row, "Wiki URL")
                    if not props.get("location_accuracy"):
                        props["location_accuracy"] = _pick(row, "Location accuracy", "Location Accuracy")

            features = []
            for feature in aggregated.values():
                props = feature["properties"]
                props["status"] = _resolve_status(props["statuses"])
                props["phase_names"] = sorted(props["phase_names"])
                props["statuses"] = sorted(props["statuses"])
                props["capacity_mw"] = round(float(props["capacity_mw"]), 3)
                features.append(feature)

            features.sort(
                key=lambda feat: (
                    feat["properties"].get("technology", ""),
                    feat["properties"].get("country", ""),
                    feat["properties"].get("name", ""),
                )
            )
            logger.info("Loaded %d generation assets from %s", len(features), workbook)
            return {"type": "FeatureCollection", "features": features}
    except Exception as exc:
        logger.error("Failed to load generation workbook %s: %s", workbook, exc, exc_info=True)
        return {"type": "FeatureCollection", "features": []}
