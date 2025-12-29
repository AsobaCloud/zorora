# Zorora v2.0.0 Release Notes

**Release Date:** December 2024  
**Previous Release:** v1.1-prod

---

## 🎉 Major Features

### Deep Research Engine
- **6-Phase Research Pipeline** - Comprehensive multi-source research with citation following, cross-referencing, credibility scoring, and synthesis
- **Parallel Source Aggregation** - Searches academic databases (7 sources), web (Brave + DuckDuckGo), and Asoba newsroom simultaneously
- **Credibility Scoring** - Multi-factor scoring system evaluating domain authority, citations, cross-references, and retraction status
- **Citation Graph Building** - Constructs directed graphs showing relationships between sources
- **Local-First Storage** - SQLite database for indexed queries (`~/.zorora/zorora.db`) + JSON files for full research data
- **Research Depth Levels** - Quick (depth=1), Balanced (depth=2), Thorough (depth=3) with configurable citation following

### Web UI
- **Research Interface** - Clean, modern web UI for non-engineers (`http://localhost:5000`)
- **Settings Modal** - Visual configuration interface for LLM models and endpoints
- **Multi-Provider Support** - Configure models from HuggingFace, OpenAI, and Anthropic APIs
- **Endpoint Management** - Add/edit/delete endpoints for all providers via UI
- **API Key Management** - Secure API key storage with masked display and show/hide toggle

### Settings Modal Features
- **Model Configuration** - Configure LLM models for each tool (orchestrator, codestral, reasoning, search, intent_detector, vision, image_generation)
- **Endpoint Selection** - Choose from Local (LM Studio), HuggingFace, OpenAI, or Anthropic endpoints
- **Per-Endpoint API Keys** - Set API keys per endpoint (overrides global keys)
- **Global API Keys** - Configure HF_TOKEN, OPENAI_API_KEY, ANTHROPIC_API_KEY
- **Config File Backup** - Automatic backup before each config write
- **Automatic Role Reassignment** - Deleted endpoints automatically reassign roles to "local"

---

## 🚀 New Capabilities

### Research Tools
- **Academic Search** - 7 sources: Google Scholar, PubMed, CORE API, arXiv, bioRxiv, medRxiv, PMC
- **Web Search** - Brave Search API + DuckDuckGo fallback with parallel search
- **Newsroom Integration** - Asoba Newsroom API for current news articles
- **Citation Following** - Multi-hop exploration of cited papers (configurable depth)

### Multi-Provider API Support
- **HuggingFace Endpoints** - Support for HF Inference Endpoints with per-endpoint API keys
- **OpenAI API** - Full support for OpenAI models (gpt-4, gpt-4-turbo, gpt-3.5-turbo)
- **Anthropic API** - Full support for Anthropic models (claude-opus, claude-sonnet, claude-haiku)
- **Local Models** - LM Studio integration for local inference

### Vision & Image Generation
- **Vision Model** - Image analysis and OCR capabilities
- **Image Generation** - Text-to-image generation with FLUX Schnell

---

## 📦 Architecture Changes

### Module Structure
- **`engine/`** - Deep research engine (`models.py`, `storage.py`, `research_engine.py`)
- **`workflows/deep_research/`** - Research workflow components (`aggregator.py`, `credibility.py`, `synthesizer.py`, `workflow.py`)
- **`tools/research/`** - Modular research tools (`academic_search.py`, `web_search.py`, `newsroom.py`)
- **`tools/registry.py`** - Central tool registry
- **`ui/web/`** - Flask web application (`app.py`, `config_manager.py`, `templates/`, `static/`)

### Tool Registry Refactor
- Modular tool organization by category (research, code, specialist)
- Backward-compatible shim for `tool_registry.py`
- Centralized tool definitions and function registry

### Storage Layer
- SQLite database for fast indexed queries
- JSON files for full research state persistence
- Automatic schema initialization

---

## 🔧 Improvements

### Configuration Management
- **Visual Settings UI** - No manual `config.py` editing required
- **Config Validation** - Input validation before write
- **Atomic Writes** - Safe config file updates with backup
- **Multi-Provider Config** - Support for HF, OpenAI, Anthropic endpoints

### Error Handling
- Masked token rejection (prevents saving masked API keys)
- Config validation with clear error messages
- Automatic fallback to "local" when endpoints deleted

### Documentation
- Comprehensive implementation guides (`DEEP_RESEARCH_IMPLEMENTATION.md`, `SETTINGS_MODAL_IMPLEMENTATION.md`)
- Updated architecture documentation
- Code review and planned fixes (`UI_CODE_REVIEW.md`)

---

## 🐛 Bug Fixes

- Fixed duplicate API key field IDs in endpoint modal
- Fixed endpoint modal API key field handling for different providers
- Fixed config file reading to handle missing attributes gracefully
- Fixed endpoint validation to check all provider types (HF, OpenAI, Anthropic)

---

## 📝 API Changes

### New Endpoints
- `GET /api/research` - Start research workflow
- `GET /api/research/<research_id>` - Get research results
- `GET /api/research/history` - Get research history
- `GET /api/settings/config` - Get current configuration
- `GET /api/settings/models` - List available models
- `GET /api/settings/endpoints` - List saved endpoints
- `POST /api/settings/config` - Save configuration
- `POST /api/settings/endpoint` - Add/edit endpoint
- `DELETE /api/settings/endpoint/<key>` - Delete endpoint

---

## 🔄 Migration Notes

### Breaking Changes
- `tool_registry.py` is now a backward-compatibility shim
- Use `from tools.registry import ...` for new code
- Web UI requires Flask (added to requirements)

### Config File Changes
- New fields: `OPENAI_ENDPOINTS`, `ANTHROPIC_ENDPOINTS`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`
- `MODEL` is now legacy-only (use `SPECIALIZED_MODELS` instead)
- Endpoint configs can now include `api_key` field for per-endpoint keys

---

## 📊 Statistics

- **Total Commits:** 30+ since v1.1-prod
- **New Modules:** 4 major modules (engine, workflows/deep_research, tools/research, ui/web)
- **New API Endpoints:** 9 endpoints
- **New Tools:** 3 research tools (academic_search, web_search, newsroom)
- **Documentation:** 3 new implementation guides

---

## 🎯 What's Next

See `docs/UI_CODE_REVIEW.md` for planned improvements:
- Real-time form validation
- Inline error messages (replace alert())
- Endpoint management section
- Loading states for all operations
- Data loss prevention warnings

---

## 🙏 Credits

Built with:
- Flask for web UI
- SQLite for local storage
- Brave Search API for enhanced web search
- Asoba Newsroom API for current news

---

**Full Changelog:** See git log `v1.1-prod..HEAD`
