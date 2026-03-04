"""Market context builder for deep research synthesis prompt injection."""

from __future__ import annotations

from typing import Dict, List, Optional

from tools.market.series import GROUPS


def build_market_context(
    summaries: Dict[str, dict],
    correlations: Optional[Dict[str, object]] = None,
    max_chars: int = 2000,
) -> str:
    """Build a compact market data context block for synthesis prompts.

    Args:
        summaries: {series_id: {current, pct_30d, pct_90d, pct_1y, vol_30d}}
        correlations: optional {group: correlation_matrix_str}
        max_chars: hard cap on output length
    """
    if not summaries:
        return ""

    lines = ["[Market Data Context — FRED + yfinance]"]

    for group_name, series_list in GROUPS.items():
        group_lines: List[str] = []
        for s in series_list:
            info = summaries.get(s.series_id)
            if not info:
                continue
            current = info.get("current")
            if current is None:
                continue
            parts = [f"{s.label}: {current:.2f} {s.unit}"]
            for period, key in [("30d", "pct_30d"), ("90d", "pct_90d"), ("1Y", "pct_1y")]:
                pct = info.get(key)
                if pct is not None:
                    parts.append(f"{period}: {pct:+.1f}%")
            group_lines.append("  " + " | ".join(parts))

        if group_lines:
            lines.append(f"{group_name.title()}:")
            lines.extend(group_lines)

    # Notable correlations
    if correlations:
        corr_lines = []
        for group_name, matrix in correlations.items():
            if hasattr(matrix, "stack"):
                stacked = matrix.stack()
                # Keep only upper triangle, exclude self-correlations
                for (a, b), val in stacked.items():
                    if a < b and abs(val) >= 0.5:
                        corr_lines.append(f"  {a} / {b}: {val:.2f}")
        if corr_lines:
            lines.append("Notable correlations:")
            lines.extend(corr_lines[:8])

    text = "\n".join(lines)
    if len(text) > max_chars:
        text = text[:max_chars - 3] + "..."
    return text
