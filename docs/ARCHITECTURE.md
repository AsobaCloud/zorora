# Architecture

## Overview

Zorora uses **deterministic routing** with pattern matching instead of LLM-based orchestration. This design choice enables reliable operation with small 4B models while maintaining RAM efficiency.

## Design Philosophy

- **Deterministic over clever** - Code-controlled workflows, not LLM orchestration
- **Research-first** - Optimized for multi-source synthesis and citation management
- **RAM-efficient** - Runs on MacBook Air with 4B orchestrator model
- **Persistent knowledge** - Save and retrieve research findings locally
- **Simple and reliable** - Hardcoded pipelines that just work

## Architecture Diagram

```
User Query / Slash Command
    ↓
Deterministic Decision Tree (pattern matching)
    ↓
    ├─→ RESEARCH WORKFLOW (newsroom + web + synthesis)
    │   └─→ Save to ~/.zorora/research/
    │
    ├─→ DEVELOPMENT WORKFLOW (/develop - multi-step code dev)
    │   ├─→ Phase 1: Explore codebase
    │   ├─→ Phase 2: Plan changes (with approval)
    │   ├─→ Phase 3: Execute with Codestral
    │   └─→ Phase 4: Lint & validate
    │
    ├─→ CODE WORKFLOW (code generation)
    │   └─→ Codestral specialist model
    │
    ├─→ FILE OPERATIONS (save/load/list)
    │   └─→ Research or filesystem operations
    │
    ├─→ IMAGE WORKFLOWS (generate/analyze)
    │   ├─→ FLUX for image generation
    │   └─→ Vision model for analysis
    │
    └─→ SIMPLE Q&A (/ask - no search)
        └─→ Direct model response
```

## Key Principles

- **No LLM-based orchestration** - Patterns determine routing, code controls execution
- **Hardcoded workflows** - Fixed pipelines for predictable results (newsroom → web → synthesis)
- **Persistent research** - Everything saved to `~/.zorora/research/` with metadata
- **Specialist models** - Codestral for code, reasoning model for synthesis
- **Hybrid inference** - Mix local models (4B orchestrator) with remote HuggingFace endpoints (32B Codestral)

## Core Components

### 1. Simplified Router (`simplified_router.py`)

Uses pattern matching to route queries to workflows:

```python
def route(self, user_input: str) -> Dict[str, Any]:
    # Priority 1: File operations (save, load, list, show)
    if re.search(r'\b(save|load|list|show|delete)\b', user_input.lower()):
        return {"workflow": "file_op", "action": "..."}

    # Priority 2: Code generation (write, create, generate + code)
    if re.search(r'\b(write|create|generate).*\b(function|class|script|code)', user_input.lower()):
        return {"workflow": "code", "tool": "use_codestral"}

    # Priority 3: Research (questions, multi-source queries)
    if re.search(r'\b(what|why|how|tell me|based on|newsroom|web search)\b', user_input.lower()):
        return {"workflow": "research", "action": "multi_source_research"}

    # Priority 4: Simple Q&A (fallback)
    return {"workflow": "qa", "tool": "use_reasoning_model"}
```

**No LLM involved** - Pure pattern matching ensures consistent, fast routing.

### 2. Research Workflow (`research_workflow.py`)

Hardcoded pipeline for multi-source research:

```python
def execute(self, query: str) -> str:
    sources = []

    # Step 1: Try newsroom (skip if unavailable)
    newsroom = self._fetch_newsroom()
    if newsroom:
        sources.append(("Newsroom", newsroom))

    # Step 2: Web search (always)
    web = self._fetch_web(self._extract_keywords(query))
    sources.append(("Web", web))

    # Step 3: Synthesize with citations
    return self._synthesize(query, sources)
```

### 3. Turn Processor (`turn_processor.py`)

Main workflow orchestration that:
- Processes user input
- Routes to appropriate workflow
- Executes tools
- Manages conversation context

### 4. Tool Registry (`tool_registry.py`)

Defines all available tools:
- Research tools: `web_search()`, `get_newsroom_headlines()`
- Code tools: `use_codestral()`
- File tools: `save_research()`, `load_research()`, `list_research()`
- General tools: `use_reasoning_model()`, `analyze_image()`, `generate_image()`

### 5. Workflows (`workflows/`)

Multi-step development workflow:
- `develop_workflow.py` - Main orchestrator
- `codebase_explorer.py` - Phase 1: Code exploration
- `code_planner.py` - Phase 2: Planning with approval
- `code_executor.py` - Phase 4: Code execution
- `code_tools.py` - File operations and linting

