"""Tool-callable wrapper for market data — registered in tools/registry.py."""

from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)


def get_market_summary(group: str = "all") -> str:
    """Return JSON market summary for a group (or all groups).

    Fetches fresh data if stale, computes summary stats, returns JSON string.
    """
    try:
        from workflows.market_workflow import MarketWorkflow

        wf = MarketWorkflow()
        wf.update_all() if group == "all" else wf.update_group(group)
        summaries = wf.compute_summary()

        if group != "all":
            from tools.market.series import get_series_by_group
            group_ids = {s.series_id for s in get_series_by_group(group)}
            summaries = {k: v for k, v in summaries.items() if k in group_ids}

        return json.dumps(summaries, indent=2, default=str)
    except Exception as exc:
        logger.error("get_market_summary failed: %s", exc)
        return json.dumps({"error": str(exc)})
