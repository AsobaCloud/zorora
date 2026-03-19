"""GCCA (Grid Connection Capacity Assessment) GeoPackage parser.

Reads AREAS_GCCA2025.gpkg and returns GeoJSON FeatureCollections for
MTS substation zones, supply areas, and local areas.
"""

from __future__ import annotations

import logging
import sqlite3
import struct
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# GPKG binary geometry → GeoJSON
# ---------------------------------------------------------------------------

def _parse_gpkg_geometry(blob: bytes) -> Optional[dict]:
    """Parse GPKG binary geometry to a GeoJSON geometry object.

    Handles the GPKG header (magic, version, flags, srs_id, envelope)
    then decodes the embedded WKB geometry.
    """
    if not blob or len(blob) < 8:
        return None

    # GPKG header
    magic = blob[0:2]
    if magic != b"GP":
        logger.warning("Invalid GPKG magic: %s", magic)
        return None

    flags = blob[3]
    envelope_type = (flags >> 1) & 0x07

    envelope_sizes = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}
    env_size = envelope_sizes.get(envelope_type, 0)
    header_size = 8 + env_size

    if len(blob) < header_size + 5:
        return None

    wkb = blob[header_size:]
    return _parse_wkb(wkb)


def _parse_wkb(wkb: bytes) -> Optional[dict]:
    """Parse WKB geometry into a GeoJSON geometry object."""
    if len(wkb) < 5:
        return None

    wkb_byte_order = wkb[0]
    endian = "<" if wkb_byte_order == 1 else ">"
    wkb_type = struct.unpack_from(f"{endian}I", wkb, 1)[0]

    if wkb_type == 6:  # MultiPolygon
        return _parse_wkb_multipolygon(wkb, endian)
    elif wkb_type == 3:  # Polygon
        poly_coords = _parse_wkb_polygon_coords(wkb, 5, endian)
        if poly_coords is not None:
            return {"type": "MultiPolygon", "coordinates": [poly_coords[0]]}
    return None


def _parse_wkb_multipolygon(
    wkb: bytes, endian: str
) -> Optional[dict]:
    """Parse WKB MultiPolygon → GeoJSON MultiPolygon."""
    offset = 5
    num_polys = struct.unpack_from(f"{endian}I", wkb, offset)[0]
    offset += 4

    polygons: List[List[List[List[float]]]] = []

    for _ in range(num_polys):
        if offset + 5 > len(wkb):
            break
        # Each polygon has its own byte_order + type header
        poly_byte_order = wkb[offset]
        poly_endian = "<" if poly_byte_order == 1 else ">"
        offset += 5  # skip byte_order(1) + type(4)

        coords, offset = _parse_polygon_rings(wkb, offset, poly_endian)
        polygons.append(coords)

    return {"type": "MultiPolygon", "coordinates": polygons}


def _parse_polygon_rings(
    wkb: bytes, offset: int, endian: str
) -> Tuple[List[List[List[float]]], int]:
    """Parse polygon rings starting at offset. Returns (rings, new_offset)."""
    num_rings = struct.unpack_from(f"{endian}I", wkb, offset)[0]
    offset += 4

    rings: List[List[List[float]]] = []
    for _ in range(num_rings):
        num_points = struct.unpack_from(f"{endian}I", wkb, offset)[0]
        offset += 4

        ring: List[List[float]] = []
        for _ in range(num_points):
            x, y = struct.unpack_from(f"{endian}2d", wkb, offset)
            offset += 16
            ring.append([x, y])
        rings.append(ring)

    return rings, offset


def _parse_wkb_polygon_coords(
    wkb: bytes, offset: int, endian: str
) -> Optional[Tuple[List[List[List[float]]], int]]:
    """Parse a single WKB Polygon starting at offset."""
    try:
        return _parse_polygon_rings(wkb, offset, endian)
    except (struct.error, IndexError):
        return None


# ---------------------------------------------------------------------------
# GeoPackage layer loading
# ---------------------------------------------------------------------------

