"""SAPP Day-Ahead Market price parser -- reads DAM xlsx exports from sappmarket.com."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def fetch_observations(
    file_path: str,
    currency: str = "usd",
) -> List[Tuple[str, float]]:
    """Parse a SAPP DAM xlsx file into (datetime_str, price) tuples.

    Args:
        file_path: Path to a DAM_*.xlsx file.
        currency: ``"usd"`` or ``"zar"``.

    Returns:
        Sorted list of ``("YYYY-MM-DD HH:00", price)`` tuples.
    """
    try:
        import openpyxl
    except ImportError:
        logger.error("openpyxl is required to parse SAPP DAM files")
        return []

    col_idx = 3 if currency.lower() == "usd" else 4  # 0-indexed

    try:
        wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
    except Exception as exc:
        logger.error("Failed to open SAPP DAM file %s: %s", file_path, exc)
        return []

    try:
        ws = wb["Data Export"]
    except KeyError:
        logger.error("Sheet 'Data Export' not found in %s", file_path)
        wb.close()
        return []

    observations: List[Tuple[str, float]] = []
    first = True
    for row in ws.iter_rows(values_only=True):
        if first:
            first = False
            continue  # skip header

        delivery_day = row[1]  # "YYYY/MM/DD"
        delivery_hour = row[2]  # "HH-HH"
        price = row[col_idx]

        if delivery_day is None or delivery_hour is None or price is None:
            continue

        day_str = str(delivery_day).replace("/", "-")
        hour_str = str(delivery_hour).split("-")[0] + ":00"
        dt = f"{day_str} {hour_str}"

        try:
            observations.append((dt, float(price)))
        except (ValueError, TypeError):
            continue

    wb.close()
    observations.sort(key=lambda x: x[0])
    return observations


def parse_all_dam_files(
    data_dir: Optional[str] = None,
) -> Dict[str, Dict[str, List[Tuple[str, float]]]]:
    """Parse all DAM xlsx files found in *data_dir*.

    Returns ``{node_key: {"usd": [...], "zar": [...]}}`` where *node_key*
    is one of ``"rsan"``, ``"rsas"``, ``"zim"``.
    """
    try:
        import config
        sapp_cfg = getattr(config, "SAPP", {})
    except ImportError:
        sapp_cfg = {}

    if data_dir is None:
        data_dir = sapp_cfg.get("data_dir", "data")

    dam_files = sapp_cfg.get("dam_files", {})
    if not dam_files:
        p = Path(data_dir)
        for f in p.glob("DAM_*.xlsx"):
            name = f.name.upper()
            if "RSAN" in name:
                dam_files["rsan"] = f.name
            elif "RSAS" in name:
                dam_files["rsas"] = f.name
            elif "ZIM" in name:
                dam_files["zim"] = f.name

    result: Dict[str, Dict[str, List[Tuple[str, float]]]] = {}
    for node, filename in dam_files.items():
        fpath = str(Path(data_dir) / filename)
        result[node] = {
            "usd": fetch_observations(fpath, currency="usd"),
            "zar": fetch_observations(fpath, currency="zar"),
        }

    return result
