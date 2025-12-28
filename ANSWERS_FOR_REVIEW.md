# Answers to Implementation Questions

## CRITICAL: Review and approve/modify these answers before development

---

## Phase 1: Tool Registry Refactor

### A1.1: Existing `research_workflow.py` Conflict
**RECOMMENDATION:** **COEXIST** - Keep both workflows

**Rationale:**
- Existing `/search` is simple, working, and actively used
- Deep research is complex and experimental
- Users should choose based on need

**Implementation:**
- Keep existing: `/search` → `ResearchWorkflow` (newsroom + web + synthesis)
- Add new: `/research` → `deep_research()` tool (6-phase deep research)
- No breaking changes

**Benefits:**
- Zero breaking changes
- Gradual migration path
- Users can compare results
- Can deprecate `/search` later if deep research proves better

---

### A1.2: Tool Registry Migration Strategy
**RECOMMENDATION:** **Phase 1 scope: Research tools ONLY**

**Rationale:**
- Minimize risk and scope
- Test new structure with small subset first
- Other tools working fine, no need to migrate yet

**Implementation:**
- Phase 1: Move only `academic_search`, `web_search`, `get_newsroom_headlines` to `tools/research/`
- Leave all other tools in `tool_registry.py`
- Create `tools/registry.py` that imports:
  - From `tools/research/*` (new)
  - From `tool_registry` (legacy) - all other tools

**Migration strategy for future:**
- Phase 2+: Migrate other tools incrementally as needed
- No deadline - migrate when touching that code
- Keep backward compatibility shim indefinitely

---

### A1.3: Newsroom API Endpoint Discrepancy
**RECOMMENDATION:** Use **production endpoint**

**Correct endpoint:**
```
https://pj1ud6q3uf.execute-api.af-south-1.amazonaws.com/prod/api/data-admin/newsroom/articles
```

**Rationale:**
- This is the actual deployed API (from platform/infrastructure code)
- The `api.asoba.co` endpoint in line 565 was aspirational (not deployed)
- Confirmed working in platform/data-admin/newsroom.py

**Action needed:**
- Update doc to use ONLY the correct endpoint
- Remove reference to `api.asoba.co`

---

### A1.4: Newsroom Tool Return Format
**RECOMMENDATION:** **Create two separate functions**

**Implementation:**
1. **`get_newsroom_headlines()`** - Keep as-is (returns formatted string for `/newsroom` command)
2. **`fetch_newsroom_api()`** - NEW (returns List[Source] for deep research)

**Rationale:**
- Existing tool used by REPL commands, shouldn't change return type
- Deep research needs structured data
- Clean separation of concerns

**Code structure:**
```python
# tools/research/newsroom.py

def fetch_newsroom_api(query, days_back=90, max_results=25) -> List[Source]:
    """Fetch from API, return Source objects (for deep research)"""
    # Implementation from Appendix A.3

def get_newsroom_headlines(query, days_back=90, max_results=25) -> str:
    """Fetch from API, return formatted string (for REPL display)"""
    sources = fetch_newsroom_api(query, days_back, max_results)
    return format_newsroom_headlines(sources)  # Format as string
```

---

## Phase 2: Storage Layer

### A2.1: Database Path Location
**RECOMMENDATION:** Use `pathlib` with auto-creation

**Implementation:**
```python
from pathlib import Path

db_path = Path.home() / ".zorora" / "zorora.db"
db_path.parent.mkdir(parents=True, exist_ok=True)  # Auto-create ~/.zorora/
```

**Behavior:**
- Auto-create `~/.zorora/` directory if doesn't exist
- Auto-create `zorora.db` file on first connection
- SQLite auto-creates schema on first `CREATE TABLE` if not exists

**Error handling:**
- If `~/.zorora/` creation fails (permissions), raise clear error
- If database connection fails, raise clear error

---

### A2.2: JSON Files Directory Structure
**RECOMMENDATION:** Flat structure with date-prefixed filenames

