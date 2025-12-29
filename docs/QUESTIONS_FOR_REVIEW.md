# Questions & Clarifications for Deep Research Implementation

## CRITICAL: Please answer ALL questions before development begins

---

## Phase 1: Tool Registry Refactor

### Q1.1: Existing `research_workflow.py` Conflict
**Issue:** The plan calls for creating new research tools, but there's already a `research_workflow.py` file that implements a research workflow (newsroom + web + synthesis).

**Question:** 
- Should I **replace** the existing `ResearchWorkflow` class entirely with the new deep research system?
- Or should I **keep both** (existing simple workflow + new deep research workflow)?
- If keeping both, how should they be differentiated/accessed?

**Current code:** `research_workflow.py` has a `ResearchWorkflow` class that does newsroom + web + synthesis (3 steps).

**Plan calls for:** 6-phase deep research pipeline (Source Aggregation → Citation Following → Cross-Referencing → Credibility Scoring → Graph Building → Synthesis).

**Options I'm considering:**
1. Replace existing `ResearchWorkflow` with new deep research system
2. Keep existing as `/search` command, add new as `/research` command
3. Make existing workflow a simplified version of deep research (depth=1)

**Need your decision:** Which approach?

---

### Q1.2: Tool Registry Migration Strategy
**Issue:** The plan says to create `tools/registry.py` that imports from new modules AND from old `tool_registry.py` for remaining tools.

**Question:**
- Should I migrate **ALL** tools eventually, or only the research tools?
- The plan mentions "will migrate later" - should I leave ALL non-research tools in `tool_registry.py` for now?
- Or should I migrate everything in Phase 1?

**Current state:** All tools are in `tool_registry.py` (academic_search, web_search, get_newsroom_headlines, plus many others).

**Plan says:** "For now, import remaining tools from old tool_registry (We'll migrate these incrementally)"

**Need your decision:** 
- Phase 1 scope: Only research tools (academic_search, web_search, get_newsroom_headlines)?
- Or migrate all tools now?

---

### Q1.3: Newsroom API Endpoint Discrepancy
**Issue:** The plan shows TWO different newsroom API endpoints:

1. Line 2457: `https://pj1ud6q3uf.execute-api.af-south-1.amazonaws.com/prod/api/data-admin/newsroom/articles`
2. Line 565: `https://api.asoba.co/data-admin/newsroom/articles`

**Question:** Which endpoint is correct?

**Current code:** Uses S3 direct access (needs to be replaced).

**Need your decision:** Which API endpoint should I use?

---

### Q1.4: Newsroom Tool Return Format
**Issue:** Current `get_newsroom_headlines()` returns a formatted string. The plan shows it should return formatted string for display, but Phase 3 needs to parse it into `Source` objects.

**Question:**
- Should `get_newsroom_headlines()` return **both** (formatted string + structured data)?
- Or should I create a **separate function** `fetch_newsroom_api()` that returns structured data, and keep `get_newsroom_headlines()` as display-only?
- Or should I parse the formatted string output in Phase 3?

**Current:** Returns formatted string like:
```
Newsroom Headlines for 2025-01-15 (25 articles)
...
• Title [date]
  URL: ...
```

**Plan shows:** Need to parse into `Source` objects for Phase 3.

**Need your decision:** What should `get_newsroom_headlines()` return?

---

## Phase 2: Storage Layer

### Q2.1: Database Path Location
**Issue:** Plan says SQLite at `~/.zorora/zorora.db`, but need to confirm exact path handling.

**Question:**
- Should I use `pathlib.Path.home() / ".zorora" / "zorora.db"`?
- What if `~/.zorora/` doesn't exist? Auto-create?
- What if database file doesn't exist? Auto-create schema?

**Need your decision:** Confirm path handling and auto-creation behavior.

---

### Q2.2: JSON Files Directory Structure
**Issue:** Plan says `~/.zorora/research/findings/` for JSON files.

**Question:**
- Filename format: Plan shows `2025-01-15_ai_trends_143022.json` - should I use this exact format?
- What if directory doesn't exist? Auto-create?
- Should I create subdirectories by date, or flat structure?

**Need your decision:** Confirm directory structure and filename format.

---

### Q2.3: Research ID Generation
**Issue:** Plan shows `research_id` as primary key, but doesn't specify generation method.

**Question:**
- Should I use UUID?
- Or timestamp-based like `20250115_143022_ai_trends`?
- Or hash of query + timestamp?

**Plan shows:** Examples like `ai_trends_20250115` but also mentions `research_id` as primary key.

**Need your decision:** How should `research_id` be generated?

---

### Q2.4: Storage Schema - Missing Fields
**Issue:** Plan shows SQLite schema, but some fields are unclear.

