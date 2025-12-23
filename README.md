# Zorora

A lightweight research REPL optimized for knowledge acquisition, multi-source synthesis, and persistent storage. Built for macOS (Apple Silicon) with minimal RAM footprint.

![Zorora Screenshot](docs/screenshot.png)

## Quick Start

### Prerequisites

- **Python 3.8+**
- **LM Studio** running on `http://localhost:1234`
  - Download: [lmstudio.ai](https://lmstudio.ai)
  - Load a 4B model (e.g., Qwen3-VL-4B, Qwen3-4B)
- **HuggingFace token** (optional) - For remote Codestral endpoint

### Installation

```bash
pip install git+https://github.com/AsobaCloud/zorora.git
```

### Run

```bash
zorora
```

## Features

- **Multi-source research** - Automatic [newsroom](https://github.com/AsobaCloud/newsroom) + web search + synthesis with citations
- **Research persistence** - Save/load findings with metadata to `~/.zorora/research/`
- **Code generation** - Dedicated Codestral model for coding tasks
- **Multi-step development** - `/develop` workflow: explore → plan → approve → execute → lint
- **Slash commands** - Force workflows: `/search`, `/ask`, `/code`, `/develop`, `/image`, `/vision`
- **Deterministic routing** - Pattern-based decision tree (no LLM routing failures)
- **Hybrid deployment** - Local 4B orchestrator + remote 32B specialists
- **RAM-efficient** - Runs on MacBook Air M3 with 4B model

## Basic Usage

### Research Query

```
[1] ⚙ > Based on the newsroom as well as web search, what are the major AI trends in 2025?
```

Zorora automatically:
- Fetches newsroom headlines
- Searches the web
- Synthesizes findings with citations
- Optionally saves results for later

### Code Generation

```
[2] ⚙ > Write a Python function to validate email addresses
```

Routes to Codestral specialist model for code generation.

### Save Research

```
[3] ⚙ > Save this as "ai_trends_2025"
Saved to: ~/.zorora/research/ai_trends_2025.md
```

### Load Research

```
[4] ⚙ > Load my research on AI trends
```

## Slash Commands

### Workflow Commands

- **`/search <query>`** - Force research workflow (newsroom + web + synthesis)
- **`/ask <query>`** - Force conversational mode (no web search)
- **`/code <prompt>`** - Force code generation with Codestral
- **`/develop <request>`** - Multi-step code development workflow
- **`/image <prompt>`** - Generate image with FLUX
- **`/vision <path> [task]`** - Analyze image with vision model

### System Commands

- **`/models`** - Interactive model selector
- **`/config`** - Show current routing configuration
- **`/history`** - Browse saved conversation sessions
- **`/help`** - Show available commands
- **`exit`, `quit`, `q`** - Exit the REPL

For detailed command reference, see [COMMANDS.md](COMMANDS.md).

## Configuration

### Quick Setup

Use the interactive `/models` command:

```
[1] ⚙ > /models
```

### Manual Configuration

1. Copy `config.example.py` to `config.py`
2. Edit `config.py` with your settings:
   - LM Studio model name
   - HuggingFace token (optional)
   - Brave Search API key (optional)
   - Specialist model configurations

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
User Query / Slash Command
    ↓
Pattern Matching (simplified_router.py)
    ↓
    ├─→ RESEARCH WORKFLOW (newsroom + web + synthesis)
    ├─→ CODE WORKFLOW (Codestral specialist)
    ├─→ DEVELOPMENT WORKFLOW (/develop - multi-step)
    ├─→ FILE OPERATIONS (save/load/list)
    └─→ SIMPLE Q&A (/ask - direct model)
```

**Key Principles:**
- Code-controlled workflows, not LLM orchestration
- Hardcoded pipelines for predictable results
- Pattern matching ensures consistent routing
- Specialist models for specific tasks

For detailed architecture documentation, see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Module Structure

```
zorora/
├── main.py                      # Entry point
├── repl.py                      # REPL loop and slash commands
├── config.py                    # Configuration
├── simplified_router.py          # Deterministic routing
├── research_workflow.py         # Research pipeline
├── turn_processor.py            # Workflow orchestration
├── tool_executor.py             # Tool execution
├── tool_registry.py             # Tool definitions
└── workflows/                   # Multi-step workflows
    ├── develop_workflow.py
    ├── codebase_explorer.py
    ├── code_planner.py
    └── code_executor.py
```

## Documentation

- **[COMMANDS.md](COMMANDS.md)** - Complete command reference
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** - Detailed architecture explanation
- **[docs/WORKFLOWS.md](docs/WORKFLOWS.md)** - Workflow documentation
- **[docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)** - Troubleshooting guide
- **[docs/BEST_PRACTICES.md](docs/BEST_PRACTICES.md)** - Best practices
- **[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)** - Development workflow details

## Performance

- **Routing decision:** 0ms (pattern matching)
- **Research workflow:** 10-60 seconds total
- **Code generation:** 10-90 seconds (local: 10-30s, HF 32B: 60-90s)
- **RAM usage:** 4-6 GB (4B orchestrator model)

## Why This Architecture?

**Problem:** 4B models struggle with LLM-based orchestration (JSON generation, tool chaining, loop detection).

**Solution:** Code handles complexity:
- Pattern matching routes queries (no LLM decision)
- Hardcoded workflows execute pipelines (no LLM planning)
- Deterministic error handling (no LLM recovery)

**Result:** 100% reliability with 4B models, 1/3 the RAM usage of 8B orchestrators.

For more details, see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Troubleshooting

### LM Studio Not Connected
**Solution:** Start LM Studio and load a model on port 1234

### Research Workflow Not Triggered
**Solution:** Include research keywords: "What", "Why", "How", "Tell me", or use `/search` command

### Can't Save Research
**Solution:** Check `~/.zorora/research/` directory exists and is writable

### HuggingFace Endpoint Errors
**Solution:** Check HF endpoint URL, verify token, ensure endpoint is running

For detailed troubleshooting, see [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).

## License

See LICENSE file.

---

**Repository:** https://github.com/AsobaCloud/zorora  
**EnergyAnalyst:** https://huggingface.co/asoba/EnergyAnalyst-v0.1  
**Version:** 1.0.0