**Implementation:**
```python
findings_dir = Path.home() / ".zorora" / "research" / "findings"
findings_dir.mkdir(parents=True, exist_ok=True)  # Auto-create

# Filename format: YYYYMMDD_HHMMSS_slug.json
filename = f"{timestamp}_{topic_slug}.json"
# Example: 20250128_143022_climate_change.json
```

**Rationale:**
- Flat structure = simple, no deep nesting
- Date prefix = easy to sort chronologically
- Topic slug = human-readable
- No subdirectories needed (flat is fine for 1000s of files)

---

### A2.3: Research ID Generation
**RECOMMENDATION:** Use **timestamp + slug** format

**Implementation:**
```python
from datetime import datetime

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
topic_slug = query[:50].replace(' ', '_').lower()
topic_slug = re.sub(r'[^a-z0-9_]', '', topic_slug)  # Remove special chars
research_id = f"{topic_slug}_{timestamp}"

# Example: climate_change_impacts_20250128_143022
```

**Rationale:**
- Human-readable (not UUID gibberish)
- Chronologically sortable
- Unique (timestamp ensures no collisions)
- Descriptive (includes topic)

**Collision handling:**
- If somehow ID exists, append random 4-char suffix

---

### A2.4: Storage Schema - Missing Fields
**RECOMMENDATIONS:**

1. **`synthesis` field:** Store first 500 chars as preview
   ```sql
   synthesis TEXT  -- Preview only, full text in JSON file
   ```

