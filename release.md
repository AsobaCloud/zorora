# Zorora v1.0.0 - Initial Release

## Overview

Zorora is a lightweight research REPL optimized for knowledge acquisition, multi-source synthesis, and persistent storage. Built for macOS (Apple Silicon) with minimal RAM footprint, it combines local and remote models to deliver reliable research and code generation workflows.

## 🎯 Key Features

### Research Capabilities
- **Multi-source research** - Automatic newsroom + web search + synthesis with citations
- **Research persistence** - Save/load findings with metadata to `~/.zorora/research/`
- **Web search integration** - Brave Search API with DuckDuckGo fallback
- **Citation management** - Synthesized results include source tags ([Newsroom], [Web])

### Code Generation
- **Code generation** - Dedicated Codestral model for coding tasks
- **Multi-step development** - `/develop` workflow: explore → plan → approve → execute → lint
- **Specialist models** - Optimized models for specific tasks

### Workflow System
- **Deterministic routing** - Pattern-based decision tree (no LLM routing failures)
- **Slash commands** - Force specific workflows (`/search`, `/ask`, `/code`, `/develop`, `/image`, `/vision`)
- **Hardcoded pipelines** - Predictable, reliable execution

### Performance & Efficiency
- **RAM-efficient** - Runs on MacBook Air M3 with 4B orchestrator model (4-6 GB RAM)
- **Hybrid deployment** - Local 4B orchestrator + remote 32B specialists
- **Fast routing** - 0ms routing decisions via pattern matching
- **Optimized workflows** - Research completes in 10-60 seconds

## 📦 Installation

```bash
pip install git+https://github.com/AsobaCloud/zorora.git
```

### Prerequisites
- Python 3.8+
- LM Studio running on `http://localhost:1234` with a 4B model loaded
- HuggingFace token (optional, for remote Codestral endpoint)
- Brave Search API key (optional, for enhanced web search)

## 🚀 Quick Start

1. **Start LM Studio** and load a 4B model (Qwen3-VL-4B recommended)

2. **Run Zorora:**
   ```bash
   zorora
   ```

3. **Start researching:**
   ```
   [1] ⚙ > Based on the newsroom as well as web search, what are the major AI trends in 2025?
   ```

## 🏗️ Architecture Highlights

Zorora uses **deterministic routing** with pattern matching instead of LLM-based orchestration. This design enables:

- ✅ **100% routing reliability** (pattern matching never fails)
- ✅ **Predictable behavior** (same query = same workflow)
- ✅ **RAM efficiency** (4B model = 4-6 GB vs 8B = 12-16 GB)
- ✅ **Fast responses** (no LLM routing overhead)

### Core Workflows

- **Research Workflow** - Newsroom → web search → synthesis with citations
- **Code Workflow** - Codestral specialist model for code generation
- **Development Workflow** - Multi-step code development with approval gates
- **File Operations** - Save/load/list research findings
- **Simple Q&A** - Direct model responses without tool use

## ⚡ Performance Metrics

- **Routing decision:** 0ms (pattern matching)
- **Research workflow:** 10-60 seconds total
- **Code generation:** 10-90 seconds (local: 10-30s, HF 32B: 60-90s)
- **RAM usage:** 4-6 GB (4B orchestrator model)

## 📚 Documentation

Comprehensive documentation is available:

- **[README.md](README.md)** - Quick start and overview
- **[COMMANDS.md](COMMANDS.md)** - Complete command reference
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** - Detailed architecture explanation
- **[docs/WORKFLOWS.md](docs/WORKFLOWS.md)** - Workflow documentation
- **[docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)** - Troubleshooting guide
- **[docs/BEST_PRACTICES.md](docs/BEST_PRACTICES.md)** - Best practices
- **[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)** - Development workflow details

## 📋 What's Included

### Core Modules
- REPL interface with rich terminal UI
- Deterministic routing system
- Research workflow engine
- Code generation pipeline
- Multi-step development workflow
- Tool execution engine
- Model selector and configuration

### Tools & Integrations
- Web search (Brave Search API + DuckDuckGo fallback)
- Research persistence (local file storage)
- Code generation (Codestral specialist)
- Image generation (FLUX Schnell)
- Image analysis (vision models)
- Energy policy analysis (optional EnergyAnalyst integration)

## 💻 System Requirements

- macOS (Apple Silicon recommended)
- Python 3.8+
- 4-6 GB RAM (with 4B orchestrator model)
- LM Studio for local model inference
- Internet connection (for web search and optional remote endpoints)

## 🤝 Contributing

This is an open-source project. Contributions, bug reports, and feature requests are welcome. Please see the repository for contribution guidelines.

## 📄 License

See LICENSE file for details.

## 🔗 Links

- **Repository:** https://github.com/AsobaCloud/zorora
- **EnergyAnalyst:** https://huggingface.co/asoba/EnergyAnalyst-v0.1
- **LM Studio:** https://lmstudio.ai

---

**Thank you for using Zorora!** We hope it helps streamline your research and development workflows.
