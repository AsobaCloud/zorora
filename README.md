# Zorora

A local-deployment deep research engine that searches across academic databases, web sources, and newsroom articles, then synthesizes findings with credibility scoring and citation graphs. Built for macOS (Apple Silicon) with minimal RAM footprint, meant to be run directly from your computer, with all content, outputs, and chats stored locally and not in the cloud, giving you complete control and privacy.

![Zorora Terminal UI](docs/screenshot.png)

![Zorora Web UI](docs/ui.png)

## Core Value Proposition

Zorora transforms from a basic research tool into a **deep research engine** that:

1. **Searches EVERYTHING** - Academic databases (7 sources) + web search + Asoba newsroom
2. **Follows citation trails** - Multi-hop research that explores cited papers
3. **Cross-references claims** - Groups similar claims and counts agreement across sources
4. **Scores credibility** - Transparent rules-based scoring of source authority
5. **Builds citation graphs** - Visualizes relationships between sources
6. **Synthesizes with confidence** - Generates comprehensive answers with citation levels

## Quick Start

### Prerequisites

- **Python 3.8+**
- **LM Studio** running on `http://localhost:1234`
  - Download: [lmstudio.ai](https://lmstudio.ai)
  - Load a 4B model (e.g., Qwen3-VL-4B, Qwen3-4B)
- **HuggingFace token** (optional) - For remote Codestral endpoint
- **Brave Search API key** (optional) - For enhanced web search
- **Flask** (for Web UI) - Installed automatically with package

### Installation

**From GitHub:**
```bash
pip install git+https://github.com/AsobaCloud/zorora.git
```

**From source:**
```bash
git clone https://github.com/AsobaCloud/zorora.git
cd zorora
pip install -e .
```

### Run

**Terminal Interface (for engineers):**
```bash
zorora
```

**Web Interface (for non-engineers):**
```bash
python web_main.py
# Opens at http://localhost:5000
```

Or if installed via pip:
```bash
zorora web
# Opens at http://localhost:5000
```

**Web UI Features:**
- Research query interface with depth selection (Quick/Balanced/Thorough)
- Settings modal (⚙️ gear icon) for configuring:
  - LLM models for each tool (orchestrator, codestral, reasoning, search, intent_detector, vision, image_generation)
  - Endpoints (Local/LM Studio, HuggingFace, OpenAI, Anthropic)
  - API keys (masked display, secure storage)
  - Add/edit/delete custom endpoints
- Research results display with synthesis, sources, and credibility scores

## Features

### Deep Research Capabilities

- **6-Phase Research Pipeline:**
  1. **Parallel Source Aggregation** - Searches academic (7 sources), web (Brave + DDG), and newsroom simultaneously
  2. **Citation Following** - Multi-hop exploration of cited papers (configurable depth: 1-3)
  3. **Cross-Referencing** - Groups claims by similarity and counts agreement
  4. **Credibility Scoring** - Rules-based scoring of source authority (academic journals, predatory publishers, retractions)
  5. **Citation Graph Building** - Constructs directed graphs showing source relationships
  6. **Synthesis** - Generates comprehensive answers with confidence levels and citations

- **Research Depth Levels:**
  - **Quick** - Initial sources only (skips citation following)
  - **Balanced** - Adds citation following (1 hop)
  - **Thorough** - Multi-hop citation exploration (up to 3 levels deep)

- **Local-First Architecture:**
  - All processing and storage on your machine
  - SQLite database for fast indexed queries (`~/.zorora/zorora.db`)
  - JSON files for full research findings (`~/.zorora/research/findings/`)
  - Zero cloud dependencies (except source fetching)
  - Complete privacy - research data never leaves your machine

### Additional Features

- **Research persistence** - Save/load findings with metadata
- **Code generation** - Dedicated Codestral model for coding tasks
- **Multi-step development** - `/develop` workflow: explore → plan → approve → execute → lint
- **Slash commands** - Force workflows: `/search`, `/ask`, `/code`, `/develop`, `/image`, `/vision`
- **Deterministic routing** - Pattern-based decision tree (no LLM routing failures)
- **Hybrid deployment** - Local 4B orchestrator + remote 32B specialists
- **RAM-efficient** - Runs on MacBook Air M3 with 4B model
- **Dual interfaces** - Terminal REPL for engineers, Web UI for non-engineers
- **Multi-provider support** - Configure models from HuggingFace, OpenAI, and Anthropic APIs
- **Visual settings management** - Web UI settings modal for easy configuration
- **Vision and image generation** - Dedicated models for image analysis and text-to-image generation

## Basic Usage

### Deep Research Query

**Terminal (via REPL):**
```
[1] ⚙ > What are the latest developments in large language model architectures?
```

The system automatically detects research intent and executes the deep research workflow.

**Web UI:**
1. Open `http://localhost:5000` in your browser
2. Enter research question in the search box
3. Select depth level:
   - **Quick** - Initial sources only (depth=1, ~25-35s)
   - **Balanced** - + Citation following (depth=2, ~35-50s) - *Coming soon*
   - **Thorough** - + Multi-hop citations (depth=3, ~50-70s) - *Coming soon*
4. Click "Start Research"
5. View synthesis, sources, and credibility scores

**Configure Settings:**
- Click the ⚙️ gear icon to open settings modal
- Configure LLM models, endpoints, and API keys
- Add/edit/delete endpoints for HuggingFace, OpenAI, and Anthropic
- Changes take effect after server restart

**API (Programmatic Access):**
```python
from engine.research_engine import ResearchEngine

engine = ResearchEngine()
state = engine.deep_research("Your research question", depth=1)
print(state.synthesis)
```

**What Happens Automatically:**
- ✅ Aggregates sources from academic databases (7 sources), web (Brave + DDG), and newsroom (parallel)
- ✅ Scores credibility of each source (multi-factor: domain, citations, cross-references)
- ✅ Cross-references claims across sources
- ✅ Synthesizes findings with citations and confidence levels
- ✅ Saves results to local storage (`~/.zorora/zorora.db` + JSON files)

### Code Generation

```
[2] ⚙ > Write a Python function to validate email addresses
```

Routes to Codestral specialist model for code generation.

### Save/Load Research

Research is automatically saved to local storage. Access via:

**Terminal:**
```python
from engine.research_engine import ResearchEngine

engine = ResearchEngine()
# Search past research
results = engine.search_research(query="LLM architectures", limit=10)
# Load specific research
research_data = engine.load_research(results[0]['research_id'])
```

**Web UI API:**
```bash
# Get research history
curl http://localhost:5000/api/research/history?limit=10

# Get specific research
curl http://localhost:5000/api/research/<research_id>
```

**Storage Location:**
- SQLite index: `~/.zorora/zorora.db`
- Full JSON files: `~/.zorora/research/findings/<research_id>.json`

## Slash Commands

### Workflow Commands

- **`/search <query>`** - Force deep research workflow (academic + web + newsroom + synthesis)
- **`/ask <query>`** - Force conversational mode (no web search)
- **`/code <prompt>`** - Code generation or file editing (auto-detects existing files)
- **`/develop <request>`** - Multi-step code development workflow (explore → plan → execute → lint)
- **`/image <prompt>`** - Generate image with FLUX
- **`/vision <path> [task]`** - Analyze image with vision model

### System Commands

- **`/models`** - Interactive model selector
- **`/config`** - Show current routing configuration
- **`/history`** - Browse saved conversation sessions
- **`/help`** - Show available commands
- **`exit`, `quit`, `q`** - Exit the REPL

### ONA Platform Commands (Optional)

Remote commands for interacting with ONA platform ML model observation workflows. Requires ONA platform integration (configured via environment variables).

- **`ml-list-challengers <customer_id>`** - List challenger models for a customer
- **`ml-show-metrics <model_id>`** - Show evaluation metrics for a model
- **`ml-diff <challenger_id> <production_id>`** - Compare challenger vs production model
- **`ml-promote <customer_id> <model_id> <reason> [--force]`** - Promote challenger model to production (requires confirmation)
- **`ml-rollback <customer_id> <reason>`** - Rollback production model to previous version (requires confirmation)
- **`ml-audit-log <customer_id>`** - Get audit log for a customer

**Configuration:**

Set environment variables before running Zorora:

```bash
# Option 1: Retrieve from AWS SSM Parameter Store (recommended)
source <(./scripts/get-global-training-api-credentials.sh)

# Option 2: Manual configuration
export ONA_API_BASE_URL="https://p0c7u3j9wi.execute-api.af-south-1.amazonaws.com/api/v1"
export ONA_API_TOKEN="your-api-token-here"
export ONA_USE_IAM="false"
```

**Environment Variables:**
- `ONA_API_BASE_URL` - ONA platform API base URL (default: `https://p0c7u3j9wi.execute-api.af-south-1.amazonaws.com/api/v1`)
- `ONA_API_TOKEN` - Authentication token for ONA platform API (required if not using IAM)
- `ONA_USE_IAM` - Use IAM authentication (default: `false`)

For detailed operational procedures, see [docs/ZORORA_OPERATIONAL_CONTRACT.md](docs/ZORORA_OPERATIONAL_CONTRACT.md).

For detailed command reference, see [COMMANDS.md](COMMANDS.md).

## Configuration

### Web UI Settings Modal (Recommended)

The easiest way to configure Zorora is through the Web UI settings modal:

1. Start the Web UI: `python web_main.py` (or `zorora web`)
2. Click the ⚙️ gear icon in the top-right corner
3. Configure LLM models and endpoints:
   - **Model Selection**: Choose models for each tool (orchestrator, codestral, reasoning, search, intent_detector, vision, image_generation)
   - **Endpoint Selection**: Select from:
     - **Local (LM Studio)** - Models running locally
     - **HuggingFace Endpoints** - Remote HF inference endpoints
     - **OpenAI Endpoints** - OpenAI API (gpt-4, gpt-4-turbo, gpt-3.5-turbo)
     - **Anthropic Endpoints** - Anthropic API (claude-opus, claude-sonnet, claude-haiku)
   - **API Keys**: Configure API keys for:
     - HuggingFace (for HF endpoints)
     - OpenAI (for OpenAI endpoints)
     - Anthropic (for Anthropic endpoints)
   - **Add/Edit Endpoints**: Click "Add New Endpoint" to configure custom endpoints
4. Click "Save" - changes take effect after server restart

**Features:**
- ✅ Visual configuration interface (no code editing required)
- ✅ Dropdown selection for models and endpoints
- ✅ Secure API key management (masked display, show/hide toggle)
- ✅ Add/edit/delete endpoints for all providers
- ✅ Automatic role reassignment when endpoints are deleted
- ✅ Config file backup before each write

### Terminal Configuration

Use the interactive `/models` command:

```
[1] ⚙ > /models
```

### Manual Configuration

1. Copy `config.example.py` to `config.py`
2. Edit `config.py` with your settings:
   - LM Studio model name
   - HuggingFace token (optional, for HF endpoints)
   - OpenAI API key (optional, for OpenAI endpoints)
   - Anthropic API key (optional, for Anthropic endpoints)
   - Brave Search API key (optional)
   - Specialist model configurations
   - Endpoint mappings (`MODEL_ENDPOINTS`, `HF_ENDPOINTS`, `OPENAI_ENDPOINTS`, `ANTHROPIC_ENDPOINTS`)

### Web Search Setup

**Brave Search API** (recommended):
- Get free API key at: https://brave.com/search/api/
- Free tier: 2000 queries/month (~66/day)
- Configure in `config.py`:
  ```python
  BRAVE_SEARCH = {
      "api_key": "YOUR_API_KEY",
      "enabled": True,
  }
  ```

**DuckDuckGo Fallback:**
- Automatically used if Brave Search unavailable
- No API key required

## Architecture

Zorora uses **deterministic routing** with pattern matching (no LLM-based orchestration):

```
User Query / Slash Command / Web UI Request
    ↓
Pattern Matching (simplified_router.py) / Flask Routes (ui/web/app.py)
    ↓
    ├─→ DEEP RESEARCH WORKFLOW (4-phase MVP pipeline)
    │   ├─► Phase 1: Parallel Source Aggregation
    │   │   ├─► Academic (7 sources: Scholar, PubMed, CORE, arXiv, bioRxiv, medRxiv, PMC)
    │   │   ├─► Web (Brave Search + DuckDuckGo)
    │   │   └─► Newsroom (Asoba API)
    │   ├─► Phase 2: Credibility Scoring (multi-factor)
    │   │   ├─► Domain-based scoring (Nature=0.85, arXiv=0.50, etc.)
    │   │   ├─► Citation modifiers
    │   │   └─► Cross-reference agreement
    │   ├─► Phase 3: Cross-Referencing (simplified)
    │   │   └─► Group claims by similarity
    │   └─► Phase 4: Synthesis (Reasoning Model)
    │       └─► Generate comprehensive answer with citations
    ├─→ CODE WORKFLOW (Codestral specialist)
    ├─→ DEVELOPMENT WORKFLOW (/develop - multi-step)
    ├─→ FILE OPERATIONS (save/load/list)
    └─→ SIMPLE Q&A (/ask - direct model)
```

**Storage Architecture:**
```
Research Request
    ↓
ResearchEngine.deep_research()
    ↓
DeepResearchWorkflow.execute()
    ↓
LocalStorage.save_research()
    ├─► SQLite Index (~/.zorora/zorora.db)
    │   ├─► research_findings (metadata)
    │   ├─► sources (indexed)
    │   └─► citations (graph)
    └─► JSON Files (~/.zorora/research/findings/<id>.json)
        └─► Full research state (sources, findings, synthesis)
```

**Key Principles:**
- **Local-first** - Everything runs on your machine (SQLite + JSON files)
- **Deterministic workflows** - Code-controlled pipelines, not LLM orchestration
- **Pattern matching** - Ensures consistent routing (0ms decision time)
- **Specialist models** - Dedicated models for specific tasks
- **Dual interfaces** - Terminal REPL for engineers, Web UI for non-engineers
- **Modular tools** - Research tools in `tools/research/`, registry in `tools/registry.py`

For detailed architecture documentation, see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Module Structure

```
zorora/
├── main.py                      # Entry point
├── repl.py                      # REPL loop and slash commands
├── web_main.py                  # Web UI entry point
├── config.py                    # Configuration
├── simplified_router.py         # Deterministic routing
├── research_workflow.py         # Legacy research pipeline
├── turn_processor.py            # Workflow orchestration
├── tool_executor.py             # Tool execution
├── tool_registry.py             # Backward-compat shim (deprecated)
├── tool_registry_legacy.py      # Original tool registry (backup)
│
├── engine/                      # Deep research engine
│   ├── models.py                # Data models (Source, Finding, ResearchState)
│   ├── storage.py               # SQLite storage layer
│   └── research_engine.py       # High-level research API
│
├── tools/                       # Modular tool registry (v2.2.0+)
│   ├── registry.py              # Central registry - import from here
│   │
│   ├── research/                # Research tools
│   │   ├── academic_search.py   # Academic search (7 sources)
│   │   ├── web_search.py        # Web search (Brave + DDG)
│   │   └── newsroom.py          # Newsroom API integration
│   │
│   ├── file_ops/                # File operations
│   │   ├── utils.py             # Path resolution & validation
│   │   ├── read.py              # read_file (with line numbers)
│   │   ├── write.py             # write_file
│   │   ├── edit.py              # edit_file (with replace_all)
│   │   └── directory.py         # make_directory, list_files, get_working_directory
│   │
│   ├── shell/                   # Shell operations
│   │   ├── run.py               # run_shell (whitelist-secured)
│   │   └── patch.py             # apply_patch (unified diff)
│   │
│   ├── specialist/              # Specialist LLM tools
│   │   ├── client.py            # Specialist client factory
│   │   ├── coding.py            # use_coding_agent (model-agnostic)
│   │   ├── reasoning.py         # use_reasoning_model
│   │   ├── search.py            # use_search_model
│   │   ├── intent.py            # use_intent_detector
│   │   └── energy.py            # use_nehanda (Nehanda RAG)
│   │
│   └── image/                   # Image tools
│       ├── analyze.py           # analyze_image (vision model)
│       ├── generate.py          # generate_image (Flux Schnell)
│       └── search.py            # web_image_search (Brave)
│
├── workflows/                   # Multi-step workflows
│   ├── develop_workflow.py      # Development workflow
│   ├── codebase_explorer.py     # Codebase exploration
│   ├── code_planner.py          # Code planning
│   ├── code_executor.py         # Code execution (with retry loop)
│   ├── code_tools.py            # File operations & linting
│   └── deep_research/           # Deep research workflow
│       ├── aggregator.py        # Source aggregation
│       ├── credibility.py       # Credibility scoring
│       ├── synthesizer.py       # Synthesis generation
│       └── workflow.py          # Workflow orchestrator
│
└── ui/web/                      # Web UI (Flask app)
    ├── app.py                   # Flask application + API routes
    ├── config_manager.py        # Config file management (read/write)
    ├── templates/
    │   └── index.html           # Research UI + Settings Modal
    └── static/
        └── images/
            ├── Artboard-7.png   # Asoba logo
            └── ui.png           # UI screenshot
```

## Documentation

- **[COMMANDS.md](COMMANDS.md)** - Complete command reference
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** - Detailed architecture explanation
- **[docs/WORKFLOWS.md](docs/WORKFLOWS.md)** - Workflow documentation
- **[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)** - Development guide
- **[docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)** - Troubleshooting guide
- **[docs/BEST_PRACTICES.md](docs/BEST_PRACTICES.md)** - Best practices

## Performance

- **Routing decision:** 0ms (pattern matching)
- **Research workflow:** Varies by depth (MVP - depth=1 only)
  - **Quick (depth=1):** ~25-35s
    - Source aggregation: ~8s (parallel)
    - Credibility scoring: ~2s
    - Synthesis: ~15-25s
  - **Balanced (depth=2):** ~35-50s - *Coming soon (citation following)*
  - **Thorough (depth=3):** ~50-70s - *Coming soon (multi-hop citations)*
- **Storage queries:** <100ms (SQLite indexed)
- **Code generation:** 10-90 seconds (local: 10-30s, HF 32B: 60-90s)
- **RAM usage:** 4-6 GB (4B orchestrator model)

## Why This Architecture?

**Problem:** 4B models struggle with LLM-based orchestration (JSON generation, tool chaining, loop detection).

**Solution:** Code handles complexity:
- Pattern matching routes queries (no LLM decision)
- Hardcoded 6-phase research pipeline (no LLM planning)
- Deterministic error handling (no LLM recovery)
- Local-first storage (SQLite + JSON files)

**Result:** 100% reliability with 4B models, 1/3 the RAM usage of 8B orchestrators, complete privacy with local storage.

For more details, see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [docs/DEEP_RESEARCH_IMPLEMENTATION.md](docs/DEEP_RESEARCH_IMPLEMENTATION.md).

## Troubleshooting

### LM Studio Not Connected
**Solution:** Start LM Studio and load a model on port 1234

### Research Workflow Not Triggered
**Solution:** Include research keywords: "What", "Why", "How", "Tell me", or use `/search` command

### Can't Save Research
**Solution:** Check `~/.zorora/research/` directory exists and is writable

### Endpoint Errors (HF/OpenAI/Anthropic)
**Solution:** 
- Check endpoint URL (for HF endpoints)
- Verify API keys are configured (use Web UI settings modal)
- Ensure endpoints are enabled in config
- Check API rate limits (OpenAI/Anthropic)
- Verify model names match provider requirements

### Web UI Not Starting
**Solution:** 
- Ensure Flask is installed: `pip install flask`
- Run: `python web_main.py` (or `zorora web` if installed via pip)
- Check port 5000 is available

### Deep Research Not Working
**Solution:**
- Check that research tools are accessible: `from tools.research.academic_search import academic_search`
- Verify storage directory exists: `~/.zorora/` (created automatically)
- Check logs for API errors (Brave Search, Newsroom API)

For detailed troubleshooting, see [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).

## License

See LICENSE file.

---

**Repository:** https://github.com/AsobaCloud/zorora
**Nehanda:** https://huggingface.co/asoba/nehanda-v1-7b
**Version:** 2.5.0 (ONA Platform Integration & Enhanced Editing)

---

## Changelog

### Version 2.5.0 - ONA Platform Integration & Enhanced Editing

**Major Features:**
- ONA Platform Integration - Remote ML model observation commands (`/ml-*`)
- Beautiful progress display with hierarchical tool visualization
- Boxed input UI using prompt_toolkit
- Complete modular tool registry migration (19 tools)

**Enhanced /code:**
- Auto-detects existing files and uses `edit_file` workflow
- Direct model call for edits (bypasses planning phase)
- Retry loop with error context (up to 3 attempts)

**Improvements:**
- SQLite threading fixes
- `/deep` command for terminal deep research
- Model-agnostic coding (`use_codestral` → `use_coding_agent`)

**Documentation:**
- Moved 21 internal docs to `docs/deprecated/`
- Streamlined to 6 essential public docs

See [docs/RELEASE_NOTES_v2.5.0.md](docs/RELEASE_NOTES_v2.5.0.md) for full details.

### Version 2.3.0 - Enhanced /code File Editing

**Major Features:**
- `/code` now auto-detects existing files and uses `edit_file` workflow
- File detection via pattern matching (e.g., "update script.py from X to Y")
- Direct model call for edits (bypasses planning phase for simple edits)
- OLD_CODE/NEW_CODE parsing with retry loop (up to 3 attempts)

**Workflow Comparison:**
| Command | Scope | Phases | Best For |
|---------|-------|--------|----------|
| `/code` | Single file/snippet | 1-2 (plan + generate/edit) | Quick edits, snippets |
| `/develop` | Entire codebase | 5 (preflight → explore → plan → execute → lint) | Features, refactoring |

**ONA Platform Commands:**
- Fixed routing for `ml-` commands (works with or without leading `/`)
- Added internal docs pattern to `.gitignore`

**Documentation Cleanup:**
- Moved implementation plans to `docs/deprecated/`
- Streamlined public documentation

### Version 2.2.0 - Modular Tool Registry & Offline Coding Improvements

**Major Features:**
- Complete modular tool registry migration (`tools/` directory)
- Renamed `use_codestral` → `use_coding_agent` (model-agnostic)
- Added `/deep` command for deep research in terminal
- Improved file editing reliability with read-before-edit enforcement
- Added retry loop to CodeExecutor for self-correcting edits
- Full file context in edit prompts with smart truncation

**Tool Registry Migration (19 tools migrated):**
- `tools/research/` - academic_search, web_search, get_newsroom_headlines
- `tools/file_ops/` - read_file, write_file, edit_file, make_directory, list_files, get_working_directory
- `tools/shell/` - run_shell, apply_patch
- `tools/specialist/` - use_coding_agent, use_reasoning_model, use_search_model, use_intent_detector, use_nehanda
- `tools/image/` - analyze_image, generate_image, web_image_search

**File Editing Improvements:**
- Line numbers now included by default in read_file output
- `replace_all` parameter for edit_file to replace all occurrences
- Better error messages showing similar text and line numbers
- Read-before-edit enforcement in tool_executor

**Code Executor Improvements:**
- Retry loop (up to 3 attempts) with error context
- Smart file truncation for large files (keyword-based region extraction)
- Line numbers in edit prompts for precise matching

**Breaking Changes:**
- `use_codestral` renamed to `use_coding_agent` (alias provided for backward compatibility)
- Import from `tools.registry` instead of `tool_registry` (deprecation warning added)

### Version 2.1.0 - Settings Modal & Multi-Provider Support

**Major Features:**
- ✅ Web UI Settings Modal - Visual configuration interface
- ✅ Multi-provider endpoint support (HuggingFace, OpenAI, Anthropic)
- ✅ API key management for all providers (masked display, secure storage)
- ✅ Endpoint CRUD operations via Web UI (add/edit/delete)
- ✅ Vision and image_generation model configuration
- ✅ Config file backup before writes
- ✅ Automatic role reassignment on endpoint deletion

**Configuration Improvements:**
- Visual settings modal (no code editing required)
- Dropdown selection for models and endpoints
- Provider-specific endpoint forms (HF: URL+Model, OpenAI/Anthropic: Model+MaxTokens)
- Secure API key handling (masking, show/hide toggle)
- Config validation and error handling

**API Enhancements:**
- `/api/settings/config` - Read/write configuration
- `/api/settings/models` - List available models (all providers)
- `/api/settings/endpoints` - List endpoints (all providers)
- `/api/settings/endpoint` - Add/edit endpoint (provider-aware)
- `/api/settings/endpoint/<key>` - Delete endpoint (checks all providers)

### Version 2.0.0 - Deep Research Release

**Major Features:**
- ✅ Deep research engine with 4-phase workflow (MVP)
- ✅ Modular tool registry (`tools/research/`, `tools/registry.py`)
- ✅ SQLite + JSON storage layer (`engine/storage.py`)
- ✅ Web UI with Flask (`ui/web/app.py`)
- ✅ Credibility scoring system
- ✅ Parallel source aggregation (academic + web + newsroom)
- ✅ Research synthesis with citations

**Architecture Changes:**
- Refactored tool registry into modular structure
- Created `engine/` module for research engine
- Created `workflows/deep_research/` for workflow components
- Added Flask-based Web UI

**Breaking Changes:**
- `tool_registry.py` is now a backward-compatibility shim
- Use `from tools.registry import ...` for new code
- Web UI requires Flask (added to requirements)
