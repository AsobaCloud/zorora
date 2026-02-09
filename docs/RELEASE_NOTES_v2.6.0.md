# Zorora v2.6.0 Release Notes

**Release Date:** February 2026  
**Previous Release:** v2.5-prod

---

## Major Features

### Web Research Session UX
- **Session Mode Transition** - After a research/news run starts producing results, the initial top search panel transitions out.
- **New Search Control** - Added `+ New Search` to return to a fresh search state.
- **Bottom-Docked Follow-Up Input** - ChatGPT-style follow-up composer fixed to the bottom of the viewport for ongoing discussion.
- **Discussion Panel** - Added an in-session discussion thread for iterative follow-ups on current research output.

### Follow-Up Chat APIs
- **Deep Research Chat Endpoint** - `POST /api/research/<research_id>/chat`
- **News Intel Chat Endpoint** - `POST /api/news-intel/chat`
- **Context-Grounded Responses** - Follow-up replies are generated from the current query/synthesis/source context.

### Streaming Chat Responses
- **SSE Streaming Mode** - Both chat endpoints now support incremental streaming via `stream=true`.
- **Progressive UI Rendering** - Frontend appends assistant output as chunks arrive for faster perceived response time.

### Source-Driven Discussion Shortcuts
- **Discuss This Source (Deep Research)** - Added quick action button on source cards.
- **Discuss This Source (News Intel)** - Added quick action button on filtered article cards.
- **Prompt Prefill** - Clicking quick action preloads structured follow-up in the chat input.

### News Intel + History UX Enhancements
- **News Intel Tab** - Topic/date-filtered newsroom synthesis in web UI without disrupting deep research flow.
- **Recent Research Controls** - Collapsible history panel with persisted collapsed state.
- **Bounded History Height** - Internal scroll prevents history from pushing results off-screen.
- **Update Indicator** - Displays history update badge while panel is collapsed.

---

## Architecture and Reliability Improvements

### Shared Deep Research Path
- Consolidated deep research execution into shared service for Web UI and REPL command paths.
- Standardized result payload shaping to reduce duplication and retrieval inconsistencies.

### Retrieval and Result Metadata
- **Reliable Research Fetching** - Web retrieval now prefers direct research ID lookup before fallback search.
- **Richer Source Metadata** - Added `publication_date` and `content_snippet` to result payloads for better source display/filtering.

### Runtime Warning Cleanup
- Replaced deprecated UTC usage with timezone-aware UTC date handling.
- Added explicit storage connection cleanup path to avoid sqlite resource warnings in test/runtime flows.

---

## Testing and Validation

- Added and expanded web API tests for:
  - research retrieval by ID and fallback behavior,
  - News Intel filtering/synthesis routes,
  - Deep Research chat endpoint,
  - News Intel chat endpoint,
  - streaming chat responses (SSE mode) for both chat routes.
- Existing regression suites for startup and REPL command processing continue to pass.

---

## Notable User-Facing Endpoints

### Existing
- `POST /api/research`
- `GET /api/research/<research_id>`
- `GET /api/research/history`
- `POST /api/news-intel/synthesize`

### New/Enhanced in v2.6.0
- `POST /api/research/<research_id>/chat` (with optional `stream=true`)
- `POST /api/news-intel/chat` (with optional `stream=true`)
- `POST /api/news-intel/articles`

---

## Upgrade Notes

- No breaking changes to existing research start/history endpoints.
- Web users should restart the server to load updated templates and chat/session UX.

---

**Full Changelog:** `git log v2.5-prod..HEAD`
