"""Load Dataset workflow — CSV ingest, ODS-E detection/mapping, profiling, session setup.

Stages:
  1. Ingest & Detect: read CSV, attempt ODS-E transform
  2. Profile & Contextualize: call profile_dataframe()
  3. Session Context Assembly: register df + metadata in session store
"""

import os
import re
import logging
import importlib.util
from typing import Dict, Tuple, Any, Optional

import pandas as pd

from tools.data_analysis.profiler import profile_dataframe
from tools.data_analysis import session

logger = logging.getLogger(__name__)

# Supported file extensions
_SUPPORTED_EXTENSIONS = {".csv"}

# OEM / ODS-E detection patterns
_OEM_PATTERNS = {
    "Huawei FusionSolar": re.compile(r"huawei|fusionsolar|string\s*id|device\s*sn", re.IGNORECASE),
    "Enphase": re.compile(r"enphase|envoy|microinverter", re.IGNORECASE),
    "Solarman": re.compile(r"INV\s*\d+|AC power \[W\]|P_AC|DC power|inverter|solarman", re.IGNORECASE),
    "SolarEdge": re.compile(r"solaredge|site id|optimizer", re.IGNORECASE),
    "Fronius": re.compile(r"fronius|datamanager|symo", re.IGNORECASE),
}

# Common timestamp column names
_TIMESTAMP_NAMES = {"timestamp", "ts", "datetime", "date", "time", "date_time"}

_CANONICAL_MAP = {
    "timestamp": ("timestamp", "ts", "datetime", "date_time", "date", "time"),
    "kwh": ("kwh", "energy_kwh", "yield_kwh", "total_kwh", "production_kwh"),
    "power_w": ("power_w", "ac_power", "p_ac", "power", "kw", "watt", "watts"),
    "energy": ("energy", "energy_wh", "energy_kwh", "yield"),
    "error_type": ("error_type", "status", "alarm", "fault", "state", "event"),
}


