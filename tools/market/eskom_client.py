"""Eskom operational data parser -- reads CSV exports from eskom.co.za/dataportal."""

from __future__ import annotations

import csv
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def _normalize_datetime(raw: str) -> Optional[str]:
    """Normalize datetime string to ``"YYYY-MM-DD HH:00"`` format."""
    if not raw or not raw.strip():
        return None
    s = raw.strip()
    # Expected: "YYYY-MM-DD HH:MM:SS" → "YYYY-MM-DD HH:00"
    if len(s) >= 16:
        return s[:14] + "00"
    return None


def _snake_case(name: str) -> str:
    """Convert column header to snake_case key."""
    s = name.strip()
    s = re.sub(r"[^\w\s]", "", s)
    s = re.sub(r"\s+", "_", s)
    return s.lower()


def _parse_csv(
    file_path: str,
    datetime_col: str,
) -> Dict[str, List[Tuple[str, float]]]:
    """Generic CSV parser that returns {column_key: [(datetime, value), ...]}."""
    result: Dict[str, List[Tuple[str, float]]] = {}
    try:
        if file_path.startswith("http://") or file_path.startswith("https://"):
            import io
            import requests
            resp = requests.get(file_path, timeout=30)
            resp.raise_for_status()
            f = io.StringIO(resp.content.decode("utf-8-sig"))
        else:
            f = open(file_path, newline="", encoding="utf-8-sig")
        with f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                return result

            value_cols = [c for c in reader.fieldnames if c != datetime_col]
            for col in value_cols:
                result[_snake_case(col)] = []

            for row in reader:
                dt = _normalize_datetime(row.get(datetime_col, ""))
                if dt is None:
                    continue

                has_any_value = False
                for col in value_cols:
                    raw = row.get(col, "")
                    if raw is None or str(raw).strip() == "":
                        continue
                    try:
                        val = float(raw)
                    except (ValueError, TypeError):
                        continue
                    has_any_value = True
                    result[_snake_case(col)].append((dt, val))

                # Skip rows where all value columns are empty (forecast placeholders)
                if not has_any_value:
                    continue

    except Exception as exc:
        logger.error("Failed to parse Eskom CSV %s: %s", file_path, exc)

    return result


def fetch_demand_observations(
    file_path: Optional[str] = None,
) -> Dict[str, List[Tuple[str, float]]]:
    """Parse System_hourly_actual_and_forecasted_demand.csv.

    Returns dict mapping column key to ``(datetime_str, value)`` tuples:
    ``"residual_forecast"``, ``"rsa_contracted_forecast"``,
    ``"residual_demand"``, ``"rsa_contracted_demand"``.
    """
    if file_path is None:
        try:
            import config
            cfg = getattr(config, "ESKOM", {})
            file_path = str(
                Path(cfg.get("data_dir", "data")) / cfg.get(
                    "demand_file",
                    "System_hourly_actual_and_forecasted_demand.csv",
                )
            )
        except ImportError:
            file_path = "data/System_hourly_actual_and_forecasted_demand.csv"

    return _parse_csv(file_path, "DateTimeKey")


def fetch_generation_observations(
    file_path: Optional[str] = None,
) -> Dict[str, List[Tuple[str, float]]]:
    """Parse Hourly_Generation.csv.

    Returns dict mapping column key to ``(datetime_str, value)`` tuples:
    ``"wind"``, ``"pv"``, ``"csp"``, ``"other_re"``.
    """
    if file_path is None:
        try:
            import config
            cfg = getattr(config, "ESKOM", {})
            file_path = str(
                Path(cfg.get("data_dir", "data")) / cfg.get(
                    "generation_file", "Hourly_Generation.csv"
                )
            )
        except ImportError:
            file_path = "data/Hourly_Generation.csv"

    return _parse_csv(file_path, "Date Time Hour Beginning")


def fetch_station_buildup_observations(
    file_path: Optional[str] = None,
) -> Dict[str, List[Tuple[str, float]]]:
    """Parse Station_Build_Up.csv.

    Returns dict mapping column key to ``(datetime_str, value)`` tuples
    for all generation-mix columns (thermal, nuclear, hydro, etc.).
    """
    if file_path is None:
        try:
            import config
            cfg = getattr(config, "ESKOM", {})
            file_path = str(
                Path(cfg.get("data_dir", "data")) / cfg.get(
                    "station_buildup_file", "Station_Build_Up.csv"
                )
            )
        except ImportError:
            file_path = "data/Station_Build_Up.csv"

    return _parse_csv(file_path, "Date_Time_Hour_Beginning")
