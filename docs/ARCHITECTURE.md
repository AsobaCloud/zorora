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
    ├─→ CODE WORKFLOW (/code - generation or editing)
    │   ├─→ File detected? → Edit workflow (read → OLD/NEW → edit_file)
    │   └─→ No file? → Generation workflow (plan → generate)
    │
    ├─→ FILE OPERATIONS (save/load/list)
    │   └─→ Research or filesystem operations
    │
    ├─→ IMAGE WORKFLOWS (generate/analyze)
    │   ├─→ FLUX for image generation
    │   └─→ Vision model for analysis
    │
    ├─→ CONFIGURATION (Web UI Settings Modal)
    │   ├─→ Model selection (orchestrator, codestral, reasoning, search, intent_detector, vision, image_generation)
    │   ├─→ Endpoint management (HF, OpenAI, Anthropic)
    │   └─→ API key management (masked display, secure storage)
    │
    └─→ SIMPLE Q&A (/ask - no search)
        └─→ Direct model response
```

## Key Principles

- **No LLM-based orchestration** - Patterns determine routing, code controls execution
- **Hardcoded workflows** - Fixed pipelines for predictable results (newsroom → web → synthesis)
- **Persistent research** - Everything saved to `~/.zorora/research/` with metadata
- **Specialist models** - Codestral for code, reasoning model for synthesis, vision for images
- **Multi-provider support** - Configure models from LM Studio (local), HuggingFace, OpenAI, and Anthropic APIs
- **Visual configuration** - Web UI settings modal for easy model/endpoint management
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
        return {"workflow": "code", "tool": "use_coding_agent"}

    # Priority 3: Research (default for non-file/non-code input)
    if re.search(r'\b(what|why|how|tell me|based on|newsroom|web search)\b', user_input.lower()):
        return {"workflow": "research", "action": "multi_source_research"}

    # Fallback: still route to research for current-information safety
    # (plain conversational QA is explicitly available via /ask)
    return {"workflow": "research", "action": "multi_source_research"}
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

### 4. Tool Registry (`tools/registry.py`)

Modular tool registry with 19+ tools organized by category:

```
tools/
├── registry.py              # Central registry - import from here
├── research/                # Research tools
│   ├── academic_search.py   # academic_search (7 sources)
│   ├── web_search.py        # web_search (Brave + DDG)
│   └── newsroom.py          # get_newsroom_headlines
├── file_ops/                # File operations
│   ├── read.py              # read_file (with line numbers)
│   ├── write.py             # write_file
│   ├── edit.py              # edit_file (with replace_all)
│   └── directory.py         # make_directory, list_files, get_working_directory
├── shell/                   # Shell operations
│   ├── run.py               # run_shell (whitelist-secured)
│   └── patch.py             # apply_patch
├── specialist/              # Specialist LLM tools
│   ├── coding.py            # use_coding_agent (model-agnostic)
│   ├── reasoning.py         # use_reasoning_model
│   ├── search.py            # use_search_model
│   ├── intent.py            # use_intent_detector
│   └── energy.py            # use_nehanda (Nehanda RAG)
└── image/                   # Image tools
    ├── analyze.py           # analyze_image (vision model)
    ├── generate.py          # generate_image (Flux Schnell)
    └── search.py            # web_image_search (Brave)
```

**Usage:** Import from `tools.registry`:
```python
from tools.registry import read_file, edit_file, use_coding_agent
```

### 5. Workflows (`workflows/`)

Multi-step development workflow:
- `develop_workflow.py` - Main orchestrator
- `codebase_explorer.py` - Phase 1: Code exploration
- `code_planner.py` - Phase 2: Planning with approval
- `code_executor.py` - Phase 4: Code execution
- `code_tools.py` - File operations and linting

### 6. Shared Deep Research Service (`engine/deep_research_service.py`)

Shared execution path for deep-research pipeline (aggregation → credibility → cross-reference → synthesis),
used by both:
- Web UI async research endpoint (`ui/web/app.py`)
- REPL `/deep` command path (`engine/repl_command_processor.py`)

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

### Code Workflow (`/code`)

```
/code <prompt>
  ↓
Detect file in input (pattern matching)
  ↓
  ├─→ [File detected] → Edit Workflow
  │   ├─→ Read file with line numbers
  │   ├─→ Build edit prompt (OLD_CODE/NEW_CODE format)
  │   ├─→ Call coding model directly (no planning phase)
  │   ├─→ Parse OLD_CODE/NEW_CODE from response
  │   └─→ Apply edit_file (with retry loop, up to 3 attempts)
  │
  └─→ [No file] → Generation Workflow
      ├─→ Planning phase (with approval)
      └─→ Generate code with Codestral
```

**File Detection Patterns:**
- `"update script.py from X to Y"` → detects `script.py`
- `"edit config.json"` → detects `config.json`
- `"change in utils.py"` → detects `utils.py`

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
├── llm_client.py               # LM Studio/HF/OpenAI/Anthropic API client
├── ui.py                       # Rich terminal UI
│
├── simplified_router.py        # Deterministic decision tree
├── research_workflow.py        # Legacy research pipeline
├── research_persistence.py     # Save/load research findings
│
├── turn_processor.py           # Main workflow orchestration
├── tool_executor.py            # Tool execution engine (with read-before-edit)
├── model_selector.py           # Interactive model configuration (terminal)
│
├── tools/                      # Modular tool registry (v2.2.0+)
│   ├── registry.py             # Central registry - import from here
│   ├── research/               # Research tools (3 tools)
│   ├── file_ops/               # File operations (6 tools)
│   ├── shell/                  # Shell operations (2 tools)
│   ├── specialist/             # Specialist LLM tools (5 tools)
│   └── image/                  # Image tools (3 tools)
│
├── workflows/                  # Multi-step development workflows
│   ├── __init__.py
│   ├── develop_workflow.py     # /develop orchestrator
│   ├── codebase_explorer.py    # Phase 1: Code exploration
│   ├── code_planner.py         # Phase 2: Planning with approval
│   ├── code_executor.py        # Phase 3: Code execution (with retry loop)
│   └── code_tools.py           # File operations and linting
│
└── ui/web/                     # Web UI (Flask application)
    ├── app.py                  # Flask routes + API endpoints
    ├── config_manager.py       # Config file read/write management
    └── templates/
        └── index.html          # Research UI + Settings Modal
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