class LoadDatasetWorkflow:
    """Three-stage workflow: ingest, profile, register."""

    def __init__(self, session_store=None):
        """Initialize workflow.

        Args:
            session_store: Optional override for the session module (testing).
        """
        self._session = session_store or session

    def execute(self, file_path: str, session_id: str = "", confirm_mapping: bool = False) -> str:
        """Load a dataset file and prepare it for analysis.

        Args:
            file_path: Path to the data file (CSV).
            session_id: Session ID for the session store.
            confirm_mapping: Apply suggested canonical mapping if available.

        Returns:
            Formatted summary string, or "Error: ..." on failure.
        """
        # --- Validate ---
        if not file_path or not file_path.strip():
            return "Error: No file path provided. Usage: /load <path>"

        file_path = file_path.strip()

        if not os.path.exists(file_path):
            return f"Error: File not found — {file_path}"

        ext = os.path.splitext(file_path)[1].lower()
        if ext not in _SUPPORTED_EXTENSIONS:
            return f"Error: Unsupported file type '{ext}'. Supported: {', '.join(_SUPPORTED_EXTENSIONS)}"

        # --- Stage 1: Ingest & Detect ---
        try:
            df = pd.read_csv(file_path)
        except Exception as e:
            return f"Error: Failed to read CSV — {e}"

        # Drop fully empty rows
        df = df.dropna(how="all")

        # Auto-detect and parse timestamp columns
        df = self._parse_timestamps(df)

        # ODS-E detection
        odse_info = self._detect_odse(df)
        transform_result = self._try_odse_transform(df, file_path, odse_info)
        if transform_result["applied"] and transform_result["dataframe"] is not None:
            df = transform_result["dataframe"]
            odse_info["transformed"] = True
            odse_info["transform_source"] = transform_result["source"]
            odse_info["mapped_columns"] = transform_result["mapped_columns"]
        else:
            odse_info["transformed"] = False
            odse_info["transform_source"] = None
            odse_info["mapped_columns"] = []

        suggested_mapping = self._suggest_column_mapping(df)
        mapping_applied = False
        if suggested_mapping and confirm_mapping:
            df, mapping_applied = self._apply_mapping(df, suggested_mapping)

        # --- Stage 2: Profile & Contextualize ---
        profile = profile_dataframe(df)

        # --- Stage 3: Session Context Assembly ---
        schema = {col: str(df[col].dtype) for col in df.columns}
        sample = df.head(5).to_dict(orient="records")

        self._session.set_df(
            df,
            session_id=session_id,
            profile=profile,
            schema=schema,
            sample=sample,
            file_path=file_path,
            odse=odse_info,
            suggested_mapping=suggested_mapping,
            mapping_applied=mapping_applied,
        )

        # --- Format summary ---
        return self._format_summary(
            profile,
            odse_info,
            file_path,
            df,
            suggested_mapping=suggested_mapping,
            mapping_applied=mapping_applied,
            confirm_mapping=confirm_mapping,
        )

    def _parse_timestamps(self, df: pd.DataFrame) -> pd.DataFrame:
        """Auto-detect and parse timestamp columns."""
        for col in df.columns:
            if col.lower().strip() in _TIMESTAMP_NAMES:
                try:
                    df[col] = pd.to_datetime(df[col], errors="coerce")
                    logger.info(f"Parsed timestamp column: {col}")
                except Exception:
                    pass
        return df

    def _detect_odse(self, df: pd.DataFrame) -> dict:
        """Detect likely OEM/ODS-E compatible format from column names."""
        matches: Dict[str, list] = {}
        for col in df.columns:
            for oem, pattern in _OEM_PATTERNS.items():
                if pattern.search(str(col)):
                    matches.setdefault(oem, []).append(col)

        if not matches:
            return {"detected": False, "columns": [], "type": None}

        oem = sorted(matches.items(), key=lambda kv: len(kv[1]), reverse=True)[0][0]
        return {
            "detected": True,
            "columns": matches[oem],
            "type": oem,
        }

    def _try_odse_transform(self, df: pd.DataFrame, file_path: str, odse_info: dict) -> Dict[str, Any]:
        """Attempt ODS-E transform through odse package if detected OEM format."""
        if not odse_info.get("detected"):
            return {"applied": False, "dataframe": None, "source": None, "mapped_columns": []}

        try:
            if importlib.util.find_spec("odse") is None:
                logger.debug("ODS-E package not installed, using raw data")
                return {"applied": False, "dataframe": None, "source": None, "mapped_columns": []}

            import odse
            logger.info("ODS-E package found, attempting transform")

            candidates = [
                ("auto_transform", getattr(odse, "auto_transform", None)),
                ("transform_csv", getattr(odse, "transform_csv", None)),
                ("transform", getattr(odse, "transform", None)),
                ("convert", getattr(odse, "convert", None)),
            ]

            for source_name, fn in candidates:
                if not callable(fn):
                    continue
                transformed = fn(file_path)
                transformed_df = self._extract_dataframe_from_transform(transformed)
                if transformed_df is not None and not transformed_df.empty:
                    return {
                        "applied": True,
                        "dataframe": transformed_df,
                        "source": source_name,
                        "mapped_columns": list(transformed_df.columns),
                    }
        except Exception as e:
            logger.warning(f"ODS-E transform failed, using raw data: {e}")
        return {"applied": False, "dataframe": None, "source": None, "mapped_columns": []}

    def _extract_dataframe_from_transform(self, transformed: Any) -> Optional[pd.DataFrame]:
        """Extract DataFrame from different possible odse return formats."""
        if isinstance(transformed, pd.DataFrame):
            return transformed
        if isinstance(transformed, dict):
            for key in ("dataframe", "df", "data"):
                value = transformed.get(key)
                if isinstance(value, pd.DataFrame):
                    return value
        if isinstance(transformed, tuple):
            for part in transformed:
                if isinstance(part, pd.DataFrame):
                    return part
        return None

    def _suggest_column_mapping(self, df: pd.DataFrame) -> Dict[str, str]:
        """Suggest canonical mappings for generic labelled CSVs."""
        mapping: Dict[str, str] = {}
        used_targets = set()

        for col in df.columns:
            normalized = re.sub(r"[^a-z0-9]+", "_", str(col).lower()).strip("_")
            for canonical, aliases in _CANONICAL_MAP.items():
                if canonical in used_targets:
                    continue
                if normalized == canonical or any(alias in normalized for alias in aliases):
                    mapping[str(col)] = canonical
                    used_targets.add(canonical)
                    break

        has_timestamp = "timestamp" in mapping.values() or any(
            str(c).lower().strip() in _TIMESTAMP_NAMES for c in df.columns
        )
        has_energy_or_power = any(v in {"kwh", "power_w", "energy"} for v in mapping.values())
        if not (has_timestamp and has_energy_or_power):
            return {}
        return mapping

    def _apply_mapping(self, df: pd.DataFrame, mapping: Dict[str, str]) -> Tuple[pd.DataFrame, bool]:
        """Apply user-confirmed mapping to dataframe columns."""
        if not mapping:
            return df, False
        renamed = df.rename(columns=mapping)
        return renamed, True

    def _format_summary(self, profile: dict, odse_info: dict,
                        file_path: str, df: pd.DataFrame,
                        suggested_mapping: Dict[str, str],
                        mapping_applied: bool,
                        confirm_mapping: bool) -> str:
        """Format a human-readable summary of the loaded dataset."""
        lines = []
        lines.append(f"## Dataset Loaded: {os.path.basename(file_path)}")
        lines.append("")

        # Shape
        lines.append(f"**Rows:** {profile['row_count']:,}")
        lines.append(f"**Columns:** {profile['column_count']}")
        lines.append("")

        # Columns
        lines.append("**Column Summary:**")
        for col in profile["columns"]:
            null_info = f" ({col['null_pct']:.1f}% null)" if col["null_count"] > 0 else ""
            lines.append(f"  - `{col['name']}` ({col['dtype']}){null_info}")
        lines.append("")

        # Time range
        if profile["time_range"]:
            tr = profile["time_range"]
            lines.append(f"**Time Range:** {tr['start']} → {tr['end']} ({tr['span_days']} days)")

        # Resolution
        if profile["resolution"]:
            lines.append(f"**Resolution:** {profile['resolution']}")

        # Gaps
        if profile["gaps"]:
            lines.append(f"**Gaps Detected:** {len(profile['gaps'])}")
            for gap in profile["gaps"][:5]:  # Show first 5
                lines.append(f"  - {gap['start']} → {gap['end']} ({gap['duration']})")
            if len(profile["gaps"]) > 5:
                lines.append(f"  - ... and {len(profile['gaps']) - 5} more")
        lines.append("")

        # Numeric summary
        if profile["numeric_summary"]:
            lines.append("**Numeric Summary:**")
            for col_name, stats in profile["numeric_summary"].items():
                if stats["min"] is not None:
                    lines.append(
                        f"  - `{col_name}`: min={stats['min']:.2f}, "
                        f"max={stats['max']:.2f}, mean={stats['mean']:.2f}, "
                        f"zeros={stats['zeros_pct']:.1f}%"
                    )
            lines.append("")

        # ODS-E info
        if odse_info["detected"]:
            lines.append(f"**Detected OEM Format:** {odse_info['type']}")
            lines.append(f"**ODS-E Compatible Columns:** {len(odse_info['columns'])}")
            for col in odse_info["columns"]:
                lines.append(f"  - `{col}`")
            if odse_info.get("transformed"):
                lines.append(f"**ODS-E Transform:** Applied via `{odse_info.get('transform_source')}`")
                lines.append(f"**Transformed Columns:** {len(odse_info.get('mapped_columns', []))}")
            else:
                lines.append("**ODS-E Transform:** Not applied (using raw DataFrame)")
            lines.append("")

        # Generic mapping flow
        if suggested_mapping:
            lines.append("**Suggested Canonical Mapping:**")
            for source_col, canonical in suggested_mapping.items():
                lines.append(f"  - `{source_col}` → `{canonical}`")
            if mapping_applied:
                lines.append("**Mapping Status:** Applied")
            elif confirm_mapping:
                lines.append("**Mapping Status:** No mapping applied")
            else:
                lines.append("**Mapping Status:** Pending confirmation")
                lines.append("Run `/load --confirm-map <path>` to apply this mapping.")
            lines.append("")

        lines.append("Dataset ready for analysis. Try: `df.describe()`, `df.head()`, or ask a question.")

        return "\n".join(lines)