def _load_layer(
    gpkg_path: str,
    table_name: str,
    property_cols: List[str],
) -> dict:
    """Load a GeoPackage layer as a GeoJSON FeatureCollection."""
    try:
        conn = sqlite3.connect(gpkg_path)
    except Exception as exc:
        logger.error("Failed to open GeoPackage %s: %s", gpkg_path, exc)
        return {"type": "FeatureCollection", "features": []}

    col_list = ", ".join(property_cols)
    sql = f"SELECT {col_list}, geom FROM {table_name}"

    features: List[dict] = []
    try:
        for row in conn.execute(sql):
            props: Dict[str, Any] = {}
            for i, col in enumerate(property_cols):
                props[col] = row[i]

            geom_blob = row[len(property_cols)]
            geometry = _parse_gpkg_geometry(geom_blob) if geom_blob else None

            features.append({
                "type": "Feature",
                "properties": props,
                "geometry": geometry,
            })
    except Exception as exc:
        logger.error("Failed to read layer %s from %s: %s",
                      table_name, gpkg_path, exc)
    finally:
        conn.close()

    return {"type": "FeatureCollection", "features": features}


def _default_gpkg_path() -> str:
    try:
        import config
        cfg = getattr(config, "GCCA", {})
        return cfg.get("gpkg_path", "data/GCCA 2025 GIS/AREAS_GCCA2025.gpkg")
    except ImportError:
        return "data/GCCA 2025 GIS/AREAS_GCCA2025.gpkg"


def load_mts_zones(gpkg_path: Optional[str] = None) -> dict:
    """Load MTS (Main Transmission Substation) zones as GeoJSON.

    Returns a FeatureCollection with 159 features. Properties:
    ``objectid``, ``mts_1``, ``supplyarea``, ``localarea``, ``substation``.
    """
    if gpkg_path is None:
        gpkg_path = _default_gpkg_path()

    return _load_layer(
        gpkg_path,
        "MTS_ZONES_GCCA2025",
        ["objectid", "mts_1", "supplyarea", "localarea", "substation"],
    )


def load_supply_areas(gpkg_path: Optional[str] = None) -> dict:
    """Load supply areas as GeoJSON.

    Returns a FeatureCollection with 10 features. Properties:
    ``objectid``, ``supplyarea``.
    """
    if gpkg_path is None:
        gpkg_path = _default_gpkg_path()

    return _load_layer(
        gpkg_path,
        "SUPPLY_AREA_GCCA2025",
        ["objectid", "supplyarea"],
    )


def load_local_areas(gpkg_path: Optional[str] = None) -> dict:
    """Load local areas as GeoJSON.

    Returns a FeatureCollection with 34 features. Properties:
    ``objectid``, ``supplyarea``, ``localarea``.
    """
    if gpkg_path is None:
        gpkg_path = _default_gpkg_path()

    return _load_layer(
        gpkg_path,
        "LOCAL_AREA_GCCA2025",
        ["objectid", "supplyarea", "localarea"],
    )


# ---------------------------------------------------------------------------
# Substation point locations (from NTCSA Shapefiles-1.zip)
# ---------------------------------------------------------------------------

def _default_substations_path() -> str:
    try:
        import config
        cfg = getattr(config, "GCCA", {})
        return cfg.get(
            "substations_shp",
            "data/GCCA Shapefiles/Shapefiles/MTS_Subs2022.shp",
        )
    except ImportError:
        return "data/GCCA Shapefiles/Shapefiles/MTS_Subs2022.shp"


