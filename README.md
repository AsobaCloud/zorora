# Zorora - Multi-Model Orchestration REPL

A local coding assistant REPL with intelligent multi-model delegation and specialized tool routing.

## Overview

Zorora is a tool-using REPL that orchestrates multiple specialized AI models to handle different types of tasks. A lightweight orchestrator model routes queries to specialist models and tools based on task requirements.

## Architecture

### Multi-Model Orchestration

```
User Query
    ↓
Orchestrator Model (fast, lightweight)
    ↓ (intelligently routes to...)
    ├─→ Filesystem Tools (read, write, list, run_shell, apply_patch)
    ├─→ Codestral (code generation)
    ├─→ Reasoning Model (planning, complex analysis)
    ├─→ Search Model (AI knowledge retrieval)
    ├─→ Web Search (DuckDuckGo - current information)
    └─→ EnergyAnalyst (energy policy RAG)
    ↓
Final Response (synthesized from tools/models)
```

### Key Principles

- **Intelligent Routing**: Orchestrator automatically selects appropriate tools/models
- **Multi-Iteration**: Can chain multiple tool calls to gather comprehensive information
- **Graceful Fallbacks**: If one tool fails, tries alternatives
- **Specialist Models**: Each model optimized for specific tasks
- **RAG Integration**: EnergyAnalyst provides domain-specific knowledge from documents

## Features

- ✅ **Multi-model delegation** - Orchestrator routes to specialist models
- ✅ **Filesystem tools** - Read, write, list, shell commands, patches
- ✅ **Code generation** - Dedicated Codestral model for coding tasks
- ✅ **Web search** - Real-time information from DuckDuckGo
- ✅ **Energy policy analysis** - RAG-powered insights from 485+ policy documents
- ✅ **Model selection** - Interactive `/models` command to configure models
- ✅ **Retry logic** - Automatic retries for transient failures
- ✅ **Rich UI** - Colored output, progress indicators, execution times

## Getting Started

### Prerequisites

