"""Data profiler — pure pandas analysis of DataFrame structure and content.

Returns a structured dict with shape, time range, resolution, gaps,
numeric summaries, and df.describe() output.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, List


def profile_dataframe(df: pd.DataFrame) -> Dict[str, Any]:
    """Profile a DataFrame and return structured metadata.

    Returns dict with keys:
        row_count, column_count, columns (list of col info dicts),
        time_range (start/end/span_days or None),
        resolution (e.g. "30min" or None),
        gaps (list of {start, end, duration}),
        numeric_summary (per-column min/max/mean/std/zeros_pct),
        describe (df.describe().to_dict())
    """
    if df.empty and len(df.columns) == 0:
        return {
            "row_count": 0,
            "column_count": 0,
            "columns": [],
            "time_range": None,
            "resolution": None,
            "gaps": [],
            "numeric_summary": {},
            "describe": {},
        }

    row_count = len(df)
    column_count = len(df.columns)

    # Column info
    columns_info = []
    for col in df.columns:
        null_count = int(df[col].isnull().sum())
        null_pct = (null_count / row_count * 100) if row_count > 0 else 0.0
        columns_info.append({
            "name": col,
            "dtype": str(df[col].dtype),
            "null_count": null_count,
            "null_pct": round(null_pct, 2),
        })

    # Find datetime column
    dt_col = _find_datetime_column(df)

    # Time range
    time_range = None
    if dt_col is not None:
        ts = df[dt_col].dropna().sort_values()
        if len(ts) > 0:
            start = ts.iloc[0]
            end = ts.iloc[-1]
            span = end - start
            time_range = {
                "start": str(start),
                "end": str(end),
                "span_days": round(span.total_seconds() / 86400, 2),
            }

    # Resolution
    resolution = _infer_resolution(df, dt_col)

    # Gaps
    gaps = _detect_gaps(df, dt_col)

    # Numeric summary
    numeric_summary = {}
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    for col in numeric_cols:
        series = df[col].dropna()
        if len(series) == 0:
            numeric_summary[col] = {
                "min": None, "max": None, "mean": None,
                "std": None, "zeros_pct": 0.0,
            }
        else:
            zeros = (series == 0).sum()
            numeric_summary[col] = {
                "min": float(series.min()),
                "max": float(series.max()),
                "mean": float(series.mean()),
                "std": float(series.std()) if len(series) > 1 else 0.0,
                "zeros_pct": round(zeros / len(df) * 100, 2),
            }

    # Describe
    try:
        describe = df.describe().to_dict()
    except Exception:
        describe = {}

    return {
        "row_count": row_count,
        "column_count": column_count,
        "columns": columns_info,
        "time_range": time_range,
        "resolution": resolution,
        "gaps": gaps,
        "numeric_summary": numeric_summary,
        "describe": describe,
    }


def _find_datetime_column(df: pd.DataFrame) -> Optional[str]:
    """Find the first datetime column in the DataFrame."""
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            return col
    # Try parsing common timestamp column names
    for col in df.columns:
        if col.lower() in ("timestamp", "ts", "datetime", "date", "time"):
            try:
                parsed = pd.to_datetime(df[col], errors="coerce")
                if parsed.notna().sum() > len(df) * 0.5:
                    return col
            except Exception:
                pass
    return None


def _infer_resolution(df: pd.DataFrame, dt_col: Optional[str]) -> Optional[str]:
    """Infer time series resolution from datetime column."""
    if dt_col is None:
        return None

    ts = df[dt_col].dropna().sort_values()
    if len(ts) < 2:
        return None

    diffs = ts.diff().dropna()
    if len(diffs) == 0:
        return None

    # Try pandas infer_freq first
    try:
        freq = pd.infer_freq(ts)
        if freq:
            return freq
    except (ValueError, TypeError):
        pass

    # Fall back to median diff
    median_diff = diffs.median()
    total_seconds = median_diff.total_seconds()

    if total_seconds <= 0:
        return "irregular"

    # Map to human-readable
    if abs(total_seconds - 900) < 60:
        return "15min"
    elif abs(total_seconds - 1800) < 60:
        return "30min"
    elif abs(total_seconds - 3600) < 60:
        return "60min"
    elif abs(total_seconds - 86400) < 3600:
        return "1day"
    else:
        minutes = int(total_seconds / 60)
        return f"{minutes}min"


def _detect_gaps(df: pd.DataFrame, dt_col: Optional[str]) -> List[Dict[str, str]]:
    """Detect gaps in time series that exceed 2x the median interval."""
    if dt_col is None:
        return []

    ts = df[dt_col].dropna().sort_values()
    if len(ts) < 3:
        return []

    diffs = ts.diff().dropna()
    median_diff = diffs.median()

    if median_diff.total_seconds() <= 0:
        return []

    threshold = median_diff * 2
    gaps = []

    for i in range(1, len(ts)):
        diff = ts.iloc[i] - ts.iloc[i - 1]
        if diff > threshold:
            gaps.append({
                "start": str(ts.iloc[i - 1]),
                "end": str(ts.iloc[i]),
                "duration": str(diff),
            })

    return gaps