def load_substations(shp_path: Optional[str] = None) -> dict:
    """Load MTS substation point locations as GeoJSON FeatureCollection.

    Parses the MTS_Subs2022 shapefile (Point type, 198 records).
    Deduplicates by coordinates — multiple transformer records at the
    same point are aggregated into a single feature with a
    ``transformers`` list property.
    """
    if shp_path is None:
        shp_path = _default_substations_path()

    dbf_path = shp_path.rsplit(".", 1)[0] + ".dbf"

    # --- Read DBF fields and records ---
    try:
        dbf_fields, dbf_records = _read_dbf(dbf_path)
    except Exception as exc:
        logger.error("Failed to read substations DBF %s: %s", dbf_path, exc)
        return {"type": "FeatureCollection", "features": []}

    # --- Read SHP point coordinates ---
    try:
        points = _read_shp_points(shp_path)
    except Exception as exc:
        logger.error("Failed to read substations SHP %s: %s", shp_path, exc)
        return {"type": "FeatureCollection", "features": []}

    if len(points) != len(dbf_records):
        logger.warning(
            "SHP/DBF record count mismatch: %d points vs %d records",
            len(points), len(dbf_records),
        )

    # --- Deduplicate by coordinates, aggregating transformer data ---
    coord_map: Dict[Tuple[float, float], dict] = {}

    for i, (lon, lat) in enumerate(points):
        if i >= len(dbf_records):
            break
        rec = dbf_records[i]
        key = (round(lon, 6), round(lat, 6))

        transformer = {
            "voltage": rec.get("Transforme", ""),
            "size_mva": rec.get("TrfrSizeMV", ""),
            "count": rec.get("NoOfTrfrs", ""),
            "installed_mva": rec.get("InstalledT", ""),
            "status": rec.get("Status", ""),
        }

        if key not in coord_map:
            coord_map[key] = {
                "substation": rec.get("Substation", rec.get("Substati_1", "")),
                "supply_area": rec.get("Supply_Are", ""),
                "transformer_voltage": transformer["voltage"],
                "installed_capacity_mva": transformer["installed_mva"],
                "status": transformer["status"],
                "reippp_gen": rec.get("REIPPPGenA", ""),
                "transformers": [transformer],
                "lon": lon,
                "lat": lat,
            }
        else:
            coord_map[key]["transformers"].append(transformer)

    # --- Build GeoJSON ---
    features: List[dict] = []
    for (lon, lat), props in coord_map.items():
        feature_props = {
            "substation": props["substation"],
            "supply_area": props["supply_area"],
            "transformer_voltage": props["transformer_voltage"],
            "installed_capacity_mva": props["installed_capacity_mva"],
            "status": props["status"],
            "reippp_gen": props["reippp_gen"],
            "transformer_count": len(props["transformers"]),
            "transformers": props["transformers"],
        }
        features.append({
            "type": "Feature",
            "properties": feature_props,
            "geometry": {
                "type": "Point",
                "coordinates": [lon, lat],
            },
        })

    return {"type": "FeatureCollection", "features": features}


def _read_dbf(dbf_path: str) -> Tuple[List[Tuple[str, str, int]], List[Dict[str, str]]]:
    """Read a DBF file. Returns (fields, records)."""
    with open(dbf_path, "rb") as f:
        f.read(1)  # version
        f.read(3)  # date
        num_records = struct.unpack("<I", f.read(4))[0]
        header_size = struct.unpack("<H", f.read(2))[0]
        record_size = struct.unpack("<H", f.read(2))[0]
        f.seek(32)

        fields: List[Tuple[str, str, int]] = []
        while f.tell() < header_size - 1:
            chunk = f.read(32)
            if len(chunk) < 32 or chunk[0] == 0x0D:
                break
            name = chunk[:11].replace(b"\x00", b"").decode("ascii", errors="replace").strip()
            ftype = chr(chunk[11])
            flen = chunk[16]
            fields.append((name, ftype, flen))

        f.seek(header_size)
        records: List[Dict[str, str]] = []
        for _ in range(num_records):
            raw = f.read(record_size)
            if len(raw) < record_size:
                break
            offset = 1  # skip deletion flag
            rec: Dict[str, str] = {}
            for name, ftype, flen in fields:
                val = raw[offset:offset + flen].decode("ascii", errors="replace").strip()
                offset += flen
                rec[name] = val
            records.append(rec)

    return fields, records


def _read_shp_points(shp_path: str) -> List[Tuple[float, float]]:
    """Read point coordinates from a Point-type shapefile."""
    points: List[Tuple[float, float]] = []
    with open(shp_path, "rb") as f:
        f.seek(100)  # skip 100-byte header
        while True:
            header = f.read(8)
            if len(header) < 8:
                break
            _rec_num, content_len = struct.unpack(">II", header)
            content = f.read(content_len * 2)
            if len(content) < 20:
                break
            shape_type = struct.unpack("<I", content[0:4])[0]
            if shape_type == 1:  # Point
                x, y = struct.unpack("<dd", content[4:20])
                points.append((x, y))
    return points
