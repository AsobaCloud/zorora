# Deep Research Feature - Technical Implementation Roadmap

## Executive Summary

This document outlines the technical implementation roadmap for the Deep Research feature in Zorora REPL. The feature will provide iterative, multi-source research capabilities that search across academic databases, web sources, and the Asoba newsroom, then filter results by credibility and authority.

**Core Value Proposition:** Transform Zorora from a basic research tool into a deep research engine that:
1. Searches EVERYTHING (academic + web + newsroom)
2. Follows citation trails (multi-hop research)
3. Cross-references claims across sources
4. Scores credibility/authority transparently
5. Builds citation graphs
6. Synthesizes with confidence levels

**Deployment Model:**
- **Local-first:** All processing and storage happens on user's machine
- **Single-user:** One instance per user (no multi-user support needed)
- **Two UIs:** Terminal interface (for engineers) and Web interface (for non-engineers)
- **No cloud deployment:** No AWS infrastructure required for users

---

## Table of Contents

1. [Architectural Principles](#architectural-principles)
2. [System Architecture](#system-architecture)
3. [Design Decisions & Defensive Reasoning](#design-decisions--defensive-reasoning)
4. [Implementation Phases](#implementation-phases)
5. [Detailed Technical Specifications](#detailed-technical-specifications)
6. [Testing Strategy](#testing-strategy)
7. [Performance Optimization](#performance-optimization)
8. [Deployment & Distribution](#deployment--distribution)
9. [Risk Mitigation](#risk-mitigation)

---

## Architectural Principles

### 1. **Local-First Architecture**

**Principle:** Everything runs on the user's machine. No cloud infrastructure required.

**Defensive Reasoning:**
- **Privacy:** Research data never leaves user's machine
- **Offline capability:** Works without internet (except for source fetching)
- **Cost:** Zero ongoing costs (no cloud hosting fees)
- **Simplicity:** No AWS setup, no credentials management
- **Control:** User owns their data completely

**Storage Strategy:**
- **SQLite database:** Local in `~/.zorora/zorora.db` (fast indexed queries)
- **JSON files:** Full research findings in `~/.zorora/research/findings/` (cheap storage)
- **Pattern:** Index in SQLite (speed) + Full data in files (cost) - mirrors newsroom's DynamoDB+S3 pattern

**What users need:**
- Python 3.8+
- ~100MB disk space
- Internet connection (for fetching sources only)

**What users DON'T need:**
- AWS account
- Cloud deployment
- Database server setup
- API keys (except optional Brave Search)

---

### 2. **Deterministic Over Clever**

**Principle:** Use pattern matching and hardcoded workflows instead of LLM-based orchestration.

**Defensive Reasoning:**
- 4B orchestrator models cannot reliably plan multi-step research (30% failure rate in early testing)
- Pattern matching is 0ms vs LLM routing (2-5s)
- 100% predictable execution paths
- Easier to debug and maintain
- Works offline with local models (backup code generator pillar)

**Application to Deep Research:**
- Research workflow is a hardcoded 6-phase pipeline, not LLM-planned
- Fixed stages: Source Aggregation → Citation Following → Cross-Referencing → Credibility Scoring → Graph Building → Synthesis
- Router uses pattern matching to detect research intent
- LLM only used for synthesis (phase 6), NOT orchestration

**Workflow Pipeline:**
```
User Query
    ↓
1. PARALLEL SOURCE AGGREGATION (ThreadPoolExecutor)
    ├─► Academic Search (7 sources)
    ├─► Web Search (Brave + DDG)
    └─► Newsroom Search (API call)
    ↓
2. CITATION FOLLOWING (multi-hop)
    ├─► Extract citations from top papers
    └─► Query for cited papers (up to max_depth)
    ↓
3. CROSS-REFERENCING
    ├─► Extract claims from sources
    └─► Group by similarity, count agreement
    ↓
4. CREDIBILITY SCORING
    ├─► Score each source (rules-based)
    └─► Assign confidence to claims
    ↓
5. CITATION GRAPH BUILDING
    ├─► Build directed graph
    └─► Calculate centrality scores
    ↓
6. SYNTHESIS (Reasoning Model)
    ├─► Format findings for model
    └─► Generate synthesis with citations
```

---

### 3. **Decoupled Engine + Multiple Interfaces**

**Principle:** Core research logic is separate from UI layer. Users can choose their preferred interface.

**Defensive Reasoning:**
- **Flexibility:** Engineers prefer terminal, non-engineers prefer web UI
- **Testability:** Core logic tested once, used by all interfaces
- **Maintainability:** UI changes don't affect core logic
- **Extensibility:** Easy to add new interfaces (IDE plugins, etc.) later

**Architecture:**
```
Research Engine (Core Library)
    ├─ Storage: SQLite (indexed queries)
    ├─ Tools: academic_search, web_search, newsroom
    ├─ Workflows: 6-phase deep research pipeline
    └─ Models: Reasoning model for synthesis
         ↓
    ┌────┴────┐
    ▼         ▼
Terminal     Web UI
(Engineers)  (Non-engineers)
```

**Both interfaces:**
- Use same engine
- Same SQLite database
- Same research logic
- Run on localhost (no remote deployment)

**User choice:**
```bash
zorora          # Terminal REPL (current)
zorora web      # Web UI on localhost:5000 (new)
```

---

### 4. **Fast Indexing Pattern (Newsroom Model)**

**Principle:** Use indexed queries instead of file scanning for fast retrieval.

**Newsroom Performance Lesson:**
- **S3 Direct Scan (Slow):** 8-10 seconds, 100+ API calls
- **DynamoDB Index (Fast):** <500ms, single query
- **Improvement:** 80% faster, 74% cost reduction

**Local Implementation:**
- **SQLite Index (Fast):** <50ms query time (equivalent to DynamoDB)
- **JSON Files (Cheap):** Full data on disk (equivalent to S3)
- **Total:** <100ms retrieval time

**SQLite Schema (mirrors DynamoDB):**
```sql
-- Research findings index (like newsroom articles table)
CREATE TABLE research_findings (
    research_id TEXT PRIMARY KEY,
    query TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL,
    synthesis TEXT,                -- Preview only (first 500 chars)
    file_path TEXT NOT NULL,       -- Path to full JSON
    total_sources INTEGER
);

CREATE INDEX idx_query ON research_findings(query);
CREATE INDEX idx_created_at ON research_findings(created_at DESC);

-- Sources index (for citation queries)
CREATE TABLE sources (
    source_id TEXT PRIMARY KEY,
    research_id TEXT NOT NULL,
    url TEXT,
    credibility_score REAL
);

-- Citation graph (like newsroom's CitedByIndex GSI)
CREATE TABLE citations (
    source_id TEXT NOT NULL,
    cites_source_id TEXT NOT NULL,
    PRIMARY KEY (source_id, cites_source_id)
);

CREATE INDEX idx_cited_by ON citations(cites_source_id);
```

**Query Performance:**
```python
# Slow (file scanning - like S3 direct)
def find_research_slow(query):
    for file in glob('~/.zorora/research/findings/*.json'):
        data = json.load(open(file))
        if query in data['query']:
            results.append(data)
    # 2-5 seconds for 1000 files

# Fast (SQLite index - like DynamoDB)
def find_research_fast(query):
    cursor.execute("""
        SELECT file_path FROM research_findings
        WHERE query LIKE ?
        ORDER BY created_at DESC LIMIT 10
    """, (f'%{query}%',))

    files = [row[0] for row in cursor.fetchall()]
    results = [json.load(open(f)) for f in files]
    # <100ms for 1000 files
```

**Same pattern as newsroom, but entirely local!**

---

### 5. **Newsroom API Access (Not S3 Direct)**

**Principle:** Call newsroom API endpoint instead of S3 direct access for speed.

**Current Implementation Issue:**
- `get_newsroom_headlines` downloads from S3 directly
- Requires AWS credentials
- Slow first run (8-10s)
- Only fast after caching

**New Implementation:**
```python
# Fast: Call DynamoDB-backed API
GET /api/data-admin/newsroom/articles?search=query&limit=50
# <500ms, no AWS creds needed

# vs Old: Download from S3
aws s3 sync s3://news-collection-website/...
# 8-10s, requires AWS creds
```

**Benefits:**
- **16-20x faster:** <500ms vs 8-10s
- **No credentials:** Users don't need AWS setup
- **Always fast:** No cold start (API uses DynamoDB index)
- **Internet only:** Just needs internet, no AWS account

**Fallback strategy:**
```python
def get_newsroom_headlines(query):
    try:
        # Try API (fast, no creds)
        return fetch_newsroom_api(query)  # <500ms
    except:
        # Newsroom unavailable - skip gracefully
        logger.info("Newsroom unavailable, using academic + web only")
        return []
```

---

## System Architecture

### **High-Level Architecture**

```
┌─────────────────────────────────────────────────────────────┐
│                    User's Machine (Local)                    │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │         Research Engine (Core Library)              │    │
│  │                                                      │    │
│  │  ┌──────────────────────────────────────────┐      │    │
│  │  │   Storage Layer                          │      │    │
│  │  │  - SQLite: ~/.zorora/zorora.db          │      │    │
│  │  │  - JSON: ~/.zorora/research/findings/   │      │    │
│  │  └──────────────────────────────────────────┘      │    │
│  │                                                      │    │
│  │  ┌──────────────────────────────────────────┐      │    │
│  │  │   Tools Layer                            │      │    │
│  │  │  - academic_search (7 sources)           │      │    │
│  │  │  - web_search (Brave + DDG)             │      │    │
│  │  │  - newsroom (API call)                  │      │    │
│  │  └──────────────────────────────────────────┘      │    │
│  │                                                      │    │
│  │  ┌──────────────────────────────────────────┐      │    │
│  │  │   Deep Research Workflow                 │      │    │
│  │  │  Phase 1: Source Aggregation             │      │    │
│  │  │  Phase 2: Citation Following             │      │    │
│  │  │  Phase 3: Cross-Referencing              │      │    │
│  │  │  Phase 4: Credibility Scoring            │      │    │
│  │  │  Phase 5: Citation Graph Building        │      │    │
│  │  │  Phase 6: Synthesis (Reasoning Model)    │      │    │
│  │  └──────────────────────────────────────────┘      │    │
│  └────────────────────────────────────────────────────┘    │
│                           │                                  │
│           ┌───────────────┴───────────────┐                 │
│           ▼                               ▼                 │
│  ┌─────────────────┐           ┌──────────────────┐        │
│  │  Terminal UI    │           │    Web UI         │        │
│  │  (Engineers)    │           │  (Non-engineers)  │        │
│  │  - Rich CLI     │           │  localhost:5000   │        │
│  │  - Current REPL │           │  - Search box     │        │
│  └─────────────────┘           │  - Results page   │        │
│                                 │  - History        │        │
│                                 └──────────────────┘        │
└─────────────────────────────────────────────────────────────┘
```

### **File Structure**

```
zorora/
├── engine/                         # NEW: Core research engine
│   ├── __init__.py
│   ├── research_engine.py          # Main engine class
│   ├── storage.py                  # SQLite + JSON storage
│   └── models.py                   # ResearchState, Source, Finding
│
├── tools/                          # Refactored tool registry
│   ├── __init__.py
│   ├── registry.py                 # Central registry
│   ├── research/
│   │   ├── __init__.py
│   │   ├── academic_search.py      # Existing (7 sources)
│   │   ├── web_search.py           # Existing (Brave + DDG)
│   │   ├── newsroom.py             # Updated (API call, not S3)
│   │   ├── deep_research.py        # NEW: Main entry point
│   │   └── credibility_scorer.py   # NEW: Rules-based scoring
│   ├── code/
│   │   ├── codestral.py
│   │   ├── file_ops.py
│   │   └── shell.py
│   ├── specialist/
│   │   ├── reasoning.py
│   │   ├── search_model.py
│   │   └── image_tools.py
│   └── utils/                      # Already exists
│       ├── _search_cache.py
│       ├── _query_optimizer.py
│       ├── _result_processor.py
│       └── _content_extractor.py
│
├── workflows/
│   └── research/                   # NEW: Deep research components
│       ├── __init__.py
│       ├── research_orchestrator.py    # 6-phase pipeline
│       ├── research_state.py           # State management
│       ├── citation_extractor.py       # Extract citations
│       ├── claim_extractor.py          # Extract claims
│       └── citation_graph.py           # Graph building
│
├── ui/                             # NEW: UI layer
│   ├── terminal/
│   │   ├── __init__.py
│   │   └── repl.py                 # Current REPL (moved here)
│   └── web/
│       ├── __init__.py
│       ├── app.py                  # Flask app
│       ├── templates/
│       │   ├── search.html         # Search page
│       │   ├── results.html        # Results page
│       │   └── history.html        # History page
│       └── static/
│           ├── css/
│           │   └── style.css
│           └── js/
│               └── app.js
│
├── main.py                         # Entry point: zorora
├── web_main.py                     # Entry point: zorora web
├── config.py                       # Configuration
└── README.md
```

### **Storage Layout**

```
~/.zorora/
├── zorora.db                       # SQLite database (indexes)
│                                   # Tables: research_findings, sources, citations
│
├── research/
│   └── findings/                   # Full research JSON files
│       ├── 2025-01-15_ai_trends_143022.json
│       ├── 2025-01-15_battery_storage_150301.json
│       └── 2025-01-16_solar_policy_091245.json
│
└── cache/                          # Optional: tool-specific caches
    ├── web_search/
    └── academic_search/
```

---

## Design Decisions & Defensive Reasoning

### Decision 1: SQLite + JSON Files (Not Cloud Storage)

**Decision:** Store research locally using SQLite index + JSON files.

**Alternatives Considered:**
1. **AWS S3 + DynamoDB (REJECTED):** Requires cloud account, ongoing costs
2. **PostgreSQL (REJECTED):** Overkill for single-user, requires server setup
3. **SQLite + JSON (CHOSEN):** Local, fast, zero setup

**Defensive Reasoning:**

**Why NOT AWS:**
- **User burden:** Requires AWS account setup, credentials management
- **Cost:** $0.03/month for 1000 sessions (small, but ongoing)
- **Complexity:** Users need to understand S3, DynamoDB, Lambda
- **Privacy:** Data leaves user's machine
- **Offline:** Doesn't work without internet

**Why NOT PostgreSQL:**
- **Server required:** Users must install/run PostgreSQL server
- **Overkill:** Single-user app doesn't need client-server database
- **Complexity:** Connection management, user/password setup

**Why SQLite + JSON WINS:**
- **Zero setup:** SQLite is embedded, no server needed
- **Fast:** Indexed queries <50ms (same as DynamoDB)
- **Local:** All data on user's machine
- **Simple:** Single .db file, easy backup
- **Standard:** Ships with Python, no dependencies
- **Cheap storage:** JSON files for full data (no size limits)

**Storage Pattern:**
```
SQLite (Indexes - Fast Queries)          JSON Files (Full Data - Cheap Storage)
────────────────────────────────         ──────────────────────────────────────
research_id: "ai_trends_20250115"        {
query: "AI trends"                         "query": "AI trends",
created_at: 2025-01-15T14:30:22           "synthesis": "...",  (full text)
synthesis: "AI capacity grew..." (500c)    "sources": [...],    (all sources)
file_path: ~/.zorora/.../ai_trends.json    "findings": [...],   (all findings)
total_sources: 52                          "citation_graph": {...}
                                         }
Query time: <50ms                        Load time: <50ms
Total: <100ms
```

**Same speed as newsroom's DynamoDB approach, but entirely local!**

---

### Decision 2: Two UIs (Terminal + Web), Not Just Terminal

**Decision:** Provide both terminal and web interfaces for different user types.

**Alternatives Considered:**
1. **Terminal only (REJECTED):** Excludes non-engineers
2. **Web only (REJECTED):** Removes terminal convenience for engineers
3. **Terminal + Web (CHOSEN):** Best of both worlds

**Defensive Reasoning:**

**Why NOT Terminal Only:**
- **Accessibility:** Non-engineers intimidated by command line
- **Visualization:** Hard to show citation graphs in terminal
- **UX:** Limited interactivity (no clickable links, filters)
- **Adoption:** Limits user base to engineers only

**Why NOT Web Only:**
- **Convenience:** Engineers prefer terminal for quick queries
- **Integration:** Hard to integrate with CLI workflows
- **Speed:** Terminal is faster for simple queries (no browser startup)
- **SSH:** Doesn't work over SSH connections

**Why Terminal + Web WINS:**
- **Flexibility:** Users choose their preferred interface
- **Shared backend:** Same engine, same data, same logic
- **Engineer UX:** Terminal for power users (current)
- **Non-engineer UX:** Web UI for accessibility
- **No conflict:** Both can run simultaneously (different ports)

**Implementation:**
```bash
# Engineers (terminal)
$ zorora
[1] ⚙ > /research AI trends

# Non-engineers (web)
$ zorora web
🔬 Zorora Research Engine
📡 Running on http://localhost:5000
```

**Shared backend:**
```python
# Both UIs use same engine
from zorora.engine import ResearchEngine

engine = ResearchEngine()  # Same SQLite, same logic
result = engine.deep_research("AI trends")

# Terminal: print to console
terminal_ui.display(result)

# Web: render to HTML
return render_template('results.html', result=result)
```

---

### Decision 3: Newsroom API Call (Not S3 Direct Access)

**Decision:** Call newsroom API endpoint instead of downloading from S3.

**Alternatives Considered:**
1. **S3 direct + cache (CURRENT):** Slow first run, requires AWS creds
2. **API endpoint (CHOSEN):** Fast always, no AWS creds
3. **Skip newsroom (REJECTED):** Loses valuable curated data

**Defensive Reasoning:**

**Why NOT S3 Direct:**
- **Speed:** 8-10s first run (downloading files)
- **Credentials:** Requires AWS account setup
- **User burden:** Most users won't have AWS access
- **Inconsistent:** Fast after cache, slow cold start

**Why NOT Skip Newsroom:**
- **Data loss:** Newsroom has curated energy/policy articles
- **Coverage:** Misses domain-specific content
- **Value prop:** "Search EVERYTHING" includes newsroom

**Why API Call WINS:**
- **Fast:** <500ms always (DynamoDB-backed)
- **No credentials:** Just needs internet connection
- **Consistent:** Same speed every time
- **Maintained:** API handles caching, indexing behind scenes
- **Graceful degradation:** If unavailable, skip silently

**Performance Comparison:**
```
S3 Direct (Current):
├─ First run: 8-10s (download + parse)
├─ Cached run: 2-5s (parse cached files)
└─ Requires: AWS credentials

API Call (New):
├─ Every run: <500ms (DynamoDB query)
├─ No cache needed (always fast)
└─ Requires: Internet connection only

Speed improvement: 16-20x faster
```

**Implementation:**
```python
def get_newsroom_headlines(query: str, max_results: int = 25) -> List[Source]:
    """Call newsroom API (fast, no AWS creds)"""
    try:
        response = requests.get(
            'https://api.asoba.co/data-admin/newsroom/articles',
            params={'search': query, 'limit': max_results},
            timeout=5
        )

        if response.status_code == 200:
            articles = response.json()['articles']
            logger.info(f"✓ Newsroom: {len(articles)} articles (<500ms)")
            return parse_newsroom_articles(articles)

    except Exception as e:
        logger.warning(f"Newsroom unavailable: {e}")
        return []  # Skip gracefully, use academic + web only
```

---

### Decision 4: Hardcoded 6-Phase Pipeline (Not LLM Orchestration)

**Decision:** Use deterministic workflow pipeline instead of LLM-based planning.

**Alternatives Considered:**
1. **LLM orchestration (REJECTED):** Let LLM decide next steps dynamically
2. **Hybrid (REJECTED):** Fixed stages, LLM chooses sources
3. **Hardcoded pipeline (CHOSEN):** Fixed 6-phase workflow

**Defensive Reasoning:**

**Why NOT LLM Orchestration:**
- **Unreliable:** 30% failure rate with 4B models (early testing)
- **Non-deterministic:** Same query, different execution paths
- **Hard to debug:** "Why did it skip web search?" is unanswerable
- **Latency:** Each decision adds 2-5s (5 decisions = 10-25s overhead)
- **Offline requirement:** Defeats "backup code generator" value prop

**Why NOT Hybrid:**
- **Complexity:** Mix of deterministic + non-deterministic is confusing
- **Partial failures:** If LLM fails to choose sources, entire research fails
- **Config conflicts:** User config says "search academic" but LLM skips it

**Why Hardcoded Pipeline WINS:**
- **Predictable:** Same query → same execution path
- **Fast:** 0ms routing decisions
- **Debuggable:** Clear log trail of each stage
- **Configurable:** User controls behavior via config
- **Testable:** Can unit test each stage independently
- **Offline:** No LLM needed for orchestration

**6-Phase Pipeline:**

```python
class ResearchOrchestrator:
    def execute(self, query: str) -> ResearchState:
        state = ResearchState(query)

        # Phase 1: Source Aggregation (parallel, 8-10s)
        self._aggregate_sources(query, state)

        # Phase 2: Citation Following (5-10s per iteration)
        if self.max_depth > 1:
            self._follow_citations(state)

        # Phase 3: Cross-Referencing (1-2s)
        self._cross_reference_findings(state)

        # Phase 4: Credibility Scoring (0.5s)
        self._score_credibility(state)

        # Phase 5: Citation Graph (1-2s)
        self._build_citation_graph(state)

        # Phase 6: Synthesis (15-30s)
        self._synthesize_findings(state)

        return state
```

**Execution Times:**
- Depth=1 (quick): 25-35s
- Depth=2 (balanced): 35-50s
- Depth=3 (thorough): 50-70s

**Compared to LLM orchestration:** Would add 10-25s overhead = 35-95s total

---

### Decision 5: Multi-Factor Credibility Scoring (Not LLM, Not Naive)

**Decision:** Use multi-factor rules-based scoring that considers domain, citation count, cross-references, retractions, and journal quality.

**Key Insight:** Academic papers are NOT automatically credible (example: Wakefield vaccine-autism paper was peer-reviewed but fraudulent and retracted). Credibility requires multiple signals.

**Alternatives Considered:**
1. **LLM scoring (REJECTED):** Ask model to evaluate each source
2. **Naive domain-based (REJECTED):** "arxiv.org = credible" ignores retractions, predatory journals
3. **Multi-factor rules (CHOSEN):** Base score + modifiers (citations, cross-refs, retractions)

**Defensive Reasoning:**

**Why NOT LLM Scoring:**
- **Consistency:** Same source gets different scores (non-deterministic)
- **Latency:** 2-5s per source × 50 sources = 100-250s (unacceptable)
- **Cost:** If external API: $0.001-0.01 per source × 50 = $0.05-0.50 per research
- **Hallucination:** Model might score low-quality sources highly

**Why NOT Naive Domain Matching:**
- **Retracted papers:** Wakefield vaccine-autism paper had DOI, was peer-reviewed, still fraudulent
- **Predatory journals:** 10,000+ predatory journals publish junk with DOIs
- **ArXiv:** NOT peer-reviewed (preprints only)
- **Citation farming:** Low-quality papers can cite each other
- **Old sources:** Medical paper from 1950s may be outdated

**Why Multi-Factor WINS:**
- **Fast:** 1-2ms per source (local lookups + optional cached API)
- **Robust:** Multiple signals reduce false positives
- **Transparent:** User sees WHY a score was given
- **Graceful degradation:** Works offline (skips API checks)
- **Configurable:** Easy to add new factors or adjust weights

---

**Multi-Factor Scoring Formula:**

```
Final Score = Base Score × Citation Modifier × Cross-Ref Modifier × Retraction Penalty × Journal Quality Modifier
```

**Factor Breakdown:**

1. **Base Score (Domain-Based)** - Fast local lookup
2. **Citation Modifier** - More citations = more credible
3. **Cross-Reference Modifier** - More sources agree = more credible
4. **Retraction Penalty** - Known retracted papers score 0.0
5. **Journal Quality Modifier** - High-impact journals boosted, predatory journals penalized

---

**Implementation:**

```python
# tools/research/credibility_scorer.py
import re
from typing import Dict, Any, Optional

# Base credibility by domain (starting point)
BASE_CREDIBILITY = {
    # Tier 1: High-quality peer-reviewed (0.70-0.85 base, NOT 0.95!)
    "nature": {"score": 0.85, "reason": "Nature journal (high impact)"},
    "science.org": {"score": 0.85, "reason": "Science journal (high impact)"},
    "cell.com": {"score": 0.80, "reason": "Cell Press journal"},
    "nejm.org": {"score": 0.85, "reason": "New England Journal of Medicine"},
    "thelancet.com": {"score": 0.85, "reason": "The Lancet (high impact)"},
    "pubmed.ncbi": {"score": 0.70, "reason": "PubMed indexed (peer-reviewed)"},

    # Tier 2: Preprints and lower-tier journals (0.50-0.65)
    "arxiv.org": {"score": 0.50, "reason": "ArXiv preprint (NOT peer-reviewed)"},
    "biorxiv.org": {"score": 0.50, "reason": "bioRxiv preprint (NOT peer-reviewed)"},
    "medrxiv.org": {"score": 0.50, "reason": "medRxiv preprint (NOT peer-reviewed)"},
    "doi:": {"score": 0.65, "reason": "Has DOI (may be peer-reviewed)"},

    # Tier 3: Government and institutions (0.75-0.85)
    ".gov": {"score": 0.85, "reason": "Government source"},
    ".edu": {"score": 0.75, "reason": "Educational institution"},
    "europa.eu": {"score": 0.80, "reason": "European Union"},
    "un.org": {"score": 0.80, "reason": "United Nations"},
    "worldbank.org": {"score": 0.80, "reason": "World Bank"},

    # Tier 4: Curated news (0.70-0.75)
    "newsroom:": {"score": 0.75, "reason": "Asoba curated newsroom"},
    "asoba.co/newsroom": {"score": 0.75, "reason": "Asoba newsroom"},

    # Tier 5: Major news outlets (0.60-0.70)
    "reuters.com": {"score": 0.70, "reason": "Reuters (news wire)"},
    "bloomberg.com": {"score": 0.70, "reason": "Bloomberg (financial news)"},
    "apnews.com": {"score": 0.70, "reason": "Associated Press"},
    "bbc.com": {"score": 0.65, "reason": "BBC News"},
    "wsj.com": {"score": 0.65, "reason": "Wall Street Journal"},
    "nytimes.com": {"score": 0.65, "reason": "New York Times"},

    # Tier 6: General web (0.30-0.50)
    "medium.com": {"score": 0.40, "reason": "Blog platform"},
    "substack.com": {"score": 0.40, "reason": "Newsletter platform"},
    "blogspot.com": {"score": 0.30, "reason": "Blog platform"},
    "wordpress.com": {"score": 0.30, "reason": "Blog platform"},
    "reddit.com": {"score": 0.25, "reason": "User-generated content"},
    "quora.com": {"score": 0.25, "reason": "Q&A platform"},
}

# Known predatory publishers (automatic 0.2 score)
PREDATORY_PUBLISHERS = [
    "scirp.org", "waset.org", "omicsonline.org", "hilarispublisher.com",
    "austinpublishinggroup.com", "crimsonpublishers.com", "lupinepublishers.com",
    # Add more from Beall's list: https://beallslist.net/
]

# Known retracted papers (check DOI or URL)
# In production, this could be API call to Retraction Watch or local database
KNOWN_RETRACTIONS = {
    "10.1016/S0140-6736(97)11096-0": "Wakefield MMR-autism paper (retracted 2010)",
    # Add more high-profile retractions
}

def calculate_citation_modifier(citation_count: int) -> float:
    """
    Higher citations = higher credibility (logarithmic scale)

    Logic:
    - 0-10 cites: 0.8x (minimal validation)
    - 10-100 cites: 1.0x (baseline)
    - 100-1000 cites: 1.1x (well-cited)
    - 1000+ cites: 1.2x (highly influential)
    """
    if citation_count == 0:
        return 0.8
    elif citation_count < 10:
        return 0.9
    elif citation_count < 100:
        return 1.0
    elif citation_count < 1000:
        return 1.1
    else:
        return 1.2

def calculate_cross_reference_modifier(agreement_count: int) -> float:
    """
    More sources agree = higher credibility

    Logic:
    - 1 source only: 0.9x (unverified claim)
    - 2-3 sources: 1.0x (baseline)
    - 4-6 sources: 1.1x (well-supported)
    - 7+ sources: 1.15x (consensus)
    """
    if agreement_count <= 1:
        return 0.9
    elif agreement_count <= 3:
        return 1.0
    elif agreement_count <= 6:
        return 1.1
    else:
        return 1.15

def check_retraction_status(url: str, doi: Optional[str] = None) -> Dict[str, Any]:
    """
    Check if paper is retracted

    Priority:
    1. Local cache of known retractions (fast)
    2. TODO: Retraction Watch API (cached, optional)
    3. Fallback: Not retracted

    Returns: {"retracted": bool, "reason": str}
    """
    # Check DOI against known retractions
    if doi and doi in KNOWN_RETRACTIONS:
        return {
            "retracted": True,
            "reason": KNOWN_RETRACTIONS[doi]
        }

    # TODO: Optional API call to Retraction Watch (with caching)
    # if ENABLE_RETRACTION_API:
    #     result = check_retraction_watch_api(doi)
    #     if result: return result

    return {"retracted": False, "reason": ""}

def is_predatory_publisher(url: str) -> bool:
    """Check if URL is from known predatory publisher"""
    url_lower = url.lower()
    return any(pub in url_lower for pub in PREDATORY_PUBLISHERS)

def extract_doi_from_url(url: str) -> Optional[str]:
    """Extract DOI from URL if present"""
    doi_pattern = r'10\.\d{4,}/[^\s]+'
    match = re.search(doi_pattern, url)
    return match.group(0) if match else None

def score_source_credibility(
    url: str,
    citation_count: int = 0,
    cross_reference_count: int = 1,
    publication_year: Optional[int] = None
) -> Dict[str, Any]:
    """
    Multi-factor credibility scoring

    Args:
        url: Source URL
        citation_count: How many times this source is cited
        cross_reference_count: How many other sources support this claim
        publication_year: Year published (for recency check)

    Returns:
        {
            "score": float (0.0-1.0),
            "base_score": float,
            "category": str,
            "modifiers": {...},
            "breakdown": str (human-readable explanation)
        }
    """
    url_lower = url.lower()

    # Step 1: Get base score from domain
    base_score = 0.50  # Default unknown
    base_reason = "Unknown source"

    for domain, info in BASE_CREDIBILITY.items():
        if domain in url_lower:
            base_score = info["score"]
            base_reason = info["reason"]
            break

    # Step 2: Check for predatory publishers (override to 0.2)
    if is_predatory_publisher(url):
        return {
            "score": 0.20,
            "base_score": base_score,
            "category": "predatory_publisher",
            "modifiers": {},
            "breakdown": "⚠️ PREDATORY PUBLISHER - Known low-quality journal"
        }

    # Step 3: Check for retractions (override to 0.0)
    doi = extract_doi_from_url(url)
    retraction_status = check_retraction_status(url, doi)
    if retraction_status["retracted"]:
        return {
            "score": 0.0,
            "base_score": base_score,
            "category": "retracted",
            "modifiers": {},
            "breakdown": f"❌ RETRACTED - {retraction_status['reason']}"
        }

    # Step 4: Apply modifiers
    citation_mod = calculate_citation_modifier(citation_count)
    cross_ref_mod = calculate_cross_reference_modifier(cross_reference_count)

    # Step 5: Calculate final score (cap at 0.95, never 1.0)
    final_score = min(0.95, base_score * citation_mod * cross_ref_mod)

    # Step 6: Build explanation
    breakdown_parts = [f"Base: {base_score:.2f} ({base_reason})"]

    if citation_mod != 1.0:
        breakdown_parts.append(f"Citations: {citation_mod:.2f}x ({citation_count} cites)")

    if cross_ref_mod != 1.0:
        breakdown_parts.append(f"Cross-refs: {cross_ref_mod:.2f}x ({cross_reference_count} sources agree)")

    breakdown_parts.append(f"→ Final: {final_score:.2f}")

    return {
        "score": final_score,
        "base_score": base_score,
        "category": base_reason,
        "modifiers": {
            "citation": citation_mod,
            "cross_reference": cross_ref_mod
        },
        "breakdown": " | ".join(breakdown_parts)
    }
```

**Example Outputs:**

```python
# High-quality, well-cited paper
score_source_credibility(
    "https://www.nature.com/articles/nature12345",
    citation_count=523,
    cross_reference_count=4
)
# Returns: {
#   "score": 0.95,
#   "breakdown": "Base: 0.85 (Nature journal) | Citations: 1.1x (523 cites) | Cross-refs: 1.1x (4 sources agree) → Final: 0.95"
# }

# ArXiv preprint with few cites (NOT automatically credible)
score_source_credibility(
    "https://arxiv.org/abs/2312.12345",
    citation_count=2,
    cross_reference_count=1
)
# Returns: {
#   "score": 0.45,
#   "breakdown": "Base: 0.50 (ArXiv preprint - NOT peer-reviewed) | Citations: 0.9x (2 cites) | Cross-refs: 0.9x (1 source only) → Final: 0.45"
# }

# Retracted paper (Wakefield vaccine-autism)
score_source_credibility(
    "https://www.thelancet.com/journals/lancet/article/PIIS0140-6736(97)11096-0/fulltext"
)
# Returns: {
#   "score": 0.0,
#   "breakdown": "❌ RETRACTED - Wakefield MMR-autism paper (retracted 2010)"
# }

# Predatory journal
score_source_credibility("https://scirp.org/journal/paperinformation.aspx?paperid=12345")
# Returns: {
#   "score": 0.20,
#   "breakdown": "⚠️ PREDATORY PUBLISHER - Known low-quality journal"
# }
```

**Performance:** 1-2ms per source (local lookups only, no API calls by default)

**Future Enhancements:**
- Optional Retraction Watch API integration (cached)
- Optional journal impact factor lookup (cached)
- Recency penalty for very old sources (configurable by domain)
- Author reputation scores (H-index lookup, cached)

---

## Implementation Phases

### Phase 1: Foundation - Tool Registry Refactor (1-2 days)

**Goal:** Split monolithic `tool_registry.py` (3199 lines) into modular structure.

**Why refactor first:**
- Clean slate for deep research implementation
- No rework (write once in right place)
- Reduced testing burden (test refactor, then feature)
- No merge conflicts

#### Tasks:

**1.1: Create Directory Structure**
```bash
mkdir -p tools/research tools/code tools/specialist
touch tools/__init__.py tools/registry.py
touch tools/research/__init__.py
```

**1.2: Move Research Tools**
- Move `academic_search()` → `tools/research/academic_search.py`
- Move `web_search()` → `tools/research/web_search.py`
- Move `get_newsroom_headlines()` → `tools/research/newsroom.py`
- Test each module independently

**1.3: Create Central Registry**
```python
# tools/registry.py
from tools.research.academic_search import academic_search
from tools.research.web_search import web_search
from tools.research.newsroom import get_newsroom_headlines

TOOL_FUNCTIONS = {
    "academic_search": academic_search,
    "web_search": web_search,
    "get_newsroom_headlines": get_newsroom_headlines,
    # ... all tools
}

TOOL_ALIASES = { ... }
TOOLS_DEFINITION = [ ... ]
SPECIALIST_TOOLS = [ ... ]
```

**1.4: Update Imports**
```python
# repl.py, tool_executor.py, turn_processor.py
from tools.registry import TOOL_FUNCTIONS  # Changed from tool_registry
```

**1.5: Backward Compatibility Shim**
```python
# tool_registry.py (deprecated, re-exports from tools.registry)
import warnings
warnings.warn("Use 'from tools.registry import ...' instead", DeprecationWarning)

from tools.registry import *
```

**Success Criteria:**
- ✅ All existing tests pass
- ✅ All tools work identically
- ✅ No performance regression
- ✅ Code organized in modules

---

### Phase 2: Storage Layer (1-2 days)

**Goal:** Implement SQLite + JSON storage with fast indexed queries.

#### Tasks:

**2.1: Create Storage Module**

```python
# engine/storage.py
import sqlite3
import json
from pathlib import Path

class LocalStorage:
    """Local SQLite + JSON storage (mirrors newsroom DynamoDB+S3 pattern)"""

    def __init__(self, db_path=None):
        if db_path is None:
            db_path = Path.home() / '.zorora' / 'zorora.db'

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        """Initialize database schema"""
        cursor = self.conn.cursor()

        # Research findings index
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS research_findings (
                research_id TEXT PRIMARY KEY,
                query TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL,
                completed_at TIMESTAMP,
                synthesis TEXT,              -- Preview (first 500 chars)
                file_path TEXT NOT NULL,     -- Path to full JSON
                total_sources INTEGER,
                max_depth INTEGER
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_query ON research_findings(query)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON research_findings(created_at DESC)")

        # Sources index
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sources (
                source_id TEXT PRIMARY KEY,
                research_id TEXT NOT NULL,
                url TEXT NOT NULL,
                title TEXT,
                credibility_score REAL,
                credibility_category TEXT,
                source_type TEXT,
                FOREIGN KEY (research_id) REFERENCES research_findings(research_id)
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sources_research ON sources(research_id)")

        # Citation graph
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS citations (
                source_id TEXT NOT NULL,
                cites_source_id TEXT NOT NULL,
                research_id TEXT NOT NULL,
                PRIMARY KEY (source_id, cites_source_id)
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cited_by ON citations(cites_source_id)")

        self.conn.commit()

    def save_research(self, state) -> str:
        """Save research to SQLite + JSON file"""
        # Generate IDs and paths
        timestamp = state.started_at.strftime("%Y%m%d_%H%M%S")
        topic_slug = state.original_query[:50].replace(' ', '_').lower()
        research_id = f"{topic_slug}_{timestamp}"

        findings_dir = self.db_path.parent / 'research' / 'findings'
        findings_dir.mkdir(parents=True, exist_ok=True)
        file_path = findings_dir / f"{research_id}.json"

        # Save full data to JSON
        with open(file_path, 'w') as f:
            json.dump(state.to_dict(), f, indent=2)

        # Index metadata in SQLite
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO research_findings
            (research_id, query, created_at, completed_at, synthesis, file_path, total_sources, max_depth)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            research_id,
            state.original_query,
            state.started_at,
            state.completed_at,
            state.synthesis[:500] if state.synthesis else None,
            str(file_path),
            state.total_sources,
            state.max_depth
        ))

        # Index sources and citations
        for source in state.sources_checked:
            cursor.execute("""
                INSERT OR IGNORE INTO sources
                (source_id, research_id, url, title, credibility_score, credibility_category, source_type)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (source.source_id, research_id, source.url, source.title,
                  source.credibility_score, source.credibility_category, source.source_type))

        for source_id, cites_list in state.citation_graph.items():
            for cited_id in cites_list:
                cursor.execute("""
                    INSERT OR IGNORE INTO citations (source_id, cites_source_id, research_id)
                    VALUES (?, ?, ?)
                """, (source_id, cited_id, research_id))

        self.conn.commit()
        return research_id

    def search_research(self, query=None, limit=10):
        """Fast search using SQLite index"""
        cursor = self.conn.cursor()

        if query:
            cursor.execute("""
                SELECT * FROM research_findings
                WHERE query LIKE ?
                ORDER BY created_at DESC LIMIT ?
            """, (f'%{query}%', limit))
        else:
            cursor.execute("""
                SELECT * FROM research_findings
                ORDER BY created_at DESC LIMIT ?
            """, (limit,))

        return [dict(row) for row in cursor.fetchall()]

    def load_research(self, research_id):
        """Load full research from JSON file"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT file_path FROM research_findings WHERE research_id = ?", (research_id,))

        row = cursor.fetchone()
        if not row:
            return None

        with open(row['file_path']) as f:
            return json.load(f)
```

**2.2: Test Storage Performance**

```python
# tests/test_storage_performance.py
import time
from engine.storage import LocalStorage

def test_query_speed():
    """SQLite query should be <100ms"""
    storage = LocalStorage()

    start = time.time()
    results = storage.search_research("AI trends")
    elapsed = time.time() - start

    assert elapsed < 0.1  # <100ms
    assert len(results) > 0

def test_load_speed():
    """JSON load should be <100ms"""
    storage = LocalStorage()
    results = storage.search_research(limit=1)

    start = time.time()
    data = storage.load_research(results[0]['research_id'])
    elapsed = time.time() - start

    assert elapsed < 0.1  # <100ms
    assert data is not None
```

---

### Phase 3: Deep Research Core (3-5 days)

**Goal:** Implement 6-phase research workflow.

#### 3.1: Research State Management

```python
# workflows/research/research_state.py
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime

@dataclass
class Source:
    source_id: str
    url: str
    title: str
    authors: List[str] = field(default_factory=list)
    publication_date: str = ""
    source_type: str = ""              # 'academic', 'web', 'newsroom'
    credibility_score: float = 0.0
    credibility_category: str = ""
    content_snippet: str = ""
    cited_by_count: int = 0
    cites: List[str] = field(default_factory=list)

@dataclass
class Finding:
    claim: str
    sources: List[str]                 # List of source_ids
    confidence: str                    # 'high', 'medium', 'low'
    average_credibility: float

@dataclass
class ResearchState:
    original_query: str
    started_at: datetime = field(default_factory=datetime.now)

    # Configuration
    max_depth: int = 3
    max_iterations: int = 5

    # Progress
    current_depth: int = 0
    current_iteration: int = 0

    # Results
    sources_checked: List[Source] = field(default_factory=list)
    findings: List[Finding] = field(default_factory=list)
    citation_graph: Dict[str, List[str]] = field(default_factory=dict)

    # Synthesis
    synthesis: Optional[str] = None
    synthesis_model: Optional[str] = None

    # Metadata
    completed_at: Optional[datetime] = None
    total_sources: int = 0

    def add_source(self, source: Source):
        """Add source and update citation graph"""
        self.sources_checked.append(source)
        self.total_sources += 1
        if source.cites:
            self.citation_graph[source.source_id] = source.cites

    def get_authoritative_sources(self, top_n=10):
        """Get most authoritative sources (credibility + centrality)"""
        import math

        # Calculate centrality
        centrality = {}
        for source_id, cites_list in self.citation_graph.items():
            for cited_id in cites_list:
                centrality[cited_id] = centrality.get(cited_id, 0) + 1

        # Score = credibility * (1 + log(centrality))
        scored = []
        for source in self.sources_checked:
            cent = centrality.get(source.source_id, 0)
            authority = source.credibility_score * (1 + math.log(1 + cent))
            scored.append((authority, source))

        scored.sort(reverse=True, key=lambda x: x[0])
        return [s for _, s in scored[:top_n]]

    def to_dict(self):
        """Serialize for storage"""
        return {
            "original_query": self.original_query,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "config": {"max_depth": self.max_depth, "max_iterations": self.max_iterations},
            "sources": [
                {
                    "source_id": s.source_id,
                    "url": s.url,
                    "title": s.title,
                    "credibility_score": s.credibility_score,
                    "credibility_category": s.credibility_category,
                    "source_type": s.source_type
                }
                for s in self.sources_checked
            ],
            "citation_graph": self.citation_graph,
            "synthesis": self.synthesis,
            "total_sources": self.total_sources
        }
```

#### 3.2: Credibility Scorer (Multi-Factor)

```python
# tools/research/credibility_scorer.py
import re
from typing import Dict, Any, Optional

# Base credibility by domain (starting point, NOT final score!)
BASE_CREDIBILITY = {
    # Tier 1: High-quality peer-reviewed (0.70-0.85 base)
    "nature": {"score": 0.85, "reason": "Nature journal (high impact)"},
    "science.org": {"score": 0.85, "reason": "Science journal (high impact)"},
    "cell.com": {"score": 0.80, "reason": "Cell Press journal"},
    "nejm.org": {"score": 0.85, "reason": "New England Journal of Medicine"},
    "thelancet.com": {"score": 0.85, "reason": "The Lancet (high impact)"},
    "pubmed.ncbi": {"score": 0.70, "reason": "PubMed indexed (peer-reviewed)"},

    # Tier 2: Preprints (0.50 - NOT automatically credible!)
    "arxiv.org": {"score": 0.50, "reason": "ArXiv preprint (NOT peer-reviewed)"},
    "biorxiv.org": {"score": 0.50, "reason": "bioRxiv preprint (NOT peer-reviewed)"},
    "medrxiv.org": {"score": 0.50, "reason": "medRxiv preprint (NOT peer-reviewed)"},
    "doi:": {"score": 0.65, "reason": "Has DOI (may be peer-reviewed)"},

    # Tier 3: Government (0.75-0.85)
    ".gov": {"score": 0.85, "reason": "Government source"},
    ".edu": {"score": 0.75, "reason": "Educational institution"},
    "europa.eu": {"score": 0.80, "reason": "European Union"},
    "un.org": {"score": 0.80, "reason": "United Nations"},

    # Tier 4: Curated news (0.75)
    "newsroom:": {"score": 0.75, "reason": "Asoba curated newsroom"},
    "asoba.co/newsroom": {"score": 0.75, "reason": "Asoba newsroom"},

    # Tier 5: Major news (0.60-0.70)
    "reuters.com": {"score": 0.70, "reason": "Reuters (news wire)"},
    "bloomberg.com": {"score": 0.70, "reason": "Bloomberg (financial news)"},
    "apnews.com": {"score": 0.70, "reason": "Associated Press"},
    "bbc.com": {"score": 0.65, "reason": "BBC News"},
    "wsj.com": {"score": 0.65, "reason": "Wall Street Journal"},

    # Tier 6: General web (0.25-0.40)
    "medium.com": {"score": 0.40, "reason": "Blog platform"},
    "substack.com": {"score": 0.40, "reason": "Newsletter platform"},
    "reddit.com": {"score": 0.25, "reason": "User-generated content"},
}

# Predatory publishers (override to 0.2)
PREDATORY_PUBLISHERS = [
    "scirp.org", "waset.org", "omicsonline.org", "hilarispublisher.com",
    "austinpublishinggroup.com", "crimsonpublishers.com", "lupinepublishers.com",
]

# Known retractions (override to 0.0)
KNOWN_RETRACTIONS = {
    "10.1016/S0140-6736(97)11096-0": "Wakefield MMR-autism paper (retracted 2010)",
}

def calculate_citation_modifier(citation_count: int) -> float:
    """More citations = higher credibility (logarithmic)"""
    if citation_count == 0:
        return 0.8
    elif citation_count < 10:
        return 0.9
    elif citation_count < 100:
        return 1.0
    elif citation_count < 1000:
        return 1.1
    else:
        return 1.2

def calculate_cross_reference_modifier(agreement_count: int) -> float:
    """More sources agree = higher credibility"""
    if agreement_count <= 1:
        return 0.9
    elif agreement_count <= 3:
        return 1.0
    elif agreement_count <= 6:
        return 1.1
    else:
        return 1.15

def check_retraction_status(url: str, doi: Optional[str] = None) -> Dict[str, Any]:
    """Check if paper is retracted (local cache)"""
    if doi and doi in KNOWN_RETRACTIONS:
        return {"retracted": True, "reason": KNOWN_RETRACTIONS[doi]}
    return {"retracted": False, "reason": ""}

def is_predatory_publisher(url: str) -> bool:
    """Check if URL is from known predatory publisher"""
    return any(pub in url.lower() for pub in PREDATORY_PUBLISHERS)

def extract_doi_from_url(url: str) -> Optional[str]:
    """Extract DOI from URL if present"""
    match = re.search(r'10\.\d{4,}/[^\s]+', url)
    return match.group(0) if match else None

def score_source_credibility(
    url: str,
    citation_count: int = 0,
    cross_reference_count: int = 1,
    publication_year: Optional[int] = None
) -> Dict[str, Any]:
    """
    Multi-factor credibility scoring

    Returns: {
        "score": float (0.0-0.95),
        "base_score": float,
        "category": str,
        "modifiers": {...},
        "breakdown": str (human-readable)
    }
    """
    url_lower = url.lower()

    # Step 1: Get base score
    base_score = 0.50
    base_reason = "Unknown source"
    for domain, info in BASE_CREDIBILITY.items():
        if domain in url_lower:
            base_score = info["score"]
            base_reason = info["reason"]
            break

    # Step 2: Check predatory publishers (override)
    if is_predatory_publisher(url):
        return {
            "score": 0.20,
            "base_score": base_score,
            "category": "predatory_publisher",
            "modifiers": {},
            "breakdown": "⚠️ PREDATORY PUBLISHER"
        }

    # Step 3: Check retractions (override)
    doi = extract_doi_from_url(url)
    retraction = check_retraction_status(url, doi)
    if retraction["retracted"]:
        return {
            "score": 0.0,
            "base_score": base_score,
            "category": "retracted",
            "modifiers": {},
            "breakdown": f"❌ RETRACTED - {retraction['reason']}"
        }

    # Step 4: Apply modifiers
    cite_mod = calculate_citation_modifier(citation_count)
    cross_mod = calculate_cross_reference_modifier(cross_reference_count)

    # Step 5: Calculate final (cap at 0.95)
    final_score = min(0.95, base_score * cite_mod * cross_mod)

    # Step 6: Build explanation
    parts = [f"Base: {base_score:.2f} ({base_reason})"]
    if cite_mod != 1.0:
        parts.append(f"Citations: {cite_mod:.2f}x ({citation_count} cites)")
    if cross_mod != 1.0:
        parts.append(f"Cross-refs: {cross_mod:.2f}x ({cross_reference_count} sources)")
    parts.append(f"→ {final_score:.2f}")

    return {
        "score": final_score,
        "base_score": base_score,
        "category": base_reason,
        "modifiers": {"citation": cite_mod, "cross_reference": cross_mod},
        "breakdown": " | ".join(parts)
    }
```

#### 3.3: Research Orchestrator

```python
# workflows/research/research_orchestrator.py
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from workflows.research.research_state import ResearchState, Source
from tools.research.credibility_scorer import score_source_credibility

logger = logging.getLogger(__name__)

class ResearchOrchestrator:
    """Orchestrates 6-phase deep research workflow"""

    def __init__(self, tool_executor, llm_client, max_depth=3, parallel_enabled=True):
        self.tool_executor = tool_executor
        self.llm_client = llm_client
        self.max_depth = max_depth
        self.parallel_enabled = parallel_enabled

    def execute(self, query: str) -> ResearchState:
        """Execute 6-phase deep research"""
        logger.info(f"Starting deep research: {query}")

        state = ResearchState(original_query=query, max_depth=self.max_depth)

        # Phase 1: Source Aggregation (parallel)
        logger.info("Phase 1/6: Aggregating sources...")
        self._aggregate_sources(query, state)

        # Phase 2: Citation Following
        if self.max_depth > 1:
            logger.info("Phase 2/6: Following citations...")
            self._follow_citations(state)
        else:
            logger.info("Phase 2/6: Skipped (depth=1)")

        # Phase 3: Cross-Referencing
        logger.info("Phase 3/6: Cross-referencing findings...")
        self._cross_reference_findings(state)

        # Phase 4: Credibility Scoring
        logger.info("Phase 4/6: Scoring credibility...")
        self._score_credibility(state)

        # Phase 5: Citation Graph
        logger.info("Phase 5/6: Building citation graph...")
        self._build_citation_graph(state)

        # Phase 6: Synthesis
        logger.info("Phase 6/6: Synthesizing findings...")
        self._synthesize_findings(state)

        state.completed_at = datetime.now()
        logger.info(f"Research complete. Total sources: {state.total_sources}")

        return state

    def _aggregate_sources(self, query, state):
        """Phase 1: Parallel source aggregation"""
        if self.parallel_enabled:
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = {
                    executor.submit(self._fetch_academic, query): "academic",
                    executor.submit(self._fetch_web, query): "web",
                    executor.submit(self._fetch_newsroom, query): "newsroom"
                }

                for future in as_completed(futures):
                    source_type = futures[future]
                    try:
                        sources = future.result(timeout=30)
                        logger.info(f"✓ {source_type}: {len(sources)} sources")
                        for source in sources:
                            state.add_source(source)
                    except Exception as e:
                        logger.error(f"✗ {source_type} failed: {e}")
        else:
            # Sequential fallback
            for fetch_fn, name in [
                (self._fetch_academic, "academic"),
                (self._fetch_web, "web"),
                (self._fetch_newsroom, "newsroom")
            ]:
                try:
                    sources = fetch_fn(query)
                    logger.info(f"✓ {name}: {len(sources)} sources")
                    for source in sources:
                        state.add_source(source)
                except Exception as e:
                    logger.error(f"✗ {name} failed: {e}")

    def _fetch_academic(self, query):
        """Fetch from academic sources"""
        result_str = self.tool_executor.execute("academic_search", {"query": query})
        return self._parse_academic_results(result_str)

    def _fetch_web(self, query):
        """Fetch from web search"""
        result_str = self.tool_executor.execute("web_search", {"query": query})
        return self._parse_web_results(result_str)

    def _fetch_newsroom(self, query):
        """Fetch from newsroom API"""
        result_str = self.tool_executor.execute("get_newsroom_headlines", {"query": query})
        return self._parse_newsroom_results(result_str)

    def _parse_academic_results(self, result_str):
        """Parse academic search results into Source objects"""
        sources = []
        # Parse result_str format (depends on academic_search implementation)
        # Extract: URL, title, authors, DOI, etc.
        # For each result, create Source object with credibility score
        return sources

    def _follow_citations(self, state):
        """Phase 2: Follow citations (multi-hop research)"""
        for depth in range(1, self.max_depth):
            state.current_depth = depth

            # Get top authoritative sources from previous depth
            top_sources = state.get_authoritative_sources(top_n=5)

            # Extract citations from these sources
            # (Simplified: in real impl, parse citations from papers)
            citation_queries = [s.title for s in top_sources[:3]]

            # Search for cited papers
            for cit_query in citation_queries:
                logger.info(f"  Following citation: {cit_query[:60]}...")
                self._aggregate_sources(cit_query, state)

    def _cross_reference_findings(self, state):
        """Phase 3: Extract claims and cross-reference"""
        # Simplified: Create findings from sources
        # In real impl, use LLM to extract claims, group by similarity
        for source in state.sources_checked:
            finding = Finding(
                claim=source.content_snippet,
                sources=[source.source_id],
                confidence="low",
                average_credibility=source.credibility_score
            )
            state.findings.append(finding)

    def _score_credibility(self, state):
        """
        Phase 4: Score source credibility (multi-factor)

        Uses citation count and cross-reference agreement to adjust base scores
        """
        # First, calculate cross-reference counts
        # (how many other sources in this research support similar claims)
        cross_ref_counts = {}
        for finding in state.findings:
            for source_id in finding.sources:
                cross_ref_counts[source_id] = cross_ref_counts.get(source_id, 0) + 1

        # Score each source using multi-factor approach
        for source in state.sources_checked:
            if not source.credibility_score:  # Not already scored
                cross_ref_count = cross_ref_counts.get(source.source_id, 1)

                cred = score_source_credibility(
                    url=source.url,
                    citation_count=source.cited_by_count,  # From academic search metadata
                    cross_reference_count=cross_ref_count  # How many findings reference this
                )

                source.credibility_score = cred["score"]
                source.credibility_category = cred["category"]

                # Log breakdown for debugging
                logger.debug(f"Scored {source.title[:50]}: {cred['breakdown']}")

    def _build_citation_graph(self, state):
        """Phase 5: Build citation graph"""
        # Already tracked in state.citation_graph via state.add_source()
        logger.info(f"Citation graph: {len(state.citation_graph)} nodes")

    def _synthesize_findings(self, state):
        """Phase 6: Synthesize using reasoning model"""
        findings_text = self._format_findings_for_synthesis(state)
        credibility_text = self._format_credibility_scores(state)

        prompt = f"""You are a research synthesis expert. Synthesize findings from multiple sources.

**Topic:** {state.original_query}

**Findings:** {findings_text}

**Source Credibility:** {credibility_text}

**Instructions:**
1. Synthesize into 2-4 paragraphs
2. Use inline citations [Source Name]
3. Note confidence levels:
   - High: 3+ sources, avg credibility >0.7
   - Medium: 2 sources, avg credibility 0.5-0.7
   - Low: 1 source, avg credibility <0.5
4. Flag contradictions

Begin synthesis:
"""

        synthesis = self.llm_client.call_model(
            model_name="reasoning",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4000
        )

        state.synthesis = synthesis
        state.synthesis_model = "reasoning"

    def _format_findings_for_synthesis(self, state):
        """Format findings for prompt"""
        lines = [f"{i}. {f.claim[:200]}..." for i, f in enumerate(state.findings[:20], 1)]
        return "\n".join(lines)

    def _format_credibility_scores(self, state):
        """Format credibility scores for prompt"""
        lines = []
        for source in state.get_authoritative_sources(top_n=15):
            lines.append(f"- {source.title[:60]} ({source.url})")
            lines.append(f"  Credibility: {source.credibility_score:.2f} ({source.credibility_category})")
        return "\n".join(lines)
```

#### 3.4: Deep Research Tool

```python
# tools/research/deep_research.py
import logging
from workflows.research.research_orchestrator import ResearchOrchestrator
from engine.storage import LocalStorage

logger = logging.getLogger(__name__)

def deep_research(query: str, max_depth: int = 3) -> str:
    """
    Execute deep research across academic, web, and newsroom sources.

    Phases:
    1. Source Aggregation (parallel)
    2. Citation Following (multi-hop)
    3. Cross-Referencing
    4. Credibility Scoring
    5. Citation Graph Building
    6. Synthesis

    Returns formatted synthesis with citations and confidence levels.
    """
    logger.info(f"Deep research: {query}")

    # Initialize orchestrator
    orchestrator = ResearchOrchestrator(
        tool_executor=...,  # Get from context
        llm_client=...,      # Get from context
        max_depth=max_depth
    )

    # Execute research
    state = orchestrator.execute(query)

    # Save to local storage
    storage = LocalStorage()
    research_id = storage.save_research(state)
    logger.info(f"Saved as {research_id}")

    # Format for display
    return format_research_output(state)

def format_research_output(state):
    """Format research state for terminal/web display"""
    lines = []

    lines.append("=" * 80)
    lines.append("DEEP RESEARCH RESULTS")
    lines.append("=" * 80)
    lines.append(f"Query: {state.original_query}")
    lines.append(f"Sources: {state.total_sources}")
    lines.append(f"Duration: {(state.completed_at - state.started_at).total_seconds():.1f}s")
    lines.append("=" * 80)
    lines.append("")

    lines.append("SYNTHESIS:")
    lines.append("")
    lines.append(state.synthesis)
    lines.append("")

    lines.append("=" * 80)
    lines.append("TOP AUTHORITATIVE SOURCES:")
    lines.append("")

    for i, source in enumerate(state.get_authoritative_sources(top_n=10), 1):
        lines.append(f"{i}. {source.title}")
        lines.append(f"   URL: {source.url}")
        lines.append(f"   Credibility: {source.credibility_score:.2f} ({source.credibility_category})")
        lines.append("")

    return "\n".join(lines)
```

---

### Phase 4: Web UI (3-4 days)

**Goal:** Create simple web interface for non-engineers.

#### 4.1: Flask App

```python
# ui/web/app.py
from flask import Flask, render_template, request, jsonify
from engine.research_engine import ResearchEngine

app = Flask(__name__)
engine = ResearchEngine()

@app.route('/')
def index():
    """Search page"""
    return render_template('search.html')

@app.route('/search')
def search():
    """Execute research"""
    query = request.args.get('q')
    depth = int(request.args.get('depth', 3))

    result = engine.deep_research(query, depth=depth)
    return render_template('results.html', result=result)

@app.route('/history')
def history():
    """Research history"""
    results = engine.search_history(limit=50)
    return render_template('history.html', results=results)

@app.route('/api/research')
def api_research():
    """JSON API for AJAX"""
    query = request.args.get('q')
    result = engine.deep_research(query)
    return jsonify(result.to_dict())

if __name__ == '__main__':
    print("🔬 Zorora Research Engine")
    print("📡 http://localhost:5000")
    app.run(host='localhost', port=5000)
```

#### 4.2: Templates

```html
<!-- ui/web/templates/search.html -->
<!DOCTYPE html>
<html>
<head>
    <title>Zorora Research</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
</head>
<body>
    <div class="container">
        <h1>🔬 Zorora Deep Research</h1>

        <form action="/search" method="get">
            <input type="text" name="q" class="search-box"
                   placeholder="What would you like to research?"
                   autofocus required>

            <div class="depth-selector">
                <label>Research depth:</label>
                <label><input type="radio" name="depth" value="1"> Quick (30s)</label>
                <label><input type="radio" name="depth" value="2"> Balanced (45s)</label>
                <label><input type="radio" name="depth" value="3" checked> Thorough (60s)</label>
            </div>

            <button type="submit">🔍 Research</button>
        </form>

        <div class="links">
            <a href="/history">📚 Research History</a>
        </div>
    </div>
</body>
</html>
```

```html
<!-- ui/web/templates/results.html -->
<!DOCTYPE html>
<html>
<head>
    <title>{{ result.query }} - Zorora Research</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
</head>
<body>
    <div class="container">
        <h1>{{ result.query }}</h1>

        <div class="meta">
            <span>📊 {{ result.total_sources }} sources</span>
            <span>⏱️ {{ result.duration }}s</span>
            <span>📅 {{ result.created_at }}</span>
        </div>

        <div class="synthesis">
            <h2>Synthesis</h2>
            <div class="content">{{ result.synthesis }}</div>
        </div>

        <div class="sources">
            <h2>Top Sources</h2>
            {% for source in result.authoritative_sources %}
            <div class="source">
                <h3>{{ source.title }}</h3>
                <div class="source-meta">
                    <span class="credibility" data-score="{{ source.credibility_score }}">
                        Credibility: {{ source.credibility_score }} ({{ source.credibility_category }})
                    </span>
                    <a href="{{ source.url }}" target="_blank">View Source →</a>
                </div>
            </div>
            {% endfor %}
        </div>

        <div class="actions">
            <a href="/">← New Search</a>
            <a href="/history">View History</a>
        </div>
    </div>
</body>
</html>
```

---

## Testing Strategy

### Unit Tests (80%+ coverage)

```python
# tests/test_credibility_scorer.py
from tools.research.credibility_scorer import score_source_credibility

def test_high_quality_well_cited():
    """High-quality journal + many citations = 0.95 score"""
    result = score_source_credibility(
        "https://www.nature.com/articles/123",
        citation_count=500,
        cross_reference_count=4
    )
    assert result["score"] == 0.95  # Cap at 0.95
    assert "Nature journal" in result["category"]
    assert "Citations: 1.1x" in result["breakdown"]

def test_arxiv_preprint_low_cites():
    """ArXiv preprint NOT automatically credible"""
    result = score_source_credibility(
        "https://arxiv.org/abs/2312.12345",
        citation_count=2,
        cross_reference_count=1
    )
    # Base 0.50 × 0.9 (low cites) × 0.9 (single source) = 0.405
    assert result["score"] < 0.50
    assert "NOT peer-reviewed" in result["breakdown"]

def test_retracted_paper():
    """Wakefield vaccine-autism paper = 0.0 score"""
    result = score_source_credibility(
        "https://www.thelancet.com/journals/lancet/article/PIIS0140-6736(97)11096-0/fulltext"
    )
    assert result["score"] == 0.0
    assert result["category"] == "retracted"
    assert "Wakefield" in result["breakdown"]

def test_predatory_publisher():
    """Known predatory journal = 0.2 score"""
    result = score_source_credibility("https://scirp.org/journal/paper.aspx?id=123")
    assert result["score"] == 0.20
    assert result["category"] == "predatory_publisher"

def test_government_source():
    """Government sources still credible"""
    result = score_source_credibility("https://www.eia.gov/data")
    assert result["score"] == 0.85
    assert "Government source" in result["category"]

def test_unknown_source():
    """Unknown sources get baseline 0.50"""
    result = score_source_credibility("https://random-blog.xyz/post")
    assert result["score"] == 0.50  # Base × 1.0 × 1.0 (no modifiers)

# tests/test_storage.py
def test_save_and_load():
    storage = LocalStorage()
    state = ResearchState(original_query="test")

    research_id = storage.save_research(state)
    loaded = storage.load_research(research_id)

    assert loaded["original_query"] == "test"

def test_search_performance():
    import time
    storage = LocalStorage()

    start = time.time()
    results = storage.search_research("AI")
    elapsed = time.time() - start

    assert elapsed < 0.1  # <100ms

# tests/test_orchestrator.py
def test_source_aggregation():
    orchestrator = ResearchOrchestrator(mock_executor, mock_client)
    state = ResearchState(original_query="test")

    orchestrator._aggregate_sources("AI trends", state)

    assert state.total_sources > 0

def test_full_research():
    orchestrator = ResearchOrchestrator(mock_executor, mock_client, max_depth=1)
    state = orchestrator.execute("renewable energy")

    assert state.synthesis is not None
    assert state.total_sources > 0
    assert state.completed_at is not None
```

### Integration Tests

```python
# tests/test_integration.py
def test_deep_research_end_to_end():
    """Test complete workflow"""
    result = deep_research("AI trends 2025")

    assert "SYNTHESIS:" in result
    assert "credibility:" in result.lower()
    assert len(result) > 500

def test_web_ui():
    """Test web interface"""
    from ui.web.app import app

    client = app.test_client()
    response = client.get('/search?q=test&depth=1')

    assert response.status_code == 200
    assert b'SYNTHESIS' in response.data
```

---

## Performance Optimization

### 1. Parallel Source Aggregation

```python
# Sequential: 8s + 5s + 0.5s = 13.5s
academic = fetch_academic(query)   # 8s
web = fetch_web(query)              # 5s
newsroom = fetch_newsroom(query)    # 0.5s (API call)

# Parallel: max(8s, 5s, 0.5s) = 8s
with ThreadPoolExecutor(max_workers=3) as executor:
    futures = [
        executor.submit(fetch_academic, query),
        executor.submit(fetch_web, query),
        executor.submit(fetch_newsroom, query)
    ]
    results = [f.result() for f in futures]

# 40% faster
```

### 2. SQLite Index Performance

```sql
-- Query with index: <50ms
SELECT * FROM research_findings
WHERE query LIKE '%AI%'
ORDER BY created_at DESC
LIMIT 10;

-- Uses: idx_query, idx_created_at
-- Equivalent to DynamoDB query on GSI
```

### 3. Newsroom API Speed

```
Old (S3 direct):
├─ Download: 8-10s
├─ Parse: 1-2s
└─ Total: 9-12s

New (API call):
├─ HTTP request: 100-200ms
├─ DynamoDB query (backend): 50-100ms
├─ Parse JSON: 10-20ms
└─ Total: 200-400ms

Speed: 20-30x faster
```

### Target Performance

- **Depth=1 (quick):** 25-35s
  - Source aggregation: 8s (parallel)
  - Cross-ref + scoring: 2s
  - Synthesis: 15-25s

- **Depth=2 (balanced):** 35-50s
  - +10-15s for citation following

- **Depth=3 (thorough):** 50-70s
  - +15-20s for deeper citation chains

---

## Deployment & Distribution

### Installation

**PyPI package:**
```bash
pip install zorora

# Terminal UI
zorora

# Web UI
zorora web
```

**From source:**
```bash
git clone https://github.com/yourusername/zorora.git
cd zorora
pip install -e .

zorora          # Terminal
zorora web      # Web UI
```

### System Requirements

- Python 3.8+
- 100MB disk space
- 4GB RAM (for local models)
- Internet connection (for source fetching)

### Configuration

```python
# ~/.zorora/config.py (optional user config)
RESEARCH_CONFIG = {
    "max_depth": 3,
    "parallel_sources": True,
    "newsroom_enabled": True,
    "synthesis_model": "reasoning"
}
```

---

## Risk Mitigation

### Risk 1: SQLite Corruption

**Mitigation:**
- WAL mode (write-ahead logging)
- Automatic backups before writes
- Repair utility (`zorora repair-db`)

### Risk 2: Slow Research Performance

**Mitigation:**
- Progress indicators (users see activity)
- Streaming results (show sources as found)
- Configurable depth (quick/balanced/thorough)
- Cancellable (Ctrl+C saves partial results)

### Risk 3: Tool Registry Refactor Breaks Code

**Mitigation:**
- Backward compatibility shim
- Comprehensive test suite
- Incremental migration (one module at a time)
- Rollback plan (keep legacy file)

### Risk 4: Web UI Complexity

**Mitigation:**
- Start simple (no JavaScript frameworks)
- Progressive enhancement
- Terminal remains primary
- Web is optional feature

---

## Success Metrics

### Quantitative

1. **Performance:**
   - SQLite query: <50ms (90th percentile)
   - Research retrieval: <100ms
   - Depth=1 research: <35s

2. **Quality:**
   - Citation accuracy: >95% valid URLs
   - Source diversity: >5 sources per research
   - High-credibility sources: >70%

3. **Adoption:**
   - `/research` usage: >50 uses/week
   - Web UI users: >20% of total users

### Qualitative

- User feedback: "Better than basic search" (>70% agree)
- Code quality: >80% test coverage, <5% regression rate

---

## Conclusion

This implementation roadmap provides a comprehensive plan for building the Deep Research feature as a **local-first, single-user application** with two UI options (terminal for engineers, web for non-engineers).

**Key architectural decisions:**
1. ✅ Local SQLite + JSON storage (no cloud)
2. ✅ Decoupled engine + multiple UIs
3. ✅ Deterministic 6-phase workflow
4. ✅ Newsroom API access (fast, no AWS creds)
5. ✅ Multi-factor credibility scoring (NOT naive domain-based)
6. ✅ Fast indexed queries (newsroom pattern)

**Credibility Scoring Approach:**
- **NOT naive:** Academic papers aren't automatically credible (e.g., Wakefield vaccine-autism retraction)
- **Multi-factor:** Base score × citation modifier × cross-reference modifier
- **Checks:** Retracted papers (0.0), predatory publishers (0.2), preprints (0.50 not 0.95)
- **Transparent:** Shows breakdown (e.g., "Base: 0.85 (Nature) | Citations: 1.1x (500 cites) → 0.95")

**Expected outcomes:**
- **Fast:** 30-70s for deep research
- **Free:** $0 ongoing costs (all local)
- **Accessible:** Terminal + web UIs
- **Simple:** `pip install zorora` and go
- **Private:** All data stays on user's machine

This design aligns with Zorora's core value propositions: AI tooling, offline backup code generator, and deep research - all running locally without cloud dependencies.

---

## Detailed Implementation Plan

This section breaks down each phase into specific, actionable tasks that can be converted into GitHub issues or work items.

### Phase 1: Tool Registry Refactor (5-7 tasks, 1-2 days)

#### Task 1.1: Create Directory Structure
**File:** Setup script or manual commands
**Acceptance Criteria:**
- [ ] `tools/` directory exists
- [ ] `tools/research/` directory exists
- [ ] `tools/code/` directory exists
- [ ] `tools/specialist/` directory exists
- [ ] All `__init__.py` files created

**Steps:**
```bash
mkdir -p tools/research tools/code tools/specialist
touch tools/__init__.py
touch tools/research/__init__.py
touch tools/code/__init__.py
touch tools/specialist/__init__.py
touch tools/registry.py
```

**Estimated time:** 5 minutes

---

#### Task 1.2: Extract and Move `academic_search` Tool
**Files to modify:**
- Create: `tools/research/academic_search.py`
- Read: `tool_registry.py` (lines 2588-2700, extract `academic_search` function)

**Steps:**
1. Copy `academic_search()` function from `tool_registry.py` to new file
2. Copy all imports needed by `academic_search` (ThreadPoolExecutor, logging, config, etc.)
3. Ensure all dependencies are imported correctly
4. Test function independently

**Code structure:**
```python
# tools/research/academic_search.py
import logging
from concurrent.futures import ThreadPoolExecutor
import config

logger = logging.getLogger(__name__)

def academic_search(query: str, max_results: int = 10) -> str:
    """
    Search multiple academic sources and check Sci-Hub for full-text availability.

    Searches 7 sources in parallel:
    - Google Scholar
    - PubMed
    - CORE
    - arXiv
    - bioRxiv
    - medRxiv
    - PMC
    """
    # ... (existing implementation from tool_registry.py)
    pass
```

**Testing:**
```python
# Test in isolation
from tools.research.academic_search import academic_search
result = academic_search("machine learning", max_results=5)
assert len(result) > 0
```

**Acceptance Criteria:**
- [ ] `tools/research/academic_search.py` created
- [ ] Function works identically to original
- [ ] All imports resolved
- [ ] Unit test passes

**Estimated time:** 30 minutes

---

#### Task 1.3: Extract and Move `web_search` Tool
**Files to modify:**
- Create: `tools/research/web_search.py`
- Read: `tool_registry.py` (lines 1506-1750, extract `web_search` function)

**Steps:**
1. Copy `web_search()` function to new file
2. Copy utility imports from `tools/utils/_search_cache.py`, `_query_optimizer.py`, etc.
3. Ensure Brave API and DuckDuckGo fallback work
4. Test with real query

**Code structure:**
```python
# tools/research/web_search.py
import logging
import requests
from tools.utils._search_cache import SearchCache
from tools.utils._query_optimizer import optimize_query
import config

logger = logging.getLogger(__name__)

def web_search(
    query: str,
    max_results: int = None,
    search_type: str = 'general',
    enable_content_extraction: bool = False
) -> str:
    """
    Web search using Brave Search API (primary) + DuckDuckGo (fallback).
    """
    # ... (existing implementation)
    pass
```

**Acceptance Criteria:**
- [ ] `tools/research/web_search.py` created
- [ ] Brave API integration works
- [ ] DuckDuckGo fallback works
- [ ] Caching works (test with repeated queries)
- [ ] Unit test passes

**Estimated time:** 30 minutes

---

#### Task 1.4: Extract and Move `get_newsroom_headlines` Tool
**Files to modify:**
- Create: `tools/research/newsroom.py`
- Read: `tool_registry.py` (lines 1172-1400, extract `get_newsroom_headlines` function)
- **IMPORTANT:** Rewrite to use API instead of S3 direct

**Steps:**
1. Create new file with API-based implementation (NOT S3)
2. Call `GET /api/data-admin/newsroom/articles`
3. Parse JSON response
4. Format for display
5. Add fallback if API unavailable

**Code structure:**
```python
# tools/research/newsroom.py
import logging
import requests
from typing import List
import config

logger = logging.getLogger(__name__)

def get_newsroom_headlines(
    query: str = None,
    days_back: int = 90,
    max_results: int = 25
) -> str:
    """
    Fetch newsroom articles via API (fast, no AWS creds needed).

    NEW IMPLEMENTATION: Calls DynamoDB-backed API instead of S3 direct.
    Speed: <500ms vs 8-10s with S3.
    """
    from datetime import datetime, timedelta

    try:
        # Calculate date range
        date_from = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')

        # Call newsroom API
        response = requests.get(
            'https://pj1ud6q3uf.execute-api.af-south-1.amazonaws.com/prod/api/data-admin/newsroom/articles',
            params={
                'search': query,
                'limit': max_results,
                'date_from': date_from
            },
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            articles = data.get('articles', [])

            # Format results
            formatted = []
            formatted.append(f"📰 Newsroom Articles ({len(articles)} found)\n")

            for article in articles:
                formatted.append(f"• {article['headline']}")
                formatted.append(f"  Date: {article['date']}")
                formatted.append(f"  Topics: {', '.join(article.get('topic_tags', []))}")
                formatted.append(f"  URL: {article['url']}\n")

            logger.info(f"✓ Newsroom: {len(articles)} articles (<500ms)")
            return '\n'.join(formatted)
        else:
            logger.warning(f"Newsroom API returned {response.status_code}")
            return "⚠ Newsroom API unavailable"

    except Exception as e:
        logger.warning(f"Newsroom API error: {e}")
        return "⚠ Newsroom unavailable (using academic + web only)"
```

**Testing:**
```python
# Test API call
result = get_newsroom_headlines("renewable energy", days_back=30, max_results=10)
assert "📰 Newsroom Articles" in result
assert len(result) > 100  # Should have content
```

**Acceptance Criteria:**
- [ ] `tools/research/newsroom.py` created
- [ ] API endpoint called successfully
- [ ] Response parsed correctly
- [ ] Graceful fallback if API unavailable
- [ ] **Speed: <500ms** (verify with timing test)
- [ ] Unit test passes

**Estimated time:** 45 minutes

---

#### Task 1.5: Create Central Registry
**Files to modify:**
- Create: `tools/registry.py`
- Read: `tool_registry.py` (copy TOOL_FUNCTIONS, TOOL_ALIASES, TOOLS_DEFINITION, SPECIALIST_TOOLS)

**Steps:**
1. Create `tools/registry.py`
2. Import all tool functions from new modules
3. Copy TOOL_FUNCTIONS dict structure
4. Copy TOOL_ALIASES dict
5. Copy TOOLS_DEFINITION list
6. Copy SPECIALIST_TOOLS list

**Code structure:**
```python
# tools/registry.py
"""
Central tool registry - imports all tools and provides unified interface.
Replaces monolithic tool_registry.py.
"""

# Import research tools
from tools.research.academic_search import academic_search
from tools.research.web_search import web_search
from tools.research.newsroom import get_newsroom_headlines

# Import code tools (will do in later phases)
# from tools.code.codestral import use_codestral
# ... etc

# Import specialist tools (will do in later phases)
# from tools.specialist.reasoning import use_reasoning_model
# ... etc

# For now, import remaining tools from old tool_registry
# (We'll migrate these incrementally)
from tool_registry import (
    use_codestral,
    use_reasoning_model,
    use_search_model,
    # ... all other tools
)

# TOOL_FUNCTIONS mapping
TOOL_FUNCTIONS = {
    # Research tools (NEW - from modules)
    "academic_search": academic_search,
    "web_search": web_search,
    "get_newsroom_headlines": get_newsroom_headlines,

    # Other tools (OLD - from tool_registry, will migrate later)
    "use_codestral": use_codestral,
    "use_reasoning_model": use_reasoning_model,
    "use_search_model": use_search_model,
    # ... (copy all other tools from tool_registry.py)
}

# TOOL_ALIASES (copy from tool_registry.py)
TOOL_ALIASES = {
    "search": "use_search_model",
    "bash": "run_shell",
    # ... (copy all aliases)
}

# TOOLS_DEFINITION (copy from tool_registry.py)
TOOLS_DEFINITION = [
    {
        "type": "function",
        "function": {
            "name": "academic_search",
            "description": "Search multiple academic sources...",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "max_results": {"type": "integer", "default": 10}
                },
                "required": ["query"]
            }
        }
    },
    # ... (copy all tool definitions)
]

# SPECIALIST_TOOLS (copy from tool_registry.py)
SPECIALIST_TOOLS = [
    "use_codestral",
    "use_reasoning_model",
    "use_search_model",
    "academic_search",
    "analyze_image",
    "generate_image"
]
```

**Acceptance Criteria:**
- [ ] `tools/registry.py` created
- [ ] All tools imported (mix of new modules + old file)
- [ ] TOOL_FUNCTIONS dict complete
- [ ] TOOL_ALIASES dict complete
- [ ] TOOLS_DEFINITION list complete
- [ ] SPECIALIST_TOOLS list complete

**Estimated time:** 30 minutes

---

#### Task 1.6: Update Import Statements
**Files to modify:**
- `repl.py`
- `tool_executor.py`
- `turn_processor.py`
- Any other files that import from `tool_registry`

**Steps:**
1. Find all files that import from `tool_registry`
2. Change imports to `tools.registry`
3. Test each file individually

**Changes:**
```python
# OLD
from tool_registry import TOOL_FUNCTIONS, TOOL_ALIASES, TOOLS_DEFINITION

# NEW
from tools.registry import TOOL_FUNCTIONS, TOOL_ALIASES, TOOLS_DEFINITION
```

**Testing:**
```bash
# Test each file
python -c "from repl import REPL; print('repl.py OK')"
python -c "from tool_executor import ToolExecutor; print('tool_executor.py OK')"
python -c "from turn_processor import TurnProcessor; print('turn_processor.py OK')"
```

**Acceptance Criteria:**
- [ ] All imports updated
- [ ] No import errors
- [ ] All tests pass
- [ ] REPL starts without errors

**Estimated time:** 15 minutes

---

#### Task 1.7: Create Backward Compatibility Shim
**Files to modify:**
- Create/Update: `tool_registry.py` (make it a shim)

**Steps:**
1. Backup original `tool_registry.py` to `tool_registry_legacy.py`
2. Replace `tool_registry.py` with shim that imports from `tools.registry`
3. Add deprecation warning

**Code:**
```python
# tool_registry.py (NEW - compatibility shim)
"""
DEPRECATED: This file is kept for backward compatibility only.
Use 'from tools.registry import ...' instead.

This shim will be removed in a future release.
"""
import warnings

warnings.warn(
    "Importing from tool_registry is deprecated. "
    "Use 'from tools.registry import ...' instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export everything from tools.registry
from tools.registry import (
    TOOL_FUNCTIONS,
    TOOL_ALIASES,
    TOOLS_DEFINITION,
    SPECIALIST_TOOLS
)

__all__ = [
    'TOOL_FUNCTIONS',
    'TOOL_ALIASES',
    'TOOLS_DEFINITION',
    'SPECIALIST_TOOLS'
]
```

**Acceptance Criteria:**
- [ ] `tool_registry_legacy.py` created (backup)
- [ ] `tool_registry.py` is now a shim
- [ ] Deprecation warning shown when imported
- [ ] All old code still works

**Estimated time:** 10 minutes

---

#### Task 1.8: Test Full Refactor
**Files to test:**
- All existing functionality

**Steps:**
1. Run full test suite
2. Test all slash commands (`/search`, `/code`, `/academic`)
3. Test tool execution
4. Performance benchmark (ensure no regression)

**Testing script:**
```bash
# Run tests
pytest tests/

# Manual tests
zorora
> /search test query
> /academic machine learning
> /code print hello world

# Performance test
time python -c "from tools.registry import TOOL_FUNCTIONS; print(len(TOOL_FUNCTIONS))"
```

**Acceptance Criteria:**
- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] All slash commands work
- [ ] Performance unchanged (<5% regression allowed)
- [ ] No import errors

**Estimated time:** 30 minutes

---

### Phase 2: Storage Layer (6 tasks, 1-2 days)

#### Task 2.1: Create Storage Module Structure
**Files to create:**
- `engine/__init__.py`
- `engine/storage.py`
- `engine/models.py`

**Steps:**
```bash
mkdir -p engine
touch engine/__init__.py
touch engine/storage.py
touch engine/models.py
```

**Acceptance Criteria:**
- [ ] Directory structure created
- [ ] Files exist

**Estimated time:** 5 minutes

---

#### Task 2.2: Implement Data Models
**Files to modify:**
- `engine/models.py`

**Steps:**
1. Create `Source` dataclass
2. Create `Finding` dataclass
3. Create `ResearchState` dataclass
4. Add serialization methods

**Code:**
```python
# engine/models.py
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime
import hashlib

@dataclass
class Source:
    """Individual source document"""
    source_id: str
    url: str
    title: str
    authors: List[str] = field(default_factory=list)
    publication_date: str = ""
    source_type: str = ""              # 'academic', 'web', 'newsroom'
    credibility_score: float = 0.0
    credibility_category: str = ""
    content_snippet: str = ""
    cited_by_count: int = 0
    cites: List[str] = field(default_factory=list)

    @staticmethod
    def generate_id(url: str) -> str:
        """Generate unique source ID from URL"""
        return hashlib.md5(url.encode()).hexdigest()

@dataclass
class Finding:
    """Research finding (claim extracted from sources)"""
    claim: str
    sources: List[str]                 # List of source_ids
    confidence: str                    # 'high', 'medium', 'low'
    average_credibility: float

@dataclass
class ResearchState:
    """Complete research workflow state"""
    # Input
    original_query: str
    started_at: datetime = field(default_factory=datetime.now)

    # Configuration
    max_depth: int = 3
    max_iterations: int = 5

    # Progress
    current_depth: int = 0
    current_iteration: int = 0

    # Results
    sources_checked: List[Source] = field(default_factory=list)
    findings: List[Finding] = field(default_factory=list)
    citation_graph: Dict[str, List[str]] = field(default_factory=dict)

    # Synthesis
    synthesis: Optional[str] = None
    synthesis_model: Optional[str] = None

    # Metadata
    completed_at: Optional[datetime] = None
    total_sources: int = 0

    def add_source(self, source: Source):
        """Add source and update citation graph"""
        self.sources_checked.append(source)
        self.total_sources += 1
        if source.cites:
            self.citation_graph[source.source_id] = source.cites

    def get_authoritative_sources(self, top_n: int = 10) -> List[Source]:
        """Get most authoritative sources (credibility + centrality)"""
        import math

        # Calculate centrality
        centrality = {}
        for source_id, cites_list in self.citation_graph.items():
            for cited_id in cites_list:
                centrality[cited_id] = centrality.get(cited_id, 0) + 1

        # Score = credibility * (1 + log(centrality))
        scored = []
        for source in self.sources_checked:
            cent = centrality.get(source.source_id, 0)
            authority = source.credibility_score * (1 + math.log(1 + cent))
            scored.append((authority, source))

        scored.sort(reverse=True, key=lambda x: x[0])
        return [s for _, s in scored[:top_n]]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for storage"""
        return {
            "original_query": self.original_query,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "config": {
                "max_depth": self.max_depth,
                "max_iterations": self.max_iterations
            },
            "progress": {
                "current_depth": self.current_depth,
                "current_iteration": self.current_iteration
            },
            "sources": [
                {
                    "source_id": s.source_id,
                    "url": s.url,
                    "title": s.title,
                    "authors": s.authors,
                    "publication_date": s.publication_date,
                    "source_type": s.source_type,
                    "credibility_score": s.credibility_score,
                    "credibility_category": s.credibility_category,
                    "cited_by_count": s.cited_by_count,
                    "cites": s.cites
                }
                for s in self.sources_checked
            ],
            "findings": [
                {
                    "claim": f.claim,
                    "sources": f.sources,
                    "confidence": f.confidence,
                    "average_credibility": f.average_credibility
                }
                for f in self.findings
            ],
            "citation_graph": self.citation_graph,
            "synthesis": self.synthesis,
            "synthesis_model": self.synthesis_model,
            "total_sources": self.total_sources
        }
```

**Testing:**
```python
# Test data model
from engine.models import Source, Finding, ResearchState

# Test Source
source = Source(
    source_id="test_id",
    url="https://example.com",
    title="Test Paper",
    source_type="academic",
    credibility_score=0.9
)
assert source.source_id == "test_id"

# Test ResearchState
state = ResearchState(original_query="test query")
state.add_source(source)
assert state.total_sources == 1
assert len(state.sources_checked) == 1

# Test serialization
data = state.to_dict()
assert data["original_query"] == "test query"
assert len(data["sources"]) == 1
```

**Acceptance Criteria:**
- [ ] All dataclasses defined
- [ ] `add_source()` works
- [ ] `get_authoritative_sources()` works
- [ ] `to_dict()` serialization works
- [ ] Unit tests pass

**Estimated time:** 1 hour

---

#### Task 2.3: Implement SQLite Storage Layer
**Files to modify:**
- `engine/storage.py`

**Steps:**
1. Create `LocalStorage` class
2. Implement `_init_schema()` to create tables
3. Implement `save_research()`
4. Implement `search_research()`
5. Implement `load_research()`

**Code:** (See Phase 2, Task 2.1 in current document for full implementation)

**Acceptance Criteria:**
- [ ] SQLite database created at `~/.zorora/zorora.db`
- [ ] Tables created: `research_findings`, `sources`, `citations`
- [ ] Indexes created: `idx_query`, `idx_created_at`, `idx_cited_by`
- [ ] `save_research()` works
- [ ] `search_research()` works
- [ ] `load_research()` works
- [ ] Unit tests pass

**Estimated time:** 2 hours

---

#### Task 2.4: Test Storage Performance
**Files to create:**
- `tests/test_storage_performance.py`

**Steps:**
1. Create performance test suite
2. Test query speed (<100ms)
3. Test load speed (<100ms)
4. Test bulk operations

**Testing code:**
```python
# tests/test_storage_performance.py
import time
import pytest
from engine.storage import LocalStorage
from engine.models import ResearchState, Source

def test_query_speed():
    """SQLite query should be <100ms"""
    storage = LocalStorage()

    # Create test data
    for i in range(100):
        state = ResearchState(original_query=f"test query {i}")
        storage.save_research(state)

    # Test query speed
    start = time.time()
    results = storage.search_research("query")
    elapsed = time.time() - start

    assert elapsed < 0.1, f"Query took {elapsed}s (should be <100ms)"
    assert len(results) > 0

def test_load_speed():
    """JSON load should be <100ms"""
    storage = LocalStorage()

    # Create and save research
    state = ResearchState(original_query="performance test")
    research_id = storage.save_research(state)

    # Test load speed
    start = time.time()
    loaded = storage.load_research(research_id)
    elapsed = time.time() - start

    assert elapsed < 0.1, f"Load took {elapsed}s (should be <100ms)"
    assert loaded is not None

def test_bulk_save():
    """Test saving many research sessions"""
    storage = LocalStorage()

    start = time.time()
    for i in range(10):
        state = ResearchState(original_query=f"bulk test {i}")
        storage.save_research(state)
    elapsed = time.time() - start

    assert elapsed < 1.0, f"Bulk save took {elapsed}s (should be <1s for 10 items)"
```

**Acceptance Criteria:**
- [ ] Query speed <100ms
- [ ] Load speed <100ms
- [ ] Bulk operations efficient
- [ ] All performance tests pass

**Estimated time:** 1 hour

---

#### Task 2.5: Create Research Engine Wrapper
**Files to create:**
- `engine/research_engine.py`

**Steps:**
1. Create `ResearchEngine` class
2. Wrap storage layer
3. Provide simple API for UIs

**Code:**
```python
# engine/research_engine.py
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from engine.storage import LocalStorage
from engine.models import ResearchState

logger = logging.getLogger(__name__)

class ResearchEngine:
    """
    Main research engine - interface-agnostic core.
    Used by both terminal and web UIs.
    """

    def __init__(self, db_path: Optional[str] = None):
        """Initialize engine with local storage"""
        self.storage = LocalStorage(db_path)
        logger.info(f"Research engine initialized: {self.storage.db_path}")

    def deep_research(self, query: str, depth: int = 3) -> ResearchState:
        """
        Execute deep research (placeholder - will implement in Phase 3).

        Args:
            query: Research query
            depth: Research depth (1-3)

        Returns:
            ResearchState with results
        """
        # TODO: Implement in Phase 3
        raise NotImplementedError("Deep research will be implemented in Phase 3")

    def search_history(self, query: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search research history.

        Args:
            query: Optional search term
            limit: Max results

        Returns:
            List of research metadata
        """
        return self.storage.search_research(query, limit)

    def load_research(self, research_id: str) -> Optional[Dict[str, Any]]:
        """
        Load full research by ID.

        Args:
            research_id: Research ID

        Returns:
            Full research data
        """
        return self.storage.load_research(research_id)

    def get_stats(self) -> Dict[str, Any]:
        """Get engine statistics"""
        results = self.storage.search_research(limit=1000)
        return {
            "total_research": len(results),
            "db_path": str(self.storage.db_path),
            "db_size_mb": self.storage.db_path.stat().st_size / (1024 * 1024)
        }
```

**Testing:**
```python
# Test engine
from engine.research_engine import ResearchEngine

engine = ResearchEngine()

# Test search
history = engine.search_history(limit=10)
assert isinstance(history, list)

# Test stats
stats = engine.get_stats()
assert "total_research" in stats
assert "db_path" in stats
```

**Acceptance Criteria:**
- [ ] `ResearchEngine` class created
- [ ] `search_history()` works
- [ ] `load_research()` works
- [ ] `get_stats()` works
- [ ] Unit tests pass

**Estimated time:** 30 minutes

---

#### Task 2.6: Integration Test - Storage End-to-End
**Files to create:**
- `tests/test_storage_integration.py`

**Steps:**
1. Test full workflow: create → save → search → load
2. Test edge cases
3. Test error handling

**Testing code:**
```python
# tests/test_storage_integration.py
import pytest
from engine.research_engine import ResearchEngine
from engine.models import ResearchState, Source

def test_full_workflow():
    """Test complete storage workflow"""
    engine = ResearchEngine()

    # Create research
    state = ResearchState(original_query="integration test")
    source = Source(
        source_id="test_source",
        url="https://example.com",
        title="Test Source",
        source_type="academic",
        credibility_score=0.9
    )
    state.add_source(source)

    # Save (will be implemented when deep_research works)
    # For now, test storage directly
    research_id = engine.storage.save_research(state)

    # Search
    results = engine.search_history("integration")
    assert len(results) >= 1
    assert results[0]["query"] == "integration test"

    # Load
    loaded = engine.load_research(research_id)
    assert loaded is not None
    assert loaded["original_query"] == "integration test"
    assert len(loaded["sources"]) == 1

def test_empty_search():
    """Test searching with no results"""
    engine = ResearchEngine()
    results = engine.search_history("nonexistent_query_xyz")
    assert len(results) == 0

def test_stats():
    """Test statistics"""
    engine = ResearchEngine()
    stats = engine.get_stats()

    assert "total_research" in stats
    assert isinstance(stats["total_research"], int)
    assert stats["db_size_mb"] > 0
```

**Acceptance Criteria:**
- [ ] Full workflow test passes
- [ ] Edge cases handled
- [ ] Error cases handled
- [ ] Integration tests pass

**Estimated time:** 45 minutes

---

### Phase 3: Deep Research Core (12 tasks, 3-5 days)

#### Task 3.1: Create Multi-Factor Credibility Scorer
**Files to create:**
- `tools/research/credibility_scorer.py`

**Implementation Details:**
See lines 1356-1524 in this document for full implementation.

**Key Components:**
1. **BASE_CREDIBILITY** dict (domain → base score mapping)
   - Tier 1: High-quality journals (0.70-0.85) - NOT 0.95!
   - Tier 2: Preprints (0.50) - ArXiv NOT automatically credible
   - Tier 3: Government (0.75-0.85)
   - Tier 4: Curated news (0.75)
   - Tier 5: Major news (0.60-0.70)
   - Tier 6: General web (0.25-0.40)

2. **PREDATORY_PUBLISHERS** list
   - Known predatory journals (scirp.org, waset.org, etc.)
   - From Beall's list: https://beallslist.net/
   - Override score to 0.2

3. **KNOWN_RETRACTIONS** dict
   - DOI → retraction reason
   - Include Wakefield vaccine-autism paper
   - Override score to 0.0

4. **Modifier Functions:**
   - `calculate_citation_modifier()` - 0.8x to 1.2x based on citation count
   - `calculate_cross_reference_modifier()` - 0.9x to 1.15x based on agreement
   - `check_retraction_status()` - Local cache check
   - `is_predatory_publisher()` - Domain matching
   - `extract_doi_from_url()` - Regex extraction

5. **Main Function:**
   - `score_source_credibility(url, citation_count, cross_reference_count, publication_year)`
   - Returns: score, base_score, category, modifiers, breakdown

**Acceptance Criteria:**
- [ ] All 6 tiers of BASE_CREDIBILITY defined
- [ ] Predatory publisher list included (7+ publishers)
- [ ] Known retractions list (Wakefield paper minimum)
- [ ] Citation modifier works (0-10: 0.8x, 1000+: 1.2x)
- [ ] Cross-ref modifier works (1: 0.9x, 7+: 1.15x)
- [ ] Retraction check returns correct status
- [ ] DOI extraction works
- [ ] `score_source_credibility()` returns all required fields
- [ ] **Nature paper (500 cites, 4 cross-refs) = 0.95** (test case)
- [ ] **ArXiv preprint (2 cites, 1 cross-ref) < 0.50** (test case)
- [ ] **Wakefield paper = 0.0** (test case)
- [ ] **Predatory journal = 0.2** (test case)
- [ ] Performance <2ms per source
- [ ] All unit tests pass (see lines 1947-1996)

**Estimated time:** 1.5 hours (increased due to multi-factor complexity)

---

#### Task 3.2: Create Research State Management
**Files already created:** `engine/models.py` (from Task 2.2)

**Additional work:**
- Verify citation graph methods work
- Add helper methods if needed

**Estimated time:** 30 minutes

---

#### Task 3.3: Create Research Orchestrator - Base Structure
**Files to create:**
- `workflows/research/__init__.py`
- `workflows/research/research_orchestrator.py`

**Steps:**
1. Create class structure
2. Implement `__init__()`
3. Implement `execute()` method skeleton
4. Define all 6 phase method signatures

**Code skeleton:**
```python
# workflows/research/research_orchestrator.py
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from engine.models import ResearchState, Source, Finding
from tools.research.credibility_scorer import score_source_credibility

logger = logging.getLogger(__name__)

class ResearchOrchestrator:
    """Orchestrates 6-phase deep research workflow"""

    def __init__(self, tool_executor, llm_client, max_depth=3, parallel_enabled=True):
        self.tool_executor = tool_executor
        self.llm_client = llm_client
        self.max_depth = max_depth
        self.parallel_enabled = parallel_enabled
        logger.info(f"Orchestrator initialized: depth={max_depth}, parallel={parallel_enabled}")

    def execute(self, query: str) -> ResearchState:
        """Execute 6-phase deep research"""
        logger.info(f"=== Starting deep research: {query} ===")
        state = ResearchState(original_query=query, max_depth=self.max_depth)

        # Phase 1: Source Aggregation
        logger.info("Phase 1/6: Aggregating sources...")
        self._aggregate_sources(query, state)

        # Phase 2: Citation Following
        if self.max_depth > 1:
            logger.info("Phase 2/6: Following citations...")
            self._follow_citations(state)
        else:
            logger.info("Phase 2/6: Skipped (depth=1)")

        # Phase 3: Cross-Referencing
        logger.info("Phase 3/6: Cross-referencing...")
        self._cross_reference_findings(state)

        # Phase 4: Credibility Scoring
        logger.info("Phase 4/6: Scoring credibility...")
        self._score_credibility(state)

        # Phase 5: Citation Graph
        logger.info("Phase 5/6: Building citation graph...")
        self._build_citation_graph(state)

        # Phase 6: Synthesis
        logger.info("Phase 6/6: Synthesizing...")
        self._synthesize_findings(state)

        state.completed_at = datetime.now()
        logger.info(f"=== Research complete: {state.total_sources} sources ===")
        return state

    def _aggregate_sources(self, query, state):
        """Phase 1: Parallel source aggregation"""
        raise NotImplementedError("Will implement in Task 3.4")

    def _follow_citations(self, state):
        """Phase 2: Follow citations"""
        raise NotImplementedError("Will implement in Task 3.5")

    def _cross_reference_findings(self, state):
        """Phase 3: Cross-reference"""
        raise NotImplementedError("Will implement in Task 3.6")

    def _score_credibility(self, state):
        """Phase 4: Score credibility"""
        raise NotImplementedError("Will implement in Task 3.7")

    def _build_citation_graph(self, state):
        """Phase 5: Build citation graph"""
        raise NotImplementedError("Will implement in Task 3.8")

    def _synthesize_findings(self, state):
        """Phase 6: Synthesize"""
        raise NotImplementedError("Will implement in Task 3.9")
```

**Acceptance Criteria:**
- [ ] Class structure created
- [ ] `execute()` method skeleton works
- [ ] All phase methods defined
- [ ] Logging in place

**Estimated time:** 30 minutes

---

#### Task 3.4: Implement Phase 1 - Source Aggregation
**Files to modify:**
- `workflows/research/research_orchestrator.py`

**Steps:**
1. Implement `_aggregate_sources()` with parallel execution
2. Implement `_fetch_academic()`
3. Implement `_fetch_web()`
4. Implement `_fetch_newsroom()`
5. Implement result parsing methods

**Code:** (See lines 1229-1285 in current document)

**Testing:**
```python
# Test source aggregation
from workflows.research.research_orchestrator import ResearchOrchestrator
from engine.models import ResearchState

# Mock tool_executor and llm_client
orchestrator = ResearchOrchestrator(mock_tool_executor, mock_llm_client)
state = ResearchState(original_query="test query")

orchestrator._aggregate_sources("test query", state)

assert state.total_sources > 0
assert len(state.sources_checked) > 0
```

**Acceptance Criteria:**
- [ ] Parallel execution works (ThreadPoolExecutor)
- [ ] All 3 sources fetched (academic, web, newsroom)
- [ ] Sources parsed correctly
- [ ] Results added to state
- [ ] Unit tests pass

**Estimated time:** 3 hours

---

#### Task 3.5: Implement Phase 2 - Citation Following
**Files to modify:**
- `workflows/research/research_orchestrator.py`

**Steps:**
1. Implement `_follow_citations()`
2. Extract citations from top sources
3. Query for cited papers
4. Iterate up to max_depth

**Code:** (See lines 1286-1302 in current document)

**Acceptance Criteria:**
- [ ] Citation extraction works
- [ ] Iterates correctly (respects max_depth)
- [ ] New sources added to state
- [ ] Unit tests pass

**Estimated time:** 2 hours

---

#### Task 3.6: Implement Phase 3 - Cross-Referencing
**Files to modify:**
- `workflows/research/research_orchestrator.py`

**Steps:**
1. Implement `_cross_reference_findings()`
2. Extract claims from sources (simplified version first)
3. Group similar claims
4. Count source agreement

**Code:** (See lines 1303-1315 in current document)

**Acceptance Criteria:**
- [ ] Claims extracted from sources
- [ ] Findings created
- [ ] Added to state
- [ ] Unit tests pass

**Estimated time:** 2 hours

---

#### Task 3.7: Implement Phase 4 - Multi-Factor Credibility Scoring
**Files to modify:**
- `workflows/research/research_orchestrator.py`

**Steps:**
1. Calculate cross-reference counts (how many findings reference each source)
2. For each source, call `score_source_credibility()` with:
   - URL (required)
   - Citation count from academic metadata (if available)
   - Cross-reference count from step 1
3. Store score and category in source object
4. Log breakdown for debugging

**Key Implementation Details:**
```python
# Calculate cross-refs first
cross_ref_counts = {}
for finding in state.findings:
    for source_id in finding.sources:
        cross_ref_counts[source_id] = cross_ref_counts.get(source_id, 0) + 1

# Score with multi-factor approach
for source in state.sources_checked:
    cross_ref_count = cross_ref_counts.get(source.source_id, 1)
    cred = score_source_credibility(
        url=source.url,
        citation_count=source.cited_by_count,
        cross_reference_count=cross_ref_count
    )
    source.credibility_score = cred["score"]
    source.credibility_category = cred["category"]
```

**Acceptance Criteria:**
- [ ] All sources scored with multi-factor approach
- [ ] ArXiv preprints score lower than Nature papers (NOT both 0.95)
- [ ] Well-cited sources get higher scores
- [ ] Cross-referenced sources get boosted
- [ ] Retracted papers score 0.0
- [ ] Predatory publishers score 0.2
- [ ] Scores stored in state
- [ ] Unit tests pass (including retraction/predatory tests)

**Estimated time:** 1 hour (increased due to multi-factor complexity)

---

#### Task 3.8: Implement Phase 5 - Citation Graph Building
**Files to modify:**
- `workflows/research/research_orchestrator.py`

**Steps:**
1. Implement `_build_citation_graph()`
2. Calculate centrality scores
3. Identify authoritative sources

**Code:** (See lines 1324-1328 in current document)

**Acceptance Criteria:**
- [ ] Citation graph built
- [ ] Centrality calculated
- [ ] Authoritative sources identified
- [ ] Unit tests pass

**Estimated time:** 1 hour

---

#### Task 3.9: Implement Phase 6 - Synthesis
**Files to modify:**
- `workflows/research/research_orchestrator.py`

**Steps:**
1. Implement `_synthesize_findings()`
2. Format findings for reasoning model
3. Call reasoning model with prompt
4. Store synthesis in state

**Code:** (See lines 1329-1375 in current document)

**Acceptance Criteria:**
- [ ] Findings formatted correctly
- [ ] Reasoning model called
- [ ] Synthesis generated
- [ ] Inline citations included
- [ ] Unit tests pass

**Estimated time:** 2 hours

---

#### Task 3.10: Create Deep Research Tool
**Files to create:**
- `tools/research/deep_research.py`

**Steps:**
1. Create `deep_research()` function
2. Initialize orchestrator
3. Execute research
4. Save results
5. Format output

**Code:** (See lines 1380-1450 in current document)

**Acceptance Criteria:**
- [ ] Function works end-to-end
- [ ] Results saved to storage
- [ ] Output formatted correctly
- [ ] Integration tests pass

**Estimated time:** 2 hours

---

#### Task 3.11: Register Deep Research Tool
**Files to modify:**
- `tools/registry.py`

**Steps:**
1. Import `deep_research` function
2. Add to TOOL_FUNCTIONS
3. Add to TOOLS_DEFINITION
4. Add to SPECIALIST_TOOLS

**Code:**
```python
# tools/registry.py
from tools.research.deep_research import deep_research

TOOL_FUNCTIONS = {
    "deep_research": deep_research,
    # ... existing tools
}

SPECIALIST_TOOLS = [
    "deep_research",  # NEW
    "use_codestral",
    # ... existing specialist tools
]

TOOLS_DEFINITION = [
    {
        "type": "function",
        "function": {
            "name": "deep_research",
            "description": "Conduct deep multi-source research with credibility scoring and citation analysis. Searches academic databases, web sources, and newsroom. Returns synthesis with confidence levels.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Research question or topic"
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": "Maximum citation depth (1-3, default: 3)"
                    }
                },
                "required": ["query"]
            }
        }
    },
    # ... existing tool definitions
]
```

**Acceptance Criteria:**
- [ ] Tool registered
- [ ] Can be called via tool_executor
- [ ] Shows up in tool list

**Estimated time:** 15 minutes

---

#### Task 3.12: Add /research Slash Command
**Files to modify:**
- `repl.py`

**Steps:**
1. Add `/research` command handler
2. Call deep_research tool
3. Display results
4. Auto-save research

**Code:**
```python
# repl.py
def _handle_workflow_command(self, command: str):
    """Handle slash commands"""
    cmd_lower = command.lower()

    # ... existing commands ...

    elif cmd_lower.startswith("/research "):
        query = command[10:].strip()

        if not query:
            self.ui.print_error("Usage: /research <query>")
            return ("", 0.0)

        self.ui.print_info(f"Starting deep research: {query}")

        # Execute deep research
        result = self.tool_executor.execute("deep_research", {"query": query})

        # Display results
        self.ui.print_assistant(result)

        return (result, 0.0)
```

**Acceptance Criteria:**
- [ ] `/research` command works
- [ ] Results displayed correctly
- [ ] Integration test passes

**Estimated time:** 30 minutes

---

### Phase 4: Web UI (8 tasks, 3-4 days)

#### Task 4.1: Create Web UI Directory Structure
**Steps:**
```bash
mkdir -p ui/web/templates
mkdir -p ui/web/static/css
mkdir -p ui/web/static/js
touch ui/__init__.py
touch ui/web/__init__.py
touch ui/web/app.py
```

**Acceptance Criteria:**
- [ ] Directory structure created

**Estimated time:** 5 minutes

---

#### Task 4.2: Implement Flask App
**Files to create:**
- `ui/web/app.py`

(Implementation in current document, lines 1461-1499)

**Acceptance Criteria:**
- [ ] Flask app created
- [ ] Routes defined
- [ ] Engine integration works
- [ ] App runs on localhost:5000

**Estimated time:** 2 hours

---

#### Task 4.3: Create Search Page Template
**Files to create:**
- `ui/web/templates/search.html`

(Implementation in current document, lines 1504-1536)

**Acceptance Criteria:**
- [ ] Search box works
- [ ] Depth selector works
- [ ] Form submits correctly

**Estimated time:** 1 hour

---

#### Task 4.4: Create Results Page Template
**Files to create:**
- `ui/web/templates/results.html`

(Implementation in current document, lines 1539-1583)

**Acceptance Criteria:**
- [ ] Results displayed correctly
- [ ] Sources listed
- [ ] Navigation works

**Estimated time:** 2 hours

---

#### Task 4.5: Create History Page Template
**Files to create:**
- `ui/web/templates/history.html`

**Acceptance Criteria:**
- [ ] Past research listed
- [ ] Can click to view details

**Estimated time:** 1 hour

---

#### Task 4.6: Add CSS Styling
**Files to create:**
- `ui/web/static/css/style.css`

**Acceptance Criteria:**
- [ ] Clean, readable design
- [ ] Responsive layout
- [ ] Good typography

**Estimated time:** 2 hours

---

#### Task 4.7: Create Web Entry Point
**Files to create:**
- `web_main.py`

**Code:**
```python
# web_main.py
"""
Zorora Web UI entry point.
Usage: python web_main.py
"""
from ui.web.app import app

if __name__ == '__main__':
    app.run(host='localhost', port=5000, debug=False)
```

**Acceptance Criteria:**
- [ ] Can run with `python web_main.py`
- [ ] Opens web UI

**Estimated time:** 15 minutes

---

#### Task 4.8: Test Web UI End-to-End
**Files to create:**
- `tests/test_web_ui.py`

**Testing:**
```python
# tests/test_web_ui.py
def test_web_ui():
    from ui.web.app import app

    client = app.test_client()

    # Test index
    response = client.get('/')
    assert response.status_code == 200
    assert b'Zorora' in response.data

    # Test search (with mock)
    response = client.get('/search?q=test&depth=1')
    assert response.status_code == 200
```

**Acceptance Criteria:**
- [ ] All routes work
- [ ] Integration tests pass

**Estimated time:** 1 hour

---

### Summary: Total Estimates

| Phase | Tasks | Estimated Time |
|-------|-------|----------------|
| Phase 1: Tool Registry Refactor | 8 tasks | 1-2 days |
| Phase 2: Storage Layer | 6 tasks | 1-2 days |
| Phase 3: Deep Research Core | 12 tasks | 3-5 days |
| Phase 4: Web UI | 8 tasks | 3-4 days |
| **TOTAL** | **34 tasks** | **8-13 days** |

**Assumptions:**
- One developer working full-time
- Includes testing and debugging time
- Assumes familiarity with codebase

**Risk buffer:** Add 20-30% for unexpected issues = **10-17 days total**

---

# APPENDICES: AI Code Generator Ready Specifications

The following appendices provide complete specifications needed for automated code generation without human intervention.

---

## Appendix A: Tool Output Formats & Parsers

### A.1: academic_search() Output Format

**CRITICAL:** The `academic_search()` function returns a **formatted string**, NOT a list or dict!

**Example Output:**
```
Academic search results for: machine learning

1. Deep Learning for Computer Vision
   URL: https://www.nature.com/articles/nature12345
   DOI: 10.1038/nature12345
   Year: 2023 | Citations: 523
   [Full Text] Sci-Hub: https://sci-hub.se/10.1038/nature12345
   Comprehensive analysis of deep learning architectures...

2. Neural Networks and Backpropagation
   URL: https://arxiv.org/abs/2301.12345
   DOI: 10.48550/arXiv.2301.12345
   Year: 2023 | Citations: 2
   Preprint analyzing gradient descent optimization...

Summary: Found 2 papers (1 with full-text access via Sci-Hub)
```

**Required Parser Implementation:**

```python
# Add to workflows/research/parsers.py (NEW FILE)

import re
from typing import List
from engine.models import Source

def parse_academic_search_results(result_str: str) -> List[Source]:
    """
    Parse academic_search string output into Source objects.
    
    Args:
        result_str: Formatted string from academic_search()
        
    Returns:
        List of Source objects with extracted metadata
    """
    sources = []
    
    if not result_str or "No academic results found" in result_str:
        return sources
    
    # Split into lines
    lines = result_str.split('\n')
    current_source = {}
    
    for line in lines:
        line = line.strip()
        
        # New result starts with number
        if re.match(r'^\d+\.\s+', line):
            # Save previous source if exists
            if current_source.get('title'):
                sources.append(_create_source_from_dict(current_source, 'academic', len(sources)))
            
            # Start new source
            current_source = {
                'title': re.sub(r'^\d+\.\s+', '', line),
                'citation_count': 0,
                'year': '',
                'url': '',
                'doi': '',
                'description': ''
            }
        
        elif line.startswith('URL:'):
            current_source['url'] = line.replace('URL:', '').strip()
        
        elif line.startswith('DOI:'):
            current_source['doi'] = line.replace('DOI:', '').strip()
        
        elif 'Citations:' in line:
            # Extract citation count
            match = re.search(r'Citations:\s*(\d+)', line)
            if match:
                current_source['citation_count'] = int(match.group(1))
            
            # Extract year
            match_year = re.search(r'Year:\s*(\d{4})', line)
            if match_year:
                current_source['year'] = match_year.group(1)
        
        elif line.startswith('[Full Text]'):
            # Skip Sci-Hub links
            pass
        
        elif line.startswith('Summary:'):
            # End of results
            break
        
        elif line and not line.startswith('Academic search results'):
            # Description line
            if current_source.get('description'):
                current_source['description'] += ' ' + line
            else:
                current_source['description'] = line
    
    # Add last source
    if current_source.get('title'):
        sources.append(_create_source_from_dict(current_source, 'academic', len(sources)))
    
    return sources

def _create_source_from_dict(data: dict, source_type: str, index: int) -> Source:
    """Helper to create Source from parsed dict"""
    return Source(
        source_id=f"{source_type}_{index}",
        url=data.get('url', ''),
        title=data.get('title', ''),
        source_type=source_type,
        cited_by_count=data.get('citation_count', 0),
        publication_date=data.get('year', ''),
        content_snippet=data.get('description', '')[:500]  # Truncate long descriptions
    )
```

---

### A.2: web_search() Output Format

**CRITICAL:** Returns formatted string, NOT structured data!

**Example Output:**
```
Web search results for: climate change

1. Climate Change: Vital Signs of the Planet
   URL: https://climate.nasa.gov/
   NASA's portal for climate data and research. Includes temperature records, CO2 measurements...

2. IPCC Climate Change Reports
   URL: https://www.ipcc.ch/
   Latest assessment reports on climate science from the Intergovernmental Panel...

Found 2 results
```

**Required Parser:**

```python
# Add to workflows/research/parsers.py

def parse_web_search_results(result_str: str) -> List[Source]:
    """
    Parse web_search string output into Source objects.
    
    Args:
        result_str: Formatted string from web_search()
        
    Returns:
        List of Source objects
    """
    sources = []
    
    if not result_str or "No results found" in result_str:
        return sources
    
    lines = result_str.split('\n')
    current_source = {}
    
    for line in lines:
        line = line.strip()
        
        # New result
        if re.match(r'^\d+\.\s+', line):
            # Save previous
            if current_source.get('title'):
                sources.append(_create_source_from_dict(current_source, 'web', len(sources)))
            
            # Start new
            current_source = {
                'title': re.sub(r'^\d+\.\s+', '', line),
                'url': '',
                'description': ''
            }
        
        elif line.startswith('URL:'):
            current_source['url'] = line.replace('URL:', '').strip()
        
        elif line.startswith('Found'):
            # End of results
            break
        
        elif line and not line.startswith('Web search results'):
            # Description
            if current_source.get('description'):
                current_source['description'] += ' ' + line
            else:
                current_source['description'] = line
    
    # Add last
    if current_source.get('title'):
        sources.append(_create_source_from_dict(current_source, 'web', len(sources)))
    
    return sources
```

---

### A.3: Newsroom API Specification

**Endpoint:** `https://pj1ud6q3uf.execute-api.af-south-1.amazonaws.com/prod/api/data-admin/newsroom/articles`

**Method:** GET

**Authentication:** None required (public endpoint with rate limiting)

**Request Parameters:**
```python
{
    "search": str,       # Search query (optional)
    "limit": int,        # Max results (default: 50, max: 200)
    "date_from": str,    # YYYY-MM-DD format (optional)
    "date_to": str,      # YYYY-MM-DD format (optional)
    "geography": str,    # Geography filter (optional)
    "topic": str,        # Topic filter (optional)
    "country": str,      # Country filter (optional)
    "page": int          # Page number (default: 1)
}
```

**Response Format:**
```json
{
  "articles": [
    {
      "headline": "UN Climate Summit Reaches Historic Agreement",
      "date": "2025-01-15",
      "topic_tags": ["Climate", "Policy", "Environment"],
      "geography_tags": ["Global", "Europe"],
      "country_tags": ["Multiple Countries"],
      "url": "https://reuters.com/article/climate-summit-2025",
      "source": "Reuters"
    }
  ],
  "pagination": {
    "page": 1,
    "total": 150,
    "total_pages": 3,
    "has_next": true
  }
}
```

**Parser Implementation:**

```python
# Add to workflows/research/parsers.py

import requests
from datetime import datetime, timedelta

def fetch_and_parse_newsroom(query: str, days_back: int = 90, max_results: int = 25) -> List[Source]:
    """
    Fetch from newsroom API and parse into Source objects.
    
    Args:
        query: Search query
        days_back: How many days to search back
        max_results: Max results to return
        
    Returns:
        List of Source objects
    """
    try:
        # Calculate date range
        date_from = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
        
        # Call API
        response = requests.get(
            'https://pj1ud6q3uf.execute-api.af-south-1.amazonaws.com/prod/api/data-admin/newsroom/articles',
            params={
                'search': query,
                'limit': max_results,
                'date_from': date_from
            },
            timeout=10
        )
        
        if response.status_code != 200:
            return []
        
        # Parse response
        data = response.json()
        articles = data.get('articles', [])
        
        return parse_newsroom_articles(articles)
        
    except Exception as e:
        # Graceful degradation - newsroom is optional
        import logging
        logging.warning(f"Newsroom API unavailable: {e}")
        return []

def parse_newsroom_articles(articles: list) -> List[Source]:
    """
    Parse newsroom API articles into Source objects.
    
    Args:
        articles: List of article dicts from API
        
    Returns:
        List of Source objects
    """
    sources = []
    
    for i, article in enumerate(articles):
        # Build content snippet from metadata
        tags = article.get('topic_tags', [])
        geo = article.get('geography_tags', [])
        source_name = article.get('source', 'Unknown')
        
        snippet_parts = [f"Source: {source_name}"]
        if tags:
            snippet_parts.append(f"Topics: {', '.join(tags[:3])}")  # First 3 tags
        if geo:
            snippet_parts.append(f"Geography: {', '.join(geo[:2])}")
        
        sources.append(Source(
            source_id=f"newsroom_{i}",
            url=article.get('url', ''),
            title=article.get('headline', ''),
            source_type='newsroom',
            publication_date=article.get('date', ''),
            content_snippet=' | '.join(snippet_parts)
        ))
    
    return sources
```

---

## Appendix B: Dependencies

### B.1: requirements.txt Updates

Add these lines to `/Users/shingi/Workbench/zorora/requirements.txt`:

```txt
# Existing dependencies
requests>=2.31.0
rich>=13.7.0
beautifulsoup4>=4.11.0

# NEW - Deep Research Feature
# (No additional Python packages needed!)
# Flask for web UI (optional - only if implementing Phase 4)
Flask>=3.0.0
Jinja2>=3.1.2
```

**Key Point:** The core deep research feature requires NO new dependencies! It uses:
- `sqlite3` (Python stdlib)
- `json` (Python stdlib)
- `re` (Python stdlib)
- `concurrent.futures` (Python stdlib)
- `requests` (already installed)

Only the **web UI** (Phase 4) requires Flask/Jinja2, and that's optional.

---

### B.2: Python Version

**Minimum:** Python 3.8+

**Recommended:** Python 3.10+

**Reason:** Uses dataclasses with `field(default_factory=...)` syntax (Python 3.7+)

---

## Appendix C: Configuration

### C.1: config.py Additions

Add these configuration values to `/Users/shingi/Workbench/zorora/config.py`:

```python
# ============================================================================
# DEEP RESEARCH CONFIGURATION
# ============================================================================

# Research Workflow Settings
DEEP_RESEARCH = {
    "default_max_depth": 2,              # Citation following depth (1-3)
    "default_max_sources": 50,           # Max sources to collect per research
    "enable_citation_following": True,   # Enable Phase 2 (multi-hop)
    "enable_cross_referencing": True,    # Enable Phase 3
    "parallel_workers": 3,               # ThreadPoolExecutor workers for source aggregation
    "max_findings": 50,                  # Max cross-referenced findings to keep
    "synthesis_max_sources": 15          # Max sources to include in synthesis prompt
}

# Storage Paths (None = use defaults)
STORAGE_DB_PATH = None                   # None = ~/.zorora/zorora.db
STORAGE_JSON_PATH = None                 # None = ~/.zorora/research/findings/

# Newsroom API Configuration
NEWSROOM_API_URL = "https://pj1ud6q3uf.execute-api.af-south-1.amazonaws.com/prod/api/data-admin/newsroom/articles"
NEWSROOM_API_TIMEOUT = 10                # seconds
NEWSROOM_DEFAULT_DAYS_BACK = 90          # Default search range
NEWSROOM_DEFAULT_MAX_RESULTS = 25        # Default max articles

# Web UI Configuration (Phase 4 - Optional)
WEB_UI_ENABLED = False                   # Set to True to enable web interface
WEB_UI_PORT = 5000
WEB_UI_HOST = "127.0.0.1"               # localhost only (single-user)
WEB_UI_DEBUG = False                     # Set to True for development only

# Credibility Scoring
CREDIBILITY_SCORING = {
    "enable_retraction_check": True,     # Check for retracted papers
    "enable_predatory_check": True,      # Check for predatory publishers
    "citation_weight": 1.0,              # Weight for citation modifier (0.8x - 1.2x)
    "cross_ref_weight": 1.0,             # Weight for cross-reference modifier (0.9x - 1.15x)
    "max_score": 0.95                    # Cap credibility score (never 1.0)
}
```

---

### C.2: Environment Variables (Optional)

Create `.env.example` (for users who want to customize):

```bash
# Deep Research Configuration
DEEP_RESEARCH_MAX_DEPTH=2
DEEP_RESEARCH_MAX_SOURCES=50

# Storage Paths (optional overrides)
# STORAGE_DB_PATH=/custom/path/zorora.db
# STORAGE_JSON_PATH=/custom/path/findings/

# Newsroom API
NEWSROOM_API_TIMEOUT=10

# Web UI (Phase 4)
WEB_UI_ENABLED=false
WEB_UI_PORT=5000
WEB_UI_DEBUG=false
```

**Note:** Environment variables are OPTIONAL. Config values in `config.py` are sufficient for MVP.

---

## Appendix D: Missing Implementation Details

### D.1: Phase 2 - Citation Following

**File:** `workflows/research/research_orchestrator.py`

**Current Status:** Method exists but raises `NotImplementedError`

**MVP Implementation (Simplified):**

```python
def _follow_citations(self, state):
    """
    Phase 2: Follow citations (multi-hop research)
    
    MVP VERSION: Simplified - skips actual citation extraction
    Full implementation would:
    1. Extract DOIs/URLs from paper content
    2. Query academic_search for cited papers
    3. Add to sources_checked
    
    For MVP: Skip this phase (citation following is complex)
    """
    if self.max_depth <= 1:
        logger.info("Skipping citation following (max_depth=1)")
        return
    
    logger.info(f"Citation following enabled (max_depth={self.max_depth})")
    logger.info("MVP: Citation following not yet implemented - skipping")
    
    # TODO for production:
    # 1. Extract citations from top academic papers
    # 2. For each citation:
    #    - Query academic_search(doi=citation_doi)
    #    - Parse results
    #    - Add to state.sources_checked
    # 3. Repeat for each depth level
    
    return  # Skip for MVP
```

**Acceptance Criteria for MVP:**
- ✅ Method doesn't crash
- ✅ Logs that it's skipping
- ✅ Returns gracefully
- ❌ Actual citation following (for v2.0)

---

### D.2: Phase 3 - Cross-Referencing

**File:** `workflows/research/research_orchestrator.py`

**Current Status:** Method exists but raises `NotImplementedError`

**MVP Implementation:**

```python
def _cross_reference_findings(self, state):
    """
    Phase 3: Cross-reference claims across sources
    
    MVP VERSION: Simple keyword-based matching
    Full implementation would use NLP for semantic similarity
    """
    from collections import defaultdict
    import re
    
    logger.info("Cross-referencing findings...")
    
    # Extract keywords from each source
    keyword_sources = defaultdict(set)  # keyword -> set of source_ids
    
    for source in state.sources_checked:
        # Combine title and snippet
        text = f"{source.title} {source.content_snippet}".lower()
        
        # Extract significant words (4+ characters)
        # Filter common words
        stop_words = {'this', 'that', 'with', 'from', 'have', 'been', 'were', 
                     'will', 'your', 'about', 'what', 'which', 'their', 'there'}
        
        words = re.findall(r'\b\w{4,}\b', text)
        significant_words = [w for w in words if w not in stop_words]
        
        # Track which sources mention each keyword
        for word in set(significant_words):  # Unique words only
            keyword_sources[word].add(source.source_id)
    
    # Create findings for keywords mentioned by 2+ sources
    findings_created = 0
    
    for keyword, source_ids in keyword_sources.items():
        if len(source_ids) >= 2:  # Cross-referenced across 2+ sources
            # Calculate average credibility of sources mentioning this keyword
            relevant_sources = [s for s in state.sources_checked if s.source_id in source_ids]
            avg_cred = sum(s.credibility_score for s in relevant_sources) / len(relevant_sources)
            
            # Determine confidence level
            if len(source_ids) >= 4 and avg_cred >= 0.7:
                confidence = "high"
            elif len(source_ids) >= 2 and avg_cred >= 0.5:
                confidence = "medium"
            else:
                confidence = "low"
            
            # Create finding
            finding = Finding(
                claim=f"Multiple sources discuss '{keyword}'",
                sources=list(source_ids),
                confidence=confidence,
                average_credibility=avg_cred
            )
            state.findings.append(finding)
            findings_created += 1
            
            # Limit findings to prevent overwhelming synthesis
            if findings_created >= 50:
                break
    
    logger.info(f"Created {len(state.findings)} cross-referenced findings from {len(keyword_sources)} keywords")
```

**Acceptance Criteria for MVP:**
- ✅ Extracts keywords from sources
- ✅ Identifies cross-references (2+ sources)
- ✅ Calculates average credibility
- ✅ Creates Finding objects
- ✅ Limits to 50 findings max
- ❌ Advanced NLP (for v2.0)

---

### D.3: Phase 6 - Synthesis

**File:** `workflows/research/research_orchestrator.py`

**Current Status:** Method exists but raises `NotImplementedError`

**MVP Implementation:**

```python
def _synthesize_findings(self, state):
    """
    Phase 6: Synthesize findings into coherent summary
    
    MVP VERSION: Simple template-based synthesis
    Full implementation would call LLM for intelligent synthesis
    """
    logger.info("Synthesizing findings...")
    
    # Get top authoritative sources
    top_sources = state.get_authoritative_sources(top_n=10)
    
    # Format synthesis (template-based for MVP)
    synthesis_parts = []
    
    # Header
    synthesis_parts.append(f"# Deep Research: {state.original_query}\n")
    synthesis_parts.append(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    synthesis_parts.append(f"Sources analyzed: {state.total_sources}\n")
    synthesis_parts.append(f"Cross-referenced findings: {len(state.findings)}\n")
    
    # Top findings (by confidence and credibility)
    high_conf = [f for f in state.findings if f.confidence == "high"]
    med_conf = [f for f in state.findings if f.confidence == "medium"]
    
    if high_conf:
        synthesis_parts.append("\n## High Confidence Findings\n")
        for finding in high_conf[:5]:  # Top 5
            synthesis_parts.append(f"- {finding.claim}")
            synthesis_parts.append(f"  (Credibility: {finding.average_credibility:.2f}, {len(finding.sources)} sources)\n")
    
    if med_conf:
        synthesis_parts.append("\n## Medium Confidence Findings\n")
        for finding in med_conf[:5]:  # Top 5
            synthesis_parts.append(f"- {finding.claim}")
            synthesis_parts.append(f"  (Credibility: {finding.average_credibility:.2f}, {len(finding.sources)} sources)\n")
    
    # Top sources
    synthesis_parts.append("\n## Most Authoritative Sources\n")
    for i, source in enumerate(top_sources[:10], 1):
        synthesis_parts.append(f"\n{i}. {source.title}")
        synthesis_parts.append(f"   URL: {source.url}")
        synthesis_parts.append(f"   Credibility: {source.credibility_score:.2f} ({source.credibility_category})")
        if source.cited_by_count > 0:
            synthesis_parts.append(f" | Citations: {source.cited_by_count}")
        synthesis_parts.append("")
    
    # TODO for production: Call LLM for intelligent synthesis
    # synthesis_parts.append("\n## AI Synthesis\n")
    # synthesis_parts.append(call_llm_for_synthesis(state))
    
    state.synthesis = "\n".join(synthesis_parts)
    logger.info(f"Synthesis complete ({len(state.synthesis)} characters)")

def _format_findings_for_synthesis(self, state):
    """Format findings for LLM prompt (future use)"""
    lines = []
    for i, finding in enumerate(state.findings[:15], 1):
        lines.append(
            f"{i}. {finding.claim} "
            f"(confidence: {finding.confidence}, "
            f"avg credibility: {finding.average_credibility:.2f}, "
            f"{len(finding.sources)} sources)"
        )
    return "\n".join(lines) if lines else "No cross-referenced findings"

def _format_credibility_scores(self, state):
    """Format source credibility for LLM prompt (future use)"""
    lines = []
    for source in state.get_authoritative_sources(top_n=10):
        lines.append(f"- {source.title} ({source.url})")
        lines.append(f"  Credibility: {source.credibility_score:.2f} ({source.credibility_category})")
    return "\n".join(lines)
```

**Acceptance Criteria for MVP:**
- ✅ Creates structured synthesis
- ✅ Shows high/medium confidence findings
- ✅ Lists top authoritative sources
- ✅ Formats as readable markdown
- ❌ LLM-based synthesis (for v2.0 when LLM integration ready)

---

## Appendix E: Integration with Existing Codebase

### E.1: How to Call Existing Tools

The orchestrator needs to import and call existing tools from `tool_registry.py`:

```python
# In workflows/research/research_orchestrator.py

def _aggregate_sources(self, query, state):
    """Phase 1: Aggregate sources from academic, web, newsroom"""
    from tools.research.academic_search import academic_search
    from tools.research.web_search import web_search
    from workflows.research.parsers import (
        parse_academic_search_results,
        parse_web_search_results,
        fetch_and_parse_newsroom
    )
    
    # IMPORTANT: These functions return STRINGS, not objects!
    # We must parse the strings into Source objects
    
    results = {}
    
    with ThreadPoolExecutor(max_workers=3) as executor:
        # Submit all 3 searches in parallel
        future_academic = executor.submit(academic_search, query, 20)
        future_web = executor.submit(web_search, query, 10)
        future_newsroom = executor.submit(fetch_and_parse_newsroom, query, 90, 25)
        
        # Wait for results
        try:
            # Academic (returns string)
            academic_str = future_academic.result(timeout=30)
            academic_sources = parse_academic_search_results(academic_str)
            results['academic'] = academic_sources
            logger.info(f"✓ Academic: {len(academic_sources)} sources")
        except Exception as e:
            logger.warning(f"Academic search failed: {e}")
            results['academic'] = []
        
        try:
            # Web (returns string)
            web_str = future_web.result(timeout=15)
            web_sources = parse_web_search_results(web_str)
            results['web'] = web_sources
            logger.info(f"✓ Web: {len(web_sources)} sources")
        except Exception as e:
            logger.warning(f"Web search failed: {e}")
            results['web'] = []
        
        try:
            # Newsroom (returns Source objects directly)
            newsroom_sources = future_newsroom.result(timeout=15)
            results['newsroom'] = newsroom_sources
            logger.info(f"✓ Newsroom: {len(newsroom_sources)} sources")
        except Exception as e:
            logger.warning(f"Newsroom search failed: {e}")
            results['newsroom'] = []
    
    # Add all sources to state
    for source_list in results.values():
        for source in source_list:
            state.add_source(source)
    
    logger.info(f"Total sources aggregated: {state.total_sources}")
```

---

### E.2: How deep_research Integrates with REPL

**CRITICAL:** The REPL expects tools to return **strings**, not objects!

```python
# tools/research/deep_research.py

def deep_research(query: str, max_depth: int = 2) -> str:
    """
    Main entry point for deep research tool.
    
    IMPORTANT: Must return STRING (REPL contract requirement!)
    
    Args:
        query: Research question
        max_depth: Citation following depth (1-3)
        
    Returns:
        Formatted research results as string
    """
    import logging
    from workflows.research.research_orchestrator import ResearchOrchestrator
    from engine.storage import LocalStorage
    
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"Starting deep research: {query}")
        
        # Execute research workflow
        orchestrator = ResearchOrchestrator(max_depth=max_depth)
        state = orchestrator.execute(query)
        
        # Save to storage
        storage = LocalStorage()
        research_id = storage.save_research(state)
        
        logger.info(f"Research saved: {research_id}")
        
        # Format output as STRING (required by REPL!)
        output = format_research_output(state, research_id)
        
        return output
        
    except Exception as e:
        logger.error(f"Deep research failed: {e}")
        import traceback
        traceback.print_exc()
        return f"Error: Deep research failed - {str(e)}"


def format_research_output(state, research_id: str) -> str:
    """
    Format research results as readable string.
    
    Returns:
        Formatted string for terminal display
    """
    from datetime import datetime
    
    lines = []
    
    # Header
    lines.append("=" * 80)
    lines.append(f"DEEP RESEARCH RESULTS")
    lines.append("=" * 80)
    lines.append(f"Query: {state.original_query}")
    lines.append(f"Research ID: {research_id}")
    lines.append(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Sources: {state.total_sources} | Depth: {state.max_depth}")
    lines.append("=" * 80)
    lines.append("")
    
    # Synthesis (already formatted in Phase 6)
    lines.append(state.synthesis)
    lines.append("")
    
    # Footer
    lines.append("=" * 80)
    lines.append(f"Research saved to: ~/.zorora/research/findings/{research_id}.json")
    lines.append(f"View again: /research-view {research_id}")
    lines.append("=" * 80)
    
    return "\n".join(lines)
```

---

### E.3: Tool Registration

**File:** `tools/registry.py`

Add deep_research to tool registry:

```python
# tools/registry.py

from tools.research.deep_research import deep_research

TOOL_FUNCTIONS = {
    # ... existing tools ...
    "deep_research": deep_research,
}

# Mark as specialist tool (bypasses orchestrator loop)
SPECIALIST_TOOLS = [
    "use_codestral",
    "deep_research",  # NEW
    # ... other specialist tools ...
]

# Tool definition for LLM
TOOLS_DEFINITION = [
    # ... existing tool definitions ...
    {
        "type": "function",
        "function": {
            "name": "deep_research",
            "description": (
                "Conduct comprehensive multi-source research with credibility scoring. "
                "Searches academic databases (7 sources), web (Brave + DDG), and Asoba newsroom. "
                "Follows citations, cross-references claims, builds citation graphs, and synthesizes findings. "
                "Returns detailed analysis with confidence levels and source credibility scores. "
                "Use for: research questions, fact-checking, literature reviews, topic exploration."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Research question or topic to investigate"
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": "Citation following depth: 1 (quick), 2 (balanced), 3 (thorough). Default: 2",
                        "enum": [1, 2, 3],
                        "default": 2
                    }
                },
                "required": ["query"]
            }
        }
    },
]
```

---

### E.4: REPL Slash Command (Optional)

**File:** `repl.py`

Add `/research` command for direct access:

```python
# In repl.py (wherever slash commands are handled)

def handle_slash_command(self, command: str):
    """Handle slash commands"""
    cmd_lower = command.lower().strip()
    
    # ... existing commands ...
    
    if cmd_lower.startswith('/research '):
        query = command[10:].strip()  # Remove '/research '
        
        if not query:
            print("Usage: /research <query>")
            print("Example: /research climate change impacts on agriculture")
            return
        
        print(f"Starting deep research: {query}")
        print("This may take 30-70 seconds...")
        
        # Call deep_research tool
        result = deep_research(query, max_depth=2)
        
        # Display results
        print(result)
        
        return
```

---

## Appendix F: Test Fixtures & Mock Data

### F.1: Mock academic_search Output

For testing parsers without API calls:

```python
# tests/fixtures/mock_outputs.py

MOCK_ACADEMIC_OUTPUT = """Academic search results for: machine learning

1. Deep Learning for Computer Vision Applications
   URL: https://www.nature.com/articles/nature12345
   DOI: 10.1038/nature12345
   Year: 2023 | Citations: 523
   [Full Text] Sci-Hub: https://sci-hub.se/10.1038/nature12345
   Comprehensive analysis of deep learning architectures for image recognition tasks.

2. Neural Networks and Backpropagation Algorithms
   URL: https://arxiv.org/abs/2301.12345
   DOI: 10.48550/arXiv.2301.12345
   Year: 2023 | Citations: 2
   Preprint analyzing gradient descent optimization techniques in neural networks.

3. Machine Learning in Healthcare: A Survey
   URL: https://pubmed.ncbi.nlm.nih.gov/12345678/
   DOI: 10.1016/j.health.2023.001
   Year: 2022 | Citations: 89
   Survey of machine learning applications in medical diagnosis and treatment planning.

Summary: Found 3 papers (1 with full-text access via Sci-Hub)
"""

MOCK_ACADEMIC_OUTPUT_EMPTY = """No academic results found for: asdfjkl12345

Try:
- Using more specific keywords
- Checking spelling
- Using academic terminology
"""
```

---

### F.2: Mock web_search Output

```python
# tests/fixtures/mock_outputs.py

MOCK_WEB_OUTPUT = """Web search results for: climate change

1. Climate Change: Vital Signs of the Planet
   URL: https://climate.nasa.gov/
   NASA's portal for climate data and research. Includes temperature records, CO2 measurements, sea level data, and scientific consensus information.

2. IPCC — Intergovernmental Panel on Climate Change
   URL: https://www.ipcc.ch/
   Latest assessment reports on climate science from the world's leading climate scientists. Comprehensive reviews of climate research and policy recommendations.

3. What Is Climate Change? | United Nations
   URL: https://www.un.org/en/climatechange/what-is-climate-change
   Overview of climate change causes, impacts, and solutions. Includes information on global temperature rise, extreme weather events, and mitigation strategies.

Found 3 results
"""

MOCK_WEB_OUTPUT_EMPTY = """No results found for: asdfjkl12345"""
```

---

### F.3: Mock Newsroom API Response

```python
# tests/fixtures/mock_outputs.py

MOCK_NEWSROOM_RESPONSE = {
    "articles": [
        {
            "headline": "UN Climate Summit Reaches Historic Agreement on Emissions",
            "date": "2025-01-15",
            "topic_tags": ["Climate", "Policy", "Environment"],
            "geography_tags": ["Global", "Europe"],
            "country_tags": ["Multiple Countries"],
            "url": "https://reuters.com/article/climate-summit-2025",
            "source": "Reuters"
        },
        {
            "headline": "New Study Reveals Accelerated Arctic Ice Melt",
            "date": "2025-01-14",
            "topic_tags": ["Climate", "Science", "Arctic"],
            "geography_tags": ["Arctic", "North America"],
            "country_tags": ["United States", "Canada"],
            "url": "https://bloomberg.com/article/arctic-ice-study",
            "source": "Bloomberg"
        },
        {
            "headline": "Renewable Energy Investments Reach Record Highs",
            "date": "2025-01-13",
            "topic_tags": ["Energy", "Climate", "Investment"],
            "geography_tags": ["Global"],
            "country_tags": ["Multiple Countries"],
            "url": "https://ft.com/article/renewable-energy-investment",
            "source": "Financial Times"
        }
    ],
    "pagination": {
        "page": 1,
        "total": 3,
        "total_pages": 1,
        "has_next": false
    }
}

MOCK_NEWSROOM_RESPONSE_EMPTY = {
    "articles": [],
    "pagination": {
        "page": 1,
        "total": 0,
        "total_pages": 0,
        "has_next": false
    }
}
```

---

### F.4: Test Cases Using Fixtures

```python
# tests/test_parsers.py

import pytest
from workflows.research.parsers import (
    parse_academic_search_results,
    parse_web_search_results,
    parse_newsroom_articles
)
from tests.fixtures.mock_outputs import (
    MOCK_ACADEMIC_OUTPUT,
    MOCK_ACADEMIC_OUTPUT_EMPTY,
    MOCK_WEB_OUTPUT,
    MOCK_WEB_OUTPUT_EMPTY,
    MOCK_NEWSROOM_RESPONSE
)

def test_parse_academic_search():
    """Test academic search parser with mock data"""
    sources = parse_academic_search_results(MOCK_ACADEMIC_OUTPUT)
    
    assert len(sources) == 3
    
    # Check first source (Nature paper)
    assert sources[0].title == "Deep Learning for Computer Vision Applications"
    assert sources[0].url == "https://www.nature.com/articles/nature12345"
    assert sources[0].cited_by_count == 523
    assert sources[0].publication_date == "2023"
    assert sources[0].source_type == "academic"
    
    # Check second source (ArXiv preprint)
    assert sources[1].cited_by_count == 2
    assert "arxiv" in sources[1].url

def test_parse_academic_search_empty():
    """Test parser with no results"""
    sources = parse_academic_search_results(MOCK_ACADEMIC_OUTPUT_EMPTY)
    assert len(sources) == 0

def test_parse_web_search():
    """Test web search parser"""
    sources = parse_web_search_results(MOCK_WEB_OUTPUT)
    
    assert len(sources) == 3
    assert sources[0].title == "Climate Change: Vital Signs of the Planet"
    assert sources[0].url == "https://climate.nasa.gov/"
    assert sources[0].source_type == "web"

def test_parse_newsroom():
    """Test newsroom parser"""
    articles = MOCK_NEWSROOM_RESPONSE['articles']
    sources = parse_newsroom_articles(articles)
    
    assert len(sources) == 3
    assert sources[0].title == "UN Climate Summit Reaches Historic Agreement on Emissions"
    assert sources[0].url == "https://reuters.com/article/climate-summit-2025"
    assert sources[0].source_type == "newsroom"
    assert "Reuters" in sources[0].content_snippet
```

---

### F.5: End-to-End Test Scenario

```python
# tests/test_end_to_end.py

def test_deep_research_end_to_end_with_mocks(monkeypatch):
    """
    End-to-end test using all mock data.
    Tests complete workflow without external API calls.
    """
    from tools.research.deep_research import deep_research
    from tests.fixtures.mock_outputs import (
        MOCK_ACADEMIC_OUTPUT,
        MOCK_WEB_OUTPUT,
        MOCK_NEWSROOM_RESPONSE
    )
    
    # Mock external tool calls
    def mock_academic_search(query, max_results):
        return MOCK_ACADEMIC_OUTPUT
    
    def mock_web_search(query, max_results):
        return MOCK_WEB_OUTPUT
    
    def mock_fetch_newsroom(query, days_back, max_results):
        from workflows.research.parsers import parse_newsroom_articles
        return parse_newsroom_articles(MOCK_NEWSROOM_RESPONSE['articles'])
    
    # Apply mocks
    monkeypatch.setattr('tools.research.academic_search.academic_search', mock_academic_search)
    monkeypatch.setattr('tools.research.web_search.web_search', mock_web_search)
    monkeypatch.setattr('workflows.research.parsers.fetch_and_parse_newsroom', mock_fetch_newsroom)
    
    # Execute deep research
    result = deep_research("climate change", max_depth=1)
    
    # Assertions
    assert isinstance(result, str)  # Returns string (REPL contract)
    assert "DEEP RESEARCH RESULTS" in result
    assert "climate change" in result.lower()
    assert "Sources:" in result or "sources" in result.lower()
    
    # Should contain synthesis
    assert len(result) > 500  # Non-trivial output
    
    print("End-to-end test passed!")
    print(result)
```

---

## Summary: AI Code Generator Readiness Checklist

With these appendices, an AI code generator can now produce working code because it has:

- ✅ **Appendix A:** Exact output formats from existing tools
- ✅ **Appendix A:** Complete parser implementations
- ✅ **Appendix B:** Dependency specifications (minimal!)
- ✅ **Appendix C:** Configuration values with defaults
- ✅ **Appendix D:** Missing implementation code (Phases 2, 3, 6)
- ✅ **Appendix E:** Integration points with existing codebase
- ✅ **Appendix E:** REPL contract (return strings, not objects)
- ✅ **Appendix E:** Tool registration pattern
- ✅ **Appendix F:** Mock data for testing without APIs
- ✅ **Appendix F:** Complete test cases

**Result:** An AI can now:
1. Read this document
2. Generate all files
3. Run tests with mock data
4. Produce a **working** (not production-ready) implementation
5. Without human intervention

**What's still needed for production:**
- LLM integration for synthesis (Phase 6)
- Advanced citation extraction (Phase 2)
- NLP-based cross-referencing (Phase 3)
- Web UI (Phase 4) - optional
- Performance optimization
- Error handling hardening
- Security review

But the **core workflow will function** with the MVP implementations provided.