2. **`total_sources`:** Store separately (don't calculate)
   ```python
   total_sources = len(state.sources_checked)  # Store this value
   ```

3. **`credibility_score`:** Store as REAL (float)
   ```sql
   credibility_score REAL  -- Floating point (0.0-1.0)
   ```

4. **`citations` table:** Keep minimal (no metadata)
   ```sql
   CREATE TABLE citations (
       source_id TEXT NOT NULL,
       cites_source_id TEXT NOT NULL,
       research_id TEXT NOT NULL,
       PRIMARY KEY (source_id, cites_source_id)
   )
   -- No page numbers, etc. - keep it simple for MVP
   ```

---

## Phase 3: Deep Research Core

### A3.1: Citation Extraction Method
**RECOMMENDATION:** **MVP: Skip citation extraction (Phase 2 disabled)**

**Rationale:**
- Citation extraction is complex (requires parsing PDFs or scraping web pages)
- Not critical for MVP
- Can add in v2.0

**MVP implementation:**
```python
def _follow_citations(self, state):
    """Phase 2: Skip for MVP"""
    if self.max_depth <= 1:
        return

    logger.info("Citation following not yet implemented - skipping")
    # TODO v2.0: Implement citation extraction
    return
```

**Future v2.0:**
- Parse academic_search results for DOI references
- Use Semantic Scholar API to get cited papers
- Extract citations from paper content via LLM

---

### A3.2: Citation Following - Query Strategy
**RECOMMENDATION:** **MVP: Not implemented (see A3.1)**

**Future v2.0 approach:**
- Query academic_search with citation DOI/title
- Limit to top 5 most-cited references per paper
- Stop if no new sources found

---

### A3.3: Cross-Referencing - Claim Extraction
**RECOMMENDATION:** **MVP: Simple keyword-based matching**

**Implementation:**
```python
# Extract keywords (4+ chars, not stopwords)
# Count sources mentioning each keyword
# Create Finding for keywords mentioned by 2+ sources
```

**Rationale:**
- LLM-based claim extraction is expensive and slow
- Keyword matching is fast and deterministic
- Good enough for MVP to show cross-referencing works

**Future v2.0:**
- Use LLM to extract semantic claims
- Use sentence embeddings for similarity matching

---

### A3.4: Credibility Scoring - Citation Count Source
**RECOMMENDATION:** Use available metadata, default to 0

**Implementation:**
```python
# For academic sources:
citation_count = source.cited_by_count  # From academic_search metadata (if available)

# For web sources:
citation_count = 0  # Not applicable

# For newsroom sources:
citation_count = 0  # Not applicable
```

**Behavior:**
- Academic sources: Use citation count from academic_search results (Google Scholar, PubMed provide this)
- If not available: Default to 0
- Web/newsroom: Always 0 (not applicable)

---

### A3.5: Credibility Scoring - Cross-Reference Count Timing
**RECOMMENDATION:** Calculate in Phase 4 (during credibility scoring)

**Rationale:**
- Cross-reference counts DEPEND on findings (created in Phase 3)
- Credibility scoring (Phase 4) needs cross-ref counts
- Therefore: Calculate cross-ref counts at START of Phase 4

**Implementation:**
```python
def _score_credibility(self, state):
    """Phase 4: Score credibility"""

    # FIRST: Calculate cross-reference counts
    cross_ref_counts = {}
    for finding in state.findings:
        for source_id in finding.sources:
            cross_ref_counts[source_id] = cross_ref_counts.get(source_id, 0) + 1

    # THEN: Score each source using those counts
    for source in state.sources_checked:
        cross_ref_count = cross_ref_counts.get(source.source_id, 1)
        cred = score_source_credibility(
            source.url,
            citation_count=source.cited_by_count,
            cross_reference_count=cross_ref_count
        )
        source.credibility_score = cred["score"]
```

---

### A3.6: Synthesis - Model Selection
**RECOMMENDATION:** Use **existing orchestrator model** (for MVP)

**Rationale:**
- No need for separate reasoning model call
- Orchestrator model (qwen/qwen2.5:32b) is good enough
- Simpler integration

**Implementation:**
```python
def _synthesize_findings(self, state):
    """Phase 6: Synthesize using orchestrator model"""

    # Build prompt (from Appendix D.3)
    prompt = build_synthesis_prompt(state)

    # Call LLM via turn_processor's LLMClient
    # For MVP: Use template-based synthesis (Appendix D.3 implementation)
    # Future: Call LLM for intelligent synthesis

    state.synthesis = template_based_synthesis(state)  # MVP
```

**Future v2.0:**
- Add dedicated reasoning model call
- Use more sophisticated prompt engineering

---

### A3.7: Source Parsing - academic_search Output Format
**RECOMMENDATION:** **Parse the formatted string** (use Appendix A parser)

**Rationale:**
- Don't modify working `academic_search()` function
- Parser is already implemented in Appendix A
- Clean separation

**Implementation:**
- Use `parse_academic_search_results()` from Appendix A.1
- Handles current format correctly
- Extracts: title, URL, DOI, year, citation_count, description

---

### A3.8: Deep Research Tool - Integration Point
**RECOMMENDATION:** **Coexist as `/research` command**

**Implementation:**
1. Keep existing: `/search` → `ResearchWorkflow.execute()`
2. Add new: `/research` → `deep_research()` tool
3. Both available as tools (orchestrator can call either)

**REPL integration:**
```python
# In repl.py
elif cmd_lower.startswith("/research "):
    query = command[10:].strip()
    result = self.tool_executor.execute("deep_research", {"query": query})
    return result
```

**turn_processor integration:**
- Add `deep_research` to `SPECIALIST_TOOLS` list
- Router can suggest deep_research for complex research questions
- User can force with `/research` command

---

## Phase 4: Web UI

### A4.1: Flask App - Entry Point
**RECOMMENDATION:** Add `zorora web` command to setup.py

**Implementation:**
```python
# In setup.py entry_points
entry_points={
    'console_scripts': [
        'zorora=main:main',          # Existing
        'zorora-web=ui.web.app:main'  # NEW
    ],
}

# In ui/web/app.py
def main():
    app.run(host='127.0.0.1', port=5000, debug=False)

if __name__ == '__main__':
    main()
```

**Usage:**
```bash
zorora        # Terminal REPL
zorora-web    # Web UI
```

---

### A4.2: Web UI - Research Engine Integration
**RECOMMENDATION:** Create new instance per request

**Rationale:**
- Flask is single-threaded by default
- No concurrency issues
- Clean isolation

**Implementation:**
```python
@app.route('/api/research', methods=['POST'])
def research():
    query = request.json.get('query')
    max_depth = request.json.get('max_depth', 2)

    # Create new engine instance for this request
    orchestrator = ResearchOrchestrator(max_depth=max_depth)
    state = orchestrator.execute(query)

    # Save and return
    storage = LocalStorage()
    research_id = storage.save_research(state)

    return jsonify({
        'research_id': research_id,
        'synthesis': state.synthesis,
        'sources': [...]
    })
```

---

### A4.3: Web UI - Template Location
**RECOMMENDATION:** **Adapt existing `index.html`**

**Implementation:**
- Rename `ui/web/templates/index.html` → `ui/web/templates/search.html`
- Use existing design (it's good!)
- Add `results.html` for showing research findings
- Add `history.html` for past research list

**File structure:**
```
ui/web/templates/
├── search.html    # Existing index.html (search form)
├── results.html   # NEW (show research findings)
└── history.html   # NEW (past research list)
```

---

## General Architecture Questions

### A5.1: Existing Code Compatibility
**RECOMMENDATION:** **Zero breaking changes**

**Requirements:**
- All existing tools must continue working
- All existing commands must work (`/search`, `/ask`, `/code`, etc.)
- Deep research is ADDITIVE only
- Feature flag: Optional (not needed if truly additive)

**Implementation:**
- New code in new files/directories
- Only additions to `tools/registry.py`, not replacements
- `/research` is new command, doesn't replace existing

---

### A5.2: Error Handling Strategy
**RECOMMENDATION:** **Graceful degradation** with logging

**Rules:**
1. If newsroom fails → Continue with academic + web
2. If academic fails → Continue with web + newsroom
3. If web fails → Continue with academic + newsroom
4. If ALL fail → Return error

**Implementation:**
```python
try:
    academic_sources = fetch_academic(query)
except Exception as e:
    logger.warning(f"Academic search failed: {e}")
    academic_sources = []

# Continue with whatever sources we got
if not any([academic_sources, web_sources, newsroom_sources]):
    raise Exception("All sources failed - cannot complete research")
```

**User feedback:**
- Log all errors
- Show warnings in UI if sources failed
- Final result shows which sources were used

---

### A5.3: Testing Requirements
**RECOMMENDATION:** **Pytest with mocks** for MVP

**Requirements:**
1. Unit tests for each module (parsers, credibility scorer, etc.)
2. Integration tests using mock data (Appendix F fixtures)
3. NO tests requiring external APIs (mock everything)

**Framework:**
```bash
pytest  # Use pytest
```

**Coverage target:**
- 70%+ for MVP (not 100%)
- Focus on critical paths (parsers, credibility scoring)
- Skip UI tests for MVP

**Test structure:**
```
tests/
├── test_parsers.py          # Parser unit tests
├── test_credibility.py      # Credibility scoring tests
├── test_storage.py          # Storage layer tests
├── test_orchestrator.py     # Integration tests (with mocks)
└── fixtures/
    └── mock_outputs.py      # Mock data from Appendix F
```

---

### A5.4: Logging Strategy
**RECOMMENDATION:** Use existing logging, INFO level

**Implementation:**
```python
import logging
logger = logging.getLogger(__name__)

# Use existing config.py logging setup
# Log levels:
# - INFO: Progress updates ("Phase 1/6: Aggregating sources...")
# - WARNING: Recoverable errors ("Newsroom unavailable, continuing...")
# - ERROR: Failures that prevent completion
# - DEBUG: Detailed diagnostics (disabled by default)
```

**Log to:**
- Console (existing behavior)
- No separate log files for MVP

---

## Critical Business Decisions

### A6.1: Backward Compatibility with Existing Research
**RECOMMENDATION:** **Ignore existing research files**

**Rationale:**
- Migration is complex and risky
- Existing research saved by `research_persistence.py` is in different format
- No user demand for migration yet

**Implementation:**
- SQLite database starts empty
- Old research files untouched in `~/.zorora/research/`
- Users can manually re-run important queries with new `/research` command
- Future: Add migration tool if users request it

---

### A6.2: Performance vs Quality Trade-offs
**RECOMMENDATION:** **Optimize for quality, accept slower speed**

**Targets:**
- Depth=1: 25-40s (acceptable)
- Depth=2: 40-70s (acceptable)
- Depth=3: 60-120s (acceptable)

**Timeouts:**
- Individual tool calls: 30s max
- Total research: 180s max (3 minutes)

**If exceeds targets:**
- Log warning but complete research
- Don't optimize prematurely
- Measure first, optimize later

---

### A6.3: Feature Completeness
**RECOMMENDATION:** **Implement ALL Phases 1-4** for MVP

**MVP Scope:**
- ✅ Phase 1: Tool registry refactor
- ✅ Phase 2: Storage layer
- ✅ Phase 3: Deep research core (simplified)
  - ✅ Phase 1: Source aggregation
  - ❌ Phase 2: Citation following (SKIP for MVP)
  - ✅ Phase 3: Cross-referencing (simple keywords)
  - ✅ Phase 4: Credibility scoring (multi-factor)
  - ✅ Phase 5: Citation graph (basic)
  - ✅ Phase 6: Synthesis (template-based)
- ✅ Phase 4: Web UI (INCLUDED in MVP)

**Rationale:**
- **Dual UIs are a core architectural principle** - not optional
- Web UI makes research accessible to non-engineers (core value prop)
- Templates already exist (`ui/web/templates/index.html`)
- Flask implementation is simple (6-7 hours, not 3-4 days)
- Decoupled engine architecture already supports it
- No authentication needed (localhost only, single-user)

**Deliverables:**
1. **Terminal REPL:**
   - Working `/research` command
   - Formatted synthesis with sources
   - Saves to SQLite + JSON

2. **Web UI:**
   - Search interface at `http://localhost:5000`
   - Results page with synthesis + sources
   - History page showing past research
   - Start with: `zorora-web`

---

## Summary of Key Decisions

| Question | Decision | Rationale |
|----------|----------|-----------|
| Q1.1 Existing workflow | **Coexist** (/search + /research) | No breaking changes |
| Q1.2 Migration scope | **Research tools only** | Minimize risk |
| Q1.3 API endpoint | **Production URL** (pj1ud6q3uf...) | Actually deployed |
| Q1.4 Newsroom format | **Two functions** (string + structured) | Clean separation |
| Q2.3 Research ID | **Timestamp + slug** | Human-readable |
| Q3.1 Citation extraction | **Skip for MVP** | Too complex |
| Q3.3 Cross-referencing | **Keyword-based** | Fast and deterministic |
| Q3.6 Synthesis model | **Template-based MVP** | Simpler integration |
| Q5.1 Compatibility | **Zero breaking changes** | Safe deployment |
| Q5.3 Testing | **Pytest with mocks** | No external APIs |
| Q6.3 Scope | **ALL Phases 1-4** | Dual UIs are core principle |

---

## Next Steps

1. **Review these answers** - Approve/modify as needed
2. **Update DEEP_RESEARCH_IMPLEMENTATION.md** with these decisions
3. **Run AI code generator** with updated doc
4. **Test with mock data** (Appendix F fixtures)
5. **Deploy to production** (MVP: terminal only)

---

**Total Answers:** 25 (all questions addressed)

**Estimated Development Time (with these answers):**
- Phase 1: 1-2 days
- Phase 2: 1-2 days
- Phase 3: 3-5 days (simplified - no citation following)
- Phase 4: 1 day (Web UI - templates mostly done)
- **Total: 6-10 days** (down from original 8-13 days by simplifying Phase 3)
