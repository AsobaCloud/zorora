"""Data session context builder for system prompt injection."""

from typing import Dict, Any


def build_data_system_context(session_data: Dict[str, Any]) -> str:
    """Build compact deterministic system context for active dataset session."""
    if not session_data or "df" not in session_data:
        return ""

    profile = session_data.get("profile", {})
    schema = session_data.get("schema", {})
    sample = session_data.get("sample", [])
    odse = session_data.get("odse", {})
    file_path = session_data.get("file_path", "")

    lines = []
    lines.append("Active dataset context:")
    if file_path:
        lines.append(f"- File: {file_path}")

    row_count = profile.get("row_count")
    column_count = profile.get("column_count")
    if row_count is not None and column_count is not None:
        lines.append(f"- Shape: {row_count} rows x {column_count} columns")

    if profile.get("time_range"):
        tr = profile["time_range"]
        lines.append(f"- Time range: {tr.get('start')} to {tr.get('end')}")

    if profile.get("resolution"):
        lines.append(f"- Resolution: {profile.get('resolution')}")

    if schema:
        lines.append("- Schema:")
        for col_name, dtype in list(schema.items())[:20]:
            lines.append(f"  - {col_name}: {dtype}")

    if sample:
        lines.append("- Sample rows:")
        for row in sample[:5]:
            lines.append(f"  - {row}")

    if odse and odse.get("detected"):
        lines.append("- ODS-E:")
        lines.append(f"  - OEM: {odse.get('type')}")
        lines.append(f"  - Transform applied: {odse.get('transformed', False)}")

    lines.append("- Available tools for this session:")
    lines.append("  - execute_analysis: run pandas/numpy/scipy/matplotlib against df")
    lines.append("  - nehanda_query: local policy retrieval")
    lines.append("  - web_search: current market/news context")
    lines.append("- Grounding rule: When combining policy + data, validate claims against dataset outputs.")
    return "\n".join(lines)