## Execution Flow

### Research Workflow

```
Query
  ↓
[Step 1/3] Fetch newsroom articles
  ↓
[Step 2/3] Web search (Brave/DuckDuckGo)
  ↓
[Step 3/3] Synthesize with citations
  ↓
Result (with [Newsroom] and [Web] tags)
```

### Code Workflow

```
Query → Codestral specialist model → Formatted code output
```

### Development Workflow

```
/develop <request>
  ↓
Phase 1: Explore codebase (codebase_explorer.py)
  ↓
Phase 2: Plan changes (code_planner.py)
  ↓
[User Approval Required]
  ↓
Phase 3: Execute changes (code_executor.py)
  ↓
Phase 4: Lint & validate (code_tools.py)
```

## No Multi-Iteration Loops

Unlike complex orchestration systems, Zorora executes workflows **once** and returns the result. No planning, no iteration loops, no LLM deciding "should I call another tool?"

**Old approach (unreliable with 4B models):**
```
Query → LLM plans → LLM calls tool 1 → LLM decides next step → LLM calls tool 2 → ...
```

**New approach (deterministic):**
```
Query → Pattern match → Execute fixed pipeline → Return result
```

## Synthesis with Citations

The reasoning model synthesizes findings from all sources:

```python
def _synthesize(self, query: str, sources: List[Tuple[str, str]]) -> str:
    prompt = f"""
    SOURCES:
    [Newsroom]: {newsroom_content}
    [Web]: {web_content}

    QUESTION: {query}

    Synthesize findings from ALL sources above.
    Cite sources using [Newsroom] or [Web] tags.
    """
    return llm_client.chat_complete(prompt)
```

## Why This Architecture?

### Problem: 4B Models Can't Orchestrate

Traditional multi-model orchestration requires the LLM to:
- Generate valid JSON plans
- Make routing decisions
- Handle multi-step iteration
- Recover from tool failures

**4B models fail at all of these.** They can't reliably generate JSON, struggle with function calling, and get stuck in loops.

### Solution: Code Handles Complexity

Instead of asking the 4B model to be smart, we made the **code smart**:
- Pattern matching routes queries (no LLM decision)
- Hardcoded workflows execute pipelines (no LLM planning)
- Fixed iteration count (no LLM loop detection)
- Deterministic error handling (no LLM recovery)

**Result:** 100% reliability with 4B models, 1/3 the RAM usage of 8B orchestrators.

### Trade-offs

**What we lost:**
- Flexibility for complex multi-tool queries
- LLM creativity in tool selection
- Adaptive workflows based on results

**What we gained:**
- 100% routing reliability (pattern matching never fails)
- Predictable behavior (same query = same workflow)
- RAM efficiency (4B model = 4-6 GB vs 8B = 12-16 GB)
- Simple debugging (no "why did it choose that tool?")
- Fast responses (no LLM routing overhead)

## Module Structure

```
zorora/
├── main.py                      # Entry point
├── repl.py                      # REPL loop and slash commands
├── config.py                    # Configuration and model settings
│
├── conversation.py              # Conversation manager
├── conversation_persistence.py  # Save/load conversations
├── llm_client.py               # LM Studio/HF API client
├── ui.py                       # Rich terminal UI
│
├── simplified_router.py        # Deterministic decision tree
├── research_workflow.py        # Hardcoded research pipeline
├── research_persistence.py     # Save/load research findings
│
├── turn_processor.py           # Main workflow orchestration
├── tool_executor.py            # Tool execution engine
├── tool_registry.py            # Tool definitions and functions
├── model_selector.py           # Interactive model configuration
│
└── workflows/                  # Multi-step development workflows
    ├── __init__.py
    ├── develop_workflow.py     # /develop orchestrator
    ├── codebase_explorer.py    # Phase 1: Code exploration
    ├── code_planner.py         # Phase 2: Planning with approval
    ├── code_executor.py        # Phase 4: Code execution
    └── code_tools.py           # File operations and linting
```

## Performance

- **Routing decision:** 0ms (pattern matching, no LLM)
- **Research workflow:** 10-60 seconds total
  - Newsroom fetch: 2-5s
  - Web search: 1-3s
  - Synthesis: 5-30s (local reasoning model)
- **Code generation:** 10-90 seconds (local: 10-30s, HF 32B: 60-90s)
- **File operations:** <100ms (local disk I/O)
- **RAM usage:** 4-6 GB (4B orchestrator model)
