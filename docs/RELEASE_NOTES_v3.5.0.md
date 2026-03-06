# Zorora v3.5.0 Release Notes

**Release Date:** March 6, 2026  
**Previous Release:** v3.0.0-prod  
**Commit Range:** `v3.0.0-prod..df39e22`

---

## Major Features

### Licensing Update

Zorora moved from Apache 2.0 to a dual-license model:

- **AGPLv3+** for open-source use
- **Commercial licensing** via AsobaCloud for organizations that want to commercialize without AGPL reciprocity obligations

### Deep Research Reliability Upgrade

Deep research was upgraded from a functional pipeline to a contract-driven synthesis system tuned for energy/electricity market research.

- **Intent-first research flow** - refined research intent feeds decomposition and source routing
- **Parallel multi-source retrieval** - Brave + newsroom + academic/structured sources
- **Ranked evidence contract** - evidence prioritized by relevance first, then credibility
- **Two-stage synthesis hardening** - outline generation + section expansion with strict quality gates
- **No raw evidence-dump fallback** - fallback now returns structured synthesis or explicit insufficiency statements

### Search Surface Expansion (SEP-031, SEP-032)

- Added six additional deep-research search surfaces in the retrieval layer
- Added structured data/academic connectors:
  - CrossRef
  - arXiv
  - World Bank
- Added local caching/data plumbing for structured source retrieval paths

### Market Intelligence Enhancements (SEP-021 + follow-ons)

- Added market data integrations including renewable/metals/ETF proxy support
- Added market context injection into synthesis path for market-intent queries
- Improved deterministic section writing to prefer credibility-ranked evidence excerpts

### Synthesis Quality and Fallback Controls

- Cold-start-aware retries for hosted reasoning endpoints
- Outline quality gates now reject generic scaffolds and source-headline style sections
- Section quality gates reject generic report narration even when citations exist
- Deterministic fallback sections now preserve answer structure and inline citations
- Explicit insufficiency path when usable evidence is unavailable

---

## Architecture Changes

### Shared Deep Research Path Hardened

`engine/deep_research_service.py` remains the shared execution path for web and REPL deep research, but the synthesis contract is substantially tighter:

1. Intent refinement
2. Intent decomposition into parallel searches
3. Multi-source aggregation
4. Relevance/credibility ranking
5. Cross-reference finding extraction
6. Two-stage synthesis with gating/retry/fallback controls

### Deep Research Synthesis Contract

`workflows/deep_research/synthesizer.py` now enforces:

- Outline admissibility checks (generic scaffold rejection)
- Section admissibility checks (answer-first + causal link + inline citations)
- Retry-before-fallback behavior for both outline and section generation
- Deterministic evidence-outline fallback instead of raw evidence list dumping

---

## Workflow and UX Improvements

- Two-column research layout and persistent history panel improvements carried forward
- Follow-up/discuss flows remain grounded in retrieved source context
- Deep research progress and provenance reporting improved (`reasoning`, `mixed`, `deterministic`)

---

## CI, Tests, and Validation

Since `v3.0.0-prod`, project testing and CI coverage for deep research and integration paths expanded materially.

Current validation snapshot used for this release cycle:

- `ruff check` on changed deep-research docs/code paths
- Deep research and shared-path regression suites passing (`130` tests in target suites at release time)
- Live benchmark runs across energy/electricity queries validating:
  - structured synthesis output
  - inline citations
  - no raw dump fallback behavior

---

## Upgrade Notes

- **Fallback behavior changed:** raw `Evidence Highlights` dump-style synthesis is removed from the deep-research contract path
- **Stricter synthesis gating:** generic model prose that previously slipped through is now rejected more aggressively
- **More source adapters:** retrieval breadth and runtime variability can increase when external APIs throttle or timeout

---

## Statistics (Since v3.0.0-prod)

- **Commits:** 58
- **Files changed:** 93
- **Lines added:** 13,057
- **Lines removed:** 1,447
- **SEPs covered in this range:** `SEP-001` through `SEP-032` (non-contiguous milestones)

---

**Full Changelog:** `git log v3.0.0-prod..df39e22 --oneline`
