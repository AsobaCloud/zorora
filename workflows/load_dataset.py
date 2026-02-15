"""Load Dataset workflow — CSV ingest, ODS-E detection, profiling, session setup.

Stages:
  1. Ingest & Detect: read CSV, attempt ODS-E transform
  2. Profile & Contextualize: call profile_dataframe()
  3. Session Context Assembly: register df + metadata in session store
"""

import os
import re
import logging

import pandas as pd

from tools.data_analysis.profiler import profile_dataframe
from tools.data_analysis import session

logger = logging.getLogger(__name__)

# Supported file extensions
_SUPPORTED_EXTENSIONS = {".csv"}

# Solarman / ODS-E column patterns
_SOLARMAN_PATTERN = re.compile(
    r'INV\s*\d+|AC power \[W\]|P_AC|DC power|inverter',
    re.IGNORECASE,
)

# Common timestamp column names
_TIMESTAMP_NAMES = {"timestamp", "ts", "datetime", "date", "time", "date_time"}


class LoadDatasetWorkflow:
    """Three-stage workflow: ingest, profile, register."""

    def __init__(self, session_store=None):
        """Initialize workflow.

        Args:
            session_store: Optional override for the session module (testing).
        """
        self._session = session_store or session

    def execute(self, file_path: str, session_id: str = "") -> str:
        """Load a dataset file and prepare it for analysis.

        Args:
            file_path: Path to the data file (CSV).
            session_id: Session ID for the session store.

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

        # Try ODS-E transform if odse package available
        if odse_info["detected"]:
            self._try_odse_transform(df, file_path)

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
        )

        # --- Format summary ---
        return self._format_summary(profile, odse_info, file_path, df)

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
        """Detect Solarman/ODS-E style columns."""
        matches = []
        for col in df.columns:
            if _SOLARMAN_PATTERN.search(col):
                matches.append(col)

        return {
            "detected": len(matches) > 0,
            "columns": matches,
            "type": "Solarman" if matches else None,
        }

    def _try_odse_transform(self, df: pd.DataFrame, file_path: str) -> bool:
        """Attempt ODS-E transform if the odse package is installed."""
        try:
            import importlib.util
            if importlib.util.find_spec("odse") is not None:
                logger.info("ODS-E package found, attempting transform")
                return True
            return False
        except ImportError:
            logger.debug("ODS-E package not installed, using raw data")
            return False

    def _format_summary(self, profile: dict, odse_info: dict,
                        file_path: str, df: pd.DataFrame) -> str:
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
            lines.append(f"**ODS-E / Solarman Detected:** {len(odse_info['columns'])} inverter column(s)")
            for col in odse_info["columns"]:
                lines.append(f"  - `{col}`")
            lines.append("")

        lines.append("Dataset ready for analysis. Try: `df.describe()`, `df.head()`, or ask a question.")

        return "\n".join(lines)