- **Python 3.8+** installed
- **LM Studio** running on `http://localhost:1234`
  - Download: [lmstudio.ai](https://lmstudio.ai)
  - Load at least one model (e.g., Qwen 3-4B, Mistral, etc.)

### Installation

Install Zorora directly from GitHub:

```bash
pip install git+https://github.com/AsobaCloud/zorora.git
```

This installs the `zorora` command globally - you can run it from anywhere!

### Quick Start

1. **Start LM Studio** and load a model

2. **Run Zorora:**
```bash
zorora
```

That's it! You're ready to go.

### Optional: EnergyAnalyst Integration

For energy policy queries with RAG (485+ policy documents):

```bash
# Clone and start the EnergyAnalyst API
cd ~/Workbench
git clone <energyanalyst-repo>
cd energyanalyst-v0.1
python api/server.py
# Runs on http://localhost:8000
```

Configure the endpoint in Zorora with `/models` command.

### First-Time Setup

**1. Configure models (optional):**
```
[1] ⚙ > /models
```

Select your preferred models for:
- Orchestrator (main routing)
- Code generation (Codestral)
- Reasoning/planning
- Search/research
- EnergyAnalyst endpoint (local/production/disabled)

**2. Start using Zorora:**
```
[2] ⚙ > What files are in this directory?
[3] ⚙ > Write a Python function to validate email addresses
[4] ⚙ > What are FERC Order 2222 requirements?
```

The orchestrator automatically routes queries to the appropriate tools!

## Available Tools

### Filesystem Tools
- `read_file(path)` - Read file contents
- `write_file(path, content)` - Write to file
- `list_files(path)` - List directory contents
- `run_shell(command)` - Execute shell commands
- `apply_patch(path, unified_diff)` - Apply unified diff patch

### Specialist Models
- `use_codestral(code_context)` - Code generation and refactoring
  - Model: Codestral-22B (optimized for code)
  - Use for: Writing functions, refactoring, code reviews

- `use_reasoning_model(task)` - Complex planning and analysis
  - Model: Qwen3-4B-Thinking (chain-of-thought reasoning)
  - Use for: Multi-step planning, architectural decisions, trade-offs

- `use_search_model(query)` - Information retrieval from AI knowledge
  - Model: Configurable (default: ii-search-4b)
  - Use for: General knowledge, explanations, research

### External Tools
- `web_search(query, max_results=5)` - DuckDuckGo web search
  - Returns: Current information, news, real-time data
  - Automatic retries with exponential backoff
  - Graceful handling of rate limits

- `use_energy_analyst(query)` - Energy policy RAG system
  - Returns: Policy analysis with document sources
  - Context: 485+ energy policy documents
  - Use for: FERC orders, ISO/RTO rules, NEM policies, tariff analysis
  - Requires: EnergyAnalyst API server running on port 8000

## Slash Commands

- `/models` - Interactive model selector
  - Choose orchestrator model
  - Configure specialist models (codestral, reasoning, search)
  - Changes saved to `config.py`
  - Requires REPL restart to apply

- `/help` - Show available commands

- `exit`, `quit`, `q` - Exit the REPL

## Usage Examples

### General Queries
```
[1] ⚙ > What's the latest news about Python 3.13?
```
*Routes to:* `web_search` → Returns current news

### Code Generation
```
[2] ⚙ > Write a function to validate email addresses with regex
```
*Routes to:* `use_codestral` → Generates optimized code

### Energy Policy
```
[3] ⚙ > What are FERC Order 2222 requirements for battery storage?
```
*Routes to:* `use_energy_analyst` → Returns policy analysis with sources

### Filesystem Operations
```
[4] ⚙ > List all Python files in src/
```
*Routes to:* `list_files` → Shows directory contents

### Multi-Tool Queries
```
[5] ⚙ > What's the best way to monetize a solar farm in Vermont?
```
*Routes to:* `use_energy_analyst` → policy foundation
*Then:* `web_search` (multiple) → current Vermont-specific info
*Synthesizes:* Comprehensive answer with policy + current data

## Configuration

### Edit `config.py`

**Orchestrator Model:**
```python
MODEL = "qwen/qwen3-4b-2507"  # Fast, decisive routing
```

**Specialist Models:**
```python
SPECIALIZED_MODELS = {
    "codestral": {
        "model": "mistralai/codestral-22b-v0.1",
        "max_tokens": 4096,
        "temperature": 0.3,
        "timeout": 90,
    },
    "reasoning": {
        "model": "qwen/qwen3-4b-thinking-2507",
        "max_tokens": 3072,
        "temperature": 0.4,
        "timeout": 90,
    },
    "search": {
        "model": "ii-search-4b",
        "max_tokens": 2048,
        "temperature": 0.5,
        "timeout": 60,
    }
}
```

**Or use the `/models` command** to configure interactively.

### API Endpoints

- **LM Studio:** `http://localhost:1234` (orchestrator + specialist models)
- **EnergyAnalyst:** `http://localhost:8000` (RAG API server)

## Module Structure

```
zorora/
├── main.py                 # Entry point
├── repl.py                 # REPL loop and slash commands
├── config.py               # Configuration and model settings
├── system_prompt.txt       # Orchestrator instructions
├── conversation.py         # Conversation history manager
├── llm_client.py          # LM Studio API client
├── tool_executor.py       # Tool execution engine
├── tool_registry.py       # Tool definitions and functions
├── turn_processor.py      # Multi-iteration tool calling loop
├── model_selector.py      # Interactive model configuration
└── ui.py                  # Rich terminal UI
```

## How It Works

### 1. Orchestrator Routes Query

The orchestrator model analyzes the user's query and determines:
- Does this need filesystem access? → Call filesystem tools
- Is this a coding task? → Route to `use_codestral`
- Need current information? → Route to `web_search`
- Energy policy question? → Route to `use_energy_analyst`
- Complex planning needed? → Route to `use_reasoning_model`

### 2. Tool Execution

Tools are called via JSON function calling or text parsing:
- **Proper function calls**: Standard OpenAI tool calling format
- **Text parsing**: For models that output JSON as text (fallback)

### 3. Multi-Iteration

The orchestrator can make multiple tool calls in sequence:
```
Query → Tool 1 → Result → Tool 2 → Result → Tool 3 → Final Answer
```
Maximum 10 iterations to prevent infinite loops.

### 4. Response Synthesis

The orchestrator receives all tool results and synthesizes them into a comprehensive, user-friendly response.

## Performance

- **Orchestrator response time:** 0.5-2 seconds (fast routing decision)
- **Code generation:** 10-30 seconds (Codestral inference)
- **Web search:** 1-3 seconds (network + parsing)
- **Energy analyst:** 60-120 seconds (RAG retrieval + LLM inference)
- **Multi-tool queries:** 30-180 seconds (depends on tool chain length)

## Troubleshooting

### LM Studio Not Connected
```
Error: Could not connect to LM Studio...
```
**Solution:** Start LM Studio and load a model on port 1234

### EnergyAnalyst Timeout
```
Error: EnergyAnalyst API request timed out...
```
**Solution:**
- Check if API server is running: `http://localhost:8000/health`
- Restart with: `cd ~/Workbench/energyanalyst-v0.1 && python api/server.py`
- Timeout is 180s (3 minutes) for slower inference

### Web Search SSL Errors
```
Web search attempt failed: Unsupported protocol version
```
**Solution:** Rate limiting - automatic retry with backoff. Successive searches may be temporarily blocked by DuckDuckGo.

### Model Not Calling Tools
- Check `system_prompt.txt` for correct tool examples
- Verify `TOOL_CHOICE` in `config.py` (should be `"required"` or `"auto"`)
- Try a different orchestrator model if current one doesn't support tools well

## Best Practices

1. **Choose the right orchestrator:**
   - Fast, small models (4B-8B) work best for routing
   - Should support OpenAI function calling format
   - Avoid "thinking" models for orchestration (too slow)

2. **Configure specialist models:**
   - Use `/models` command to select models you have loaded
   - Match model strengths to tasks (Codestral for code, etc.)

3. **Start EnergyAnalyst when needed:**
   - Only required for energy policy queries
   - System gracefully falls back to web search if not available

4. **Monitor performance:**
   - Execution times shown after each response
   - Multi-tool queries take longer but provide better answers

## Contributing

This is a personal project, but feel free to fork and adapt for your needs.

## License

See LICENSE file.

---

**Repository:** https://github.com/AsobaCloud/zorora
**Version:** 1.0.0
**Last Updated:** 2025-12-15
