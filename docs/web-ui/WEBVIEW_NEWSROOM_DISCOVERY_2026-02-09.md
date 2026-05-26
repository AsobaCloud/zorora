# Web View Newsroom Discovery (2026-02-09)

## Context

This note captures a clarification from review: `~/Workbench/newsroom` is the producer repo for the AWS-deployed newsroom API. In Zorora, consuming newsroom content via API is the intended integration path.

## Key Discovery

The earlier concern that Zorora lacked path-based ingestion from `~/Workbench/newsroom` was too literal for this architecture.

- Correct model: `~/Workbench/newsroom` deploys the service; Zorora consumes that deployed API.
- Therefore, API integration is not a gap by itself.

## Evidence In Code

- Newsroom API endpoint is explicitly configured in `tools/research/newsroom.py`:
  - `NEWSROOM_API_URL` in `/Users/shingi/Workbench/zorora/tools/research/newsroom.py`
- Deep research source aggregation includes newsroom API fetch:
  - `fetch_newsroom_api(...)` used in `/Users/shingi/Workbench/zorora/workflows/deep_research/aggregator.py`
- Web view research flow uses deep-research aggregation and synthesis:
  - `/Users/shingi/Workbench/zorora/ui/web/app.py`

## What The Real Web UX Gaps Are

Given the clarified architecture, the opportunity is better newsroom surfacing in web UI, not alternative ingestion.

1. Newsroom relevance is weak for many natural queries
- API `search` parameter is only applied for single-word queries in `/Users/shingi/Workbench/zorora/tools/research/newsroom.py`.
- Most multi-word user queries become broad recency pulls, which can reduce relevance.

2. Newsroom context is not prominently surfaced in result UX
- Result cards render mixed source lists without newsroom-first grouping in `/Users/shingi/Workbench/zorora/ui/web/templates/index.html`.
- Source metadata shown is minimal (type + credibility), with limited newsroom-specific context.

3. Useful history capability exists but is not exposed in main web UX
- History API exists (`/api/research/history`) in `/Users/shingi/Workbench/zorora/ui/web/app.py`.
- Current page behavior does not present a dedicated recent-history view for quick newsroom revisit.

4. Reliability issue likely affects completed-result retrieval after SSE failure
- Fallback path uses `/api/research/<research_id>`.
- The retrieval path appears to search by `query` instead of `research_id` match semantics, risking misses.

## Practical Takeaway

No ingestion rewrite is needed to reflect `~/Workbench/newsroom`.

Focus should be on:
- stronger newsroom relevance handling,
- newsroom-first presentation affordances,
- and robust retrieval/history UX in the web view.

## Status

Documented only. No code changes made in this step.