**Question:**
- `research_findings.synthesis` - Plan says "Preview only (first 500 chars)" - should I truncate when saving?
- `research_findings.total_sources` - Should this be calculated from `sources` table count, or stored separately?
- `sources.credibility_score` - Should I store as REAL (float) or TEXT?
- `citations` table - Plan shows `source_id` and `cites_source_id` - should I also store citation metadata (page numbers, etc.)?

**Need your decision:** Confirm data types and field purposes.

---

## Phase 3: Deep Research Core

### Q3.1: Citation Extraction Method
**Issue:** Plan says "Extract citations from top papers" but doesn't specify HOW.

**Question:**
- Should I parse citation strings from academic search results?
- Should I extract DOIs/URLs from source content?
- Should I use regex patterns, or LLM extraction?
- What format are citations in academic_search results?

**Current `academic_search()`:** Returns formatted string with URLs/DOIs, but citations aren't explicitly extracted.

**Need your decision:** How should I extract citations from sources?

---

### Q3.2: Citation Following - Query Strategy
**Issue:** Plan says "Query for cited papers (up to max_depth)" but doesn't specify HOW to query.

**Question:**
- Should I use `academic_search()` with the citation title/DOI?
- Should I search for the DOI directly?
- What if citation is a URL? Should I fetch the page and extract citations from it?
- How many citations should I follow per source? Top N?

**Need your decision:** What's the algorithm for following citations?

---

### Q3.3: Cross-Referencing - Claim Extraction
**Issue:** Plan says "Extract claims from sources" and "Group by similarity" but doesn't specify HOW.

**Question:**
- Should I use LLM to extract claims from source content?
- Or use simple keyword matching?
- How do I determine "similarity" between claims?
- What's the minimum confidence for a claim to be included?

**Plan mentions:** "NLP-based cross-referencing" but also says "simplified version first".

**Need your decision:** 
- Phase 3 implementation: Simple keyword-based or LLM-based?
- If LLM-based, which model should I use (reasoning model)?

---

### Q3.4: Credibility Scoring - Citation Count Source
**Issue:** Plan says `score_source_credibility()` needs `citation_count`, but where does this come from?

**Question:**
- For academic sources: Should I use `citation_count` from academic_search results?
- For web sources: How do I get citation count? (They don't have citations)
- For newsroom sources: How do I get citation count?
- Should citation_count default to 0 for non-academic sources?

**Current `academic_search()`:** Returns `citation_count` in metadata for some sources.

**Need your decision:** How should I obtain citation_count for each source type?

---

### Q3.5: Credibility Scoring - Cross-Reference Count Timing
**Issue:** Plan says cross-reference count is calculated in Phase 3, but credibility scoring happens in Phase 4.

**Question:**
- Should I calculate cross-reference counts FIRST (in Phase 3), then use them in Phase 4?
- Or should Phase 4 calculate cross-reference counts as part of scoring?
- The plan shows Phase 3 creates `Finding` objects with `sources` list - is that what I count?

**Need your decision:** When and how should cross-reference count be calculated?

---

### Q3.6: Synthesis - Model Selection
**Issue:** Plan says "Synthesis (Reasoning Model)" but doesn't specify which model.

**Question:**
- Should I use `use_reasoning_model()` tool?
- Or create a new LLMClient with reasoning model config?
- What prompt format should I use?
- Should synthesis include inline citations? How should they be formatted?

**Current code:** Has `use_reasoning_model()` tool that takes a `task` parameter.

**Need your decision:** 
- Which model/function should I use for synthesis?
- What should the synthesis prompt look like?

---

### Q3.7: Source Parsing - academic_search Output Format
**Issue:** Plan shows parsers for web_search and newsroom, but academic_search output format needs clarification.

**Question:**
- Current `academic_search()` returns formatted string - should I parse this?
- Or should I modify `academic_search()` to return structured data?
- The plan shows `parse_academic_search_results()` but doesn't provide implementation - should I create it?

**Current format:**
```
Academic search results for: query

1. Title
   URL: ...
   DOI: ...
   Year: ... | Citations: ...
   Description...
```

**Need your decision:** 
- Should I parse the formatted string, or modify academic_search to return structured data?
- If parsing, what's the exact format I should expect?

---

### Q3.8: Deep Research Tool - Integration Point
**Issue:** Plan shows creating `deep_research()` tool, but need to understand integration.

**Question:**
- Should `deep_research()` be callable via `/research` command?
- Should it also be available as a regular tool (so orchestrator can call it)?
- Should it replace the existing research workflow, or coexist?
- How should it integrate with `turn_processor.py`?

**Current:** `/search` command calls `research_workflow.execute()`.

**Plan shows:** `/research` command should call `deep_research()` tool.

**Need your decision:** 
- Should `/research` replace `/search`, or coexist?
- How should deep_research integrate with turn_processor?

---

## Phase 4: Web UI

### Q4.1: Flask App - Entry Point
**Issue:** Plan shows `web_main.py` as entry point, but need to confirm CLI integration.

**Question:**
- Should `zorora web` command (from setup.py) call `web_main.py`?
- Or should I add Flask app directly to `main.py` with a flag?
- What port should it use? Plan says localhost:5000 - confirm?

**Need your decision:** How should web UI be started?

---

### Q4.2: Web UI - Research Engine Integration
**Issue:** Plan shows Flask app should use `ResearchEngine`, but need to confirm.

**Question:**
- Should Flask app create its own `ResearchEngine` instance?
- Or should it share with terminal UI?
- How should it handle concurrent research requests?

**Need your decision:** How should web UI access the research engine?

---

### Q4.3: Web UI - Template Location
**Issue:** Plan shows templates in `ui/web/templates/`, but we already created `ui/web/templates/index.html`.

**Question:**
- Should I use the existing `index.html` as the search page?
- Or create separate `search.html`?
- The existing `index.html` has the UI design - should I adapt it or create new templates?

**Current:** `ui/web/templates/index.html` exists with research UI design.

**Plan shows:** `search.html`, `results.html`, `history.html` templates.

**Need your decision:** 
- Should I rename `index.html` to `search.html`?
- Or keep `index.html` and create additional templates?

---

## General Architecture Questions

### Q5.1: Existing Code Compatibility
**Issue:** Plan calls for major refactoring, but existing code is in use.

**Question:**
- Should I ensure **zero breaking changes** during implementation?
- Or is it acceptable to break existing functionality temporarily?
- Should I implement feature flags to enable/disable deep research?

**Need your decision:** What's the compatibility requirement?

---

### Q5.2: Error Handling Strategy
**Issue:** Plan mentions graceful degradation but doesn't specify error handling details.

**Question:**
- If newsroom API fails, should I continue with academic + web only?
- If academic search fails, should I continue with web + newsroom?
- If all sources fail, what should happen?
- Should errors be logged, displayed to user, or both?

**Need your decision:** What's the error handling strategy for each phase?

---

### Q5.3: Testing Requirements
**Issue:** Plan mentions tests but doesn't specify testing approach.

**Question:**
- Should I write unit tests for each task?
- Should I write integration tests?
- Should I mock external APIs (newsroom, academic sources)?
- What test framework should I use (pytest, unittest)?

**Need your decision:** What are the testing requirements?

---

### Q5.4: Logging Strategy
**Issue:** Plan shows logging statements but doesn't specify log levels or format.

**Question:**
- What log level should each phase use?
- Should I use the existing logging configuration from `config.py`?
- Should I create separate log files for research operations?

**Current:** Uses `logging.getLogger(__name__)` pattern.

**Need your decision:** What logging strategy should I follow?

---

## Critical Business Decisions

### Q6.1: Backward Compatibility with Existing Research
**Issue:** Users may have existing research saved in `~/.zorora/research/` directory.

**Question:**
- Should I migrate existing research files to new SQLite database?
- Or should I leave them as-is and only use SQLite for new research?
- What format are existing research files in?

**Need your decision:** How should I handle existing research data?

---

### Q6.2: Performance vs Quality Trade-offs
**Issue:** Plan mentions performance targets but doesn't specify what to do if targets aren't met.

**Question:**
- If research takes longer than 70s (depth=3), should I optimize or accept it?
- Should I implement timeouts for each phase?
- What's the maximum acceptable time for a research query?

**Need your decision:** What are the performance requirements and trade-offs?

---

### Q6.3: Feature Completeness
**Issue:** Plan has many phases and tasks - should I implement everything?

**Question:**
- Should I implement ALL phases (1-4) in one shot?
- Or should I implement incrementally and test after each phase?
- Are there any phases/tasks that are optional or can be deferred?

**Need your decision:** What's the scope for this implementation?

---

## Summary

**Total Questions:** 25

**Critical (blocking development):**
- Q1.1: Existing research_workflow.py conflict
- Q1.3: Newsroom API endpoint
- Q3.1-Q3.8: Deep research core implementation details
- Q6.3: Feature completeness scope

**Important (need before specific phases):**
- Q1.2: Tool registry migration scope
- Q1.4: Newsroom return format
- Q2.1-Q2.4: Storage layer details
- Q4.1-Q4.3: Web UI integration

**Clarification (nice to have):**
- Q5.1-Q5.4: General architecture
- Q6.1-Q6.2: Business decisions

---

**Please answer ALL questions before I begin development. I will NOT proceed with any implementation until I have clear answers to avoid making assumptions or business decisions.**
