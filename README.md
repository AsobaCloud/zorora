# Zorora - Multi-Model Orchestration REPL

A local coding assistant REPL with intelligent multi-model delegation, specialized tool routing, and hybrid local/remote inference.

## Overview

Zorora is a tool-using REPL that orchestrates multiple specialized AI models to handle different types of tasks. A lightweight orchestrator model routes queries to specialist models and tools based on task requirements. Supports both local (LM Studio) and remote (HuggingFace) inference endpoints.

## Architecture

### Multi-Model Orchestration

```
User Query
    ↓
Intent Detection (fast classifier) → Suggests tool
    ↓
Orchestrator Model (fast, lightweight)
    ↓ (intelligently routes to...)
    ├─→ Filesystem Tools (read, write, list, run_shell, apply_patch)
    ├─→ Vision Tools (analyze_image - OCR & image understanding)
    ├─→ Image Generation (generate_image - text-to-image with Flux Schnell)
    ├─→ Codestral (code generation - local or HF endpoint)
    ├─→ Reasoning Model (planning, complex analysis)
    ├─→ Search Model (AI knowledge retrieval)
    ├─→ Web Search (Brave Search API + DuckDuckGo fallback - current information)
    └─→ EnergyAnalyst (energy policy RAG)
    ↓
Final Response (synthesized from tools/models)
```

### Key Principles

- **Intelligent Routing**: Intent detection + orchestrator for optimal tool selection
- **Hybrid Inference**: Mix local models with remote HuggingFace endpoints
- **Multi-Iteration**: Chain multiple tool calls for comprehensive answers
- **Context Management**: Smart summarization preserves conversation history
- **Specialist Models**: Each model optimized for specific tasks
- **RAG Integration**: EnergyAnalyst provides domain-specific policy knowledge

## Features

- ✅ **Multi-model delegation** - Orchestrator routes to specialist models
- ✅ **Hybrid deployment** - Local + remote HuggingFace endpoints
- ✅ **Intent detection** - Fast classifier prevents orchestrator confusion
- ✅ **Vision/OCR** - Image analysis with VL models (Qwen3-VL)
- ✅ **Image generation** - Text-to-image with Flux Schnell (16:9, 1344x768)
- ✅ **Filesystem tools** - Read, write, list, shell commands, patches
- ✅ **Code generation** - Dedicated models for coding tasks
- ✅ **Context summarization** - Intelligent conversation compression for VRAM
- ✅ **Conversation persistence** - Auto-save, resume, history browser
- ✅ **Web search** - Real-time information via Brave Search API with DuckDuckGo fallback, query caching, parallel search, and result optimization
- ✅ **Energy policy analysis** - RAG-powered insights from 485+ documents
- ✅ **Model selection** - Interactive `/models` command with HF endpoint management
- ✅ **Retry logic** - Automatic retries for transient failures
- ✅ **Rich UI** - Colored output, progress indicators, execution times

## Getting Started

### Prerequisites

- **Python 3.8+** installed
- **LM Studio** running on `http://localhost:1234`
  - Download: [lmstudio.ai](https://lmstudio.ai)
  - Load at least one model (e.g., Qwen3-VL-8B, Qwen3-4B)
- **HuggingFace token** (optional) - For remote inference endpoints

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

### Optional: HuggingFace Inference Endpoints

For remote inference (e.g., larger models like Qwen2.5-Coder-32B):

1. **Get HF token:** https://huggingface.co/settings/tokens
2. **Configure via `/models` command:**
   - Add new HF endpoint (URL, model name, timeout)
   - Set HF token
   - Assign endpoints to roles (orchestrator, codestral, etc.)

3. **Or edit `config.py` manually:**
```python
HF_TOKEN = "hf_your_token_here"
HF_ENDPOINTS = {
    "qwen-coder-32b": {
        "url": "https://your-endpoint.endpoints.huggingface.cloud/v1/chat/completions",
        "model_name": "Qwen/Qwen2.5-Coder-32B-Instruct",
        "timeout": 120,
        "enabled": True,
    }
}
MODEL_ENDPOINTS = {
    "codestral": "qwen-coder-32b",  # Use HF endpoint for code generation
}
```

### Optional: EnergyAnalyst Integration

For energy policy queries with RAG (485+ policy documents):

```bash
# Clone from HuggingFace
cd ~/Workbench
git clone https://huggingface.co/asoba/EnergyAnalyst-v0.1
cd EnergyAnalyst-v0.1
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
- Vision/image analysis
- EnergyAnalyst endpoint (local/production/disabled)
- HuggingFace token
- Add new HF endpoints

**2. Start using Zorora:**
```
[2] ⚙ > What files are in this directory?
[3] ⚙ > Write a Python function to validate email addresses
[4] ⚙ > Analyze gdp.png and convert to markdown
[5] ⚙ > What are FERC Order 2222 requirements?
```

The orchestrator automatically routes queries to the appropriate tools!

## Available Tools

### Filesystem Tools
- `read_file(path)` - Read file contents
- `write_file(path, content)` - Write to file (auto-extracts code from markdown)
- `list_files(path)` - List directory contents
- `run_shell(command)` - Execute shell commands (whitelisted for safety)
- `apply_patch(path, unified_diff)` - Apply unified diff patch

### Vision Tools
- `analyze_image(path, task)` - Image analysis with VL model
  - OCR text extraction
  - Image-to-markdown conversion
  - Chart/graph understanding
  - Uses configured vision model (e.g., Qwen3-VL-8B)

- `generate_image(prompt, filename)` - Text-to-image generation
  - Uses Flux Schnell model via HuggingFace endpoint
  - 16:9 aspect ratio (1344x768 resolution)
  - Optimized parameters: guidance_scale=0.0, 4 inference steps
  - Auto-generates timestamped filename if not provided
  - Returns path to generated PNG file

### Specialist Models
- `use_codestral(code_context)` - Code generation and refactoring
  - Supports local or HF endpoints
  - Use for: Writing functions, refactoring, code reviews
  - Auto-extracts code from markdown when saving

- `use_reasoning_model(task)` - Complex planning and analysis
  - Model: Qwen3-4B-Thinking (chain-of-thought reasoning)
  - Use for: Multi-step planning, architectural decisions, trade-offs
  - Used for context summarization

- `use_search_model(query)` - Information retrieval from AI knowledge
  - Configurable model
  - Use for: General knowledge, explanations, research

### External Tools
- `web_search(query, max_results=5)` - Enhanced web search
  - **Primary**: Brave Search API (requires API key)
  - **Fallback**: DuckDuckGo (automatic if Brave unavailable)
  - **Features**:
    - Query caching (1-24 hour TTL, configurable)
    - Query optimization and intent detection
    - Parallel search (Brave + DuckDuckGo simultaneously)
    - Result deduplication, ranking, and domain diversity
    - Automatic news search routing
    - Content extraction (optional)
    - Result synthesis via LLM (optional)
  - Returns: Current information, news, real-time data
  - Automatic retries with exponential backoff
  - Graceful handling of rate limits

- `use_energy_analyst(query)` - Energy policy RAG system
  - Returns: Policy analysis with document sources
  - Context: 485+ energy policy documents
  - Use for: FERC orders, ISO/RTO rules, NEM policies, tariff analysis
  - Requires: EnergyAnalyst API server running on port 8000

## Slash Commands

### Model Configuration
- `/models` - Interactive model selector
  - Choose orchestrator model
  - Configure specialist models (codestral, reasoning, search, vision)
  - Add/manage HuggingFace inference endpoints
  - Update HF token
  - Changes saved to `config.py`
  - Requires REPL restart to apply

### Conversation Management
- `/history` - Browse saved conversation sessions
  - Shows session ID, message count, start time, preview
  - Conversations auto-saved to `.zorora/conversations/`

- `/resume <session_id>` - Resume a previous conversation
  - Loads full conversation history
  - Continue exactly where you left off

- `/save <filename>` - Save last specialist output to file
  - Saves code/analysis from last tool use
  - Auto-extracts code from markdown blocks

- `/clear` - Clear conversation context
  - Resets to fresh state
  - Keeps session for history

### Other
- `/visualize` - Show context usage statistics
  - Message count, token estimates, usage bar

- `/help` - Show available commands

- `exit`, `quit`, `q`, `Ctrl+C` - Exit the REPL

## Usage Examples

### Image Analysis & OCR
```
[1] ⚙ > analyze gdp.png and convert to markdown
```
*Routes to:* `analyze_image` → VL model extracts text/data → Returns markdown

### Image Generation
```
[2] ⚙ > generate an image of a sunset over mountains with vibrant colors
```
*Routes to:* `generate_image` → Flux Schnell creates 1344x768 image → Saves as `generated_YYYYMMDD_HHMMSS.png`

### Code Generation with Save
```
[3] ⚙ > create a python script that generates interactive charts
[4] ⚙ > save to chart.py
```
*Routes to:* `use_codestral` → Generates code with explanation → Saves only code to file

### General Queries
```
[5] ⚙ > What's the latest news about Python 3.13?
```
*Routes to:* `web_search` → Returns current news

### Energy Policy
```
[6] ⚙ > What are FERC Order 2222 requirements for battery storage?
```
*Routes to:* `use_energy_analyst` → Returns policy analysis with sources

### Filesystem Operations
```
[7] ⚙ > List all Python files in src/
```
*Routes to:* `list_files` → Shows directory contents

### Multi-Tool Queries
```
[8] ⚙ > What's the best way to monetize a solar farm in Vermont?
```
*Routes to:* `use_energy_analyst` → policy foundation
*Then:* `web_search` (multiple) → current Vermont-specific info
*Synthesizes:* Comprehensive answer with policy + current data

## Context Management

Zorora uses intelligent context summarization to handle long conversations efficiently:

### How It Works
- **Limit:** 50 messages per conversation
- **Trigger:** When limit reached, automatically summarizes oldest messages
- **Strategy:** Summarize oldest 35 messages, keep 15 recent
- **Result:** System + summary + 15 recent = ~17 total messages
- **Breathing room:** 33 messages before next summarization

### Benefits
- ✅ Preserves conversation context (not lost, just compressed)
- ✅ Reduces VRAM usage (~66% reduction)
- ✅ Prevents context-related crashes
- ✅ Less frequent summarization (33 message buffer)
- ✅ Uses configured reasoning model

### Configuration
```python
MAX_CONTEXT_MESSAGES = 50
ENABLE_CONTEXT_SUMMARIZATION = True
CONTEXT_KEEP_RECENT = 15  # Conservative for local VRAM
```

## Configuration

### Edit `config.py`

**Orchestrator Model:**
```python
MODEL = "qwen/qwen3-vl-8b"  # VL model for vision support
```

**Specialist Models:**
```python
SPECIALIZED_MODELS = {
    "codestral": {
        "model": "qwen/qwen3-vl-8b",
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
    "vision": {
        "model": "qwen/qwen3-vl-8b",
        "max_tokens": 3072,
        "temperature": 0.2,
        "timeout": 90,
    }
}
```

**HuggingFace Endpoints:**
```python
HF_TOKEN = "hf_your_token_here"
HF_ENDPOINTS = {
    "qwen-coder-32b": {
        "url": "https://your-endpoint.cloud/v1/chat/completions",
        "model_name": "Qwen/Qwen2.5-Coder-32B-Instruct",
        "timeout": 120,
        "enabled": True,
    }
}
MODEL_ENDPOINTS = {
    "orchestrator": "local",
    "codestral": "qwen-coder-32b",  # Use HF for code gen
    "reasoning": "local",
    "vision": "local",
}
```

**Or use the `/models` command** to configure interactively.

### API Endpoints

- **LM Studio:** `http://localhost:1234` (local models)
- **HuggingFace:** Custom inference endpoint URLs
- **EnergyAnalyst:** `http://localhost:8000` (RAG API server)

## Module Structure

```
zorora/
├── main.py                      # Entry point
├── repl.py                      # REPL loop and slash commands
├── config.py                    # Configuration and model settings
├── config.example.py            # Template (safe to commit)
├── system_prompt.txt            # Orchestrator instructions
├── conversation.py              # Conversation manager with summarization
├── conversation_persistence.py  # Save/load conversations
├── llm_client.py               # LM Studio/HF API client
├── tool_executor.py            # Tool execution engine
├── tool_registry.py            # Tool definitions and functions
├── turn_processor.py           # Multi-iteration with intent detection
├── model_selector.py           # Interactive model configuration
└── ui.py                       # Rich terminal UI
```

## How It Works

### 1. Intent Detection (Fast Routing)

Before the orchestrator runs, a fast intent detection model (4B) analyzes the query:
- Identifies the most appropriate tool
- High confidence → Forces tool execution (bypasses orchestrator)
- Low confidence → Falls back to orchestrator decision

This prevents orchestrator from making bad decisions and getting stuck in loops.

### 2. Orchestrator Routes Query

If intent detection doesn't force a tool, the orchestrator analyzes:
- Does this need filesystem access? → Call filesystem tools
- Is this a coding task? → Route to `use_codestral`
- Is there an image? → Route to `analyze_image`
- Need current information? → Route to `web_search`
- Energy policy question? → Route to `use_energy_analyst`
- Complex planning needed? → Route to `use_reasoning_model`

### 3. Tool Execution

Tools are called via:
- **Forced execution**: High-confidence intent detection
- **OpenAI function calling**: Standard tool calling format
- **Text parsing**: For models that output JSON as text (fallback)

When specialist tools execute, their output is saved and can be written to files with `write_file` (auto-extracts code from markdown).

### 4. Multi-Iteration

The orchestrator can make multiple tool calls in sequence:
```
Query → Tool 1 → Result → Tool 2 → Result → Tool 3 → Final Answer
```
Maximum 10 iterations with loop detection to prevent infinite loops.

### 5. Response Synthesis

The orchestrator receives all tool results and synthesizes them into a comprehensive, user-friendly response.

## Performance

- **Intent detection:** 1-2 seconds (fast classifier)
- **Orchestrator routing:** 0.5-2 seconds (fast decision)
- **Code generation:** 10-90 seconds (local: 10-30s, HF 32B: 60-90s)
- **Image analysis:** 5-15 seconds (VL model inference)
- **Context summarization:** 10-30 seconds (reasoning model)
- **Web search:** 1-3 seconds (network + parsing)
- **Energy analyst:** 60-120 seconds (RAG retrieval + LLM inference)
- **Multi-tool queries:** 30-180 seconds (depends on tool chain length)

## Troubleshooting

### LM Studio Not Connected
```
Error: Could not connect to LM Studio...
```
**Solution:** Start LM Studio and load a model on port 1234

### HuggingFace Endpoint Errors
```
Error: LLM API client error (HTTP 400): model has crashed
```
**Solution:**
- Check HF endpoint URL in `/models` or `config.py`
- Verify HF token is valid
- Check endpoint is running (not paused)
- Try reducing context size (use `/clear` to reset)

### EnergyAnalyst Timeout
```
Error: EnergyAnalyst API request timed out...
```
**Solution:**
- Check if API server is running: `http://localhost:8000/health`
- Clone from: `https://huggingface.co/asoba/EnergyAnalyst-v0.1`
- Restart with: `cd EnergyAnalyst-v0.1 && python api/server.py`
- Timeout is 180s (3 minutes) for slower inference

### Web Search SSL Errors
```
### Web Search Configuration

**Brave Search API** (recommended):
- Get free API key at: https://brave.com/search/api/
- Free tier: 2000 queries/month (~66/day)
- Configure in `config.py`:
  ```python
  BRAVE_SEARCH = {
      "api_key": "YOUR_API_KEY",
      "enabled": True,
      "endpoint": "https://api.search.brave.com/res/v1/web/search",
      "timeout": 10,
  }
  ```

**DuckDuckGo Fallback**:
- Automatically used if Brave Search is unavailable or fails
- No API key required
- Rate limiting: Automatic retry with exponential backoff

**Web Search Features** (configurable in `config.py`):
- Query caching (reduce API calls, 1-24 hour TTL)
- Query optimization (remove meta-language, detect intent)
- Parallel search (search both engines simultaneously)
- Result processing (deduplication, ranking, domain diversity)
- Content extraction (fetch full page content, optional)
- Result synthesis (LLM-powered summaries, optional)
- News search (automatic routing for news queries)

### Model Not Calling Tools / Stuck in Loops
```
Error: Loop detected. I called 'list_files' multiple times...
```
**Solution:**
- Intent detection should prevent this (enable if disabled)
- Try `/clear` to reset conversation
- Check orchestrator model supports function calling
- Avoid "thinking" models for orchestration (too verbose)

### Context/VRAM Issues
```
Error: Model has crashed (Exit code: 6)
```
**Solution:**
- Use `/clear` to reset context
- Reduce `CONTEXT_KEEP_RECENT` in `config.py` (default: 15)
- Enable context summarization (default: enabled)
- Use smaller models or HF endpoints for heavy tasks

## Best Practices

1. **Choose the right orchestrator:**
   - Fast, small models (4B-8B) work best for routing
   - VL models (Qwen3-VL) support both text and image understanding
   - Avoid "thinking" models for orchestration (too slow/verbose)

2. **Configure specialist models:**
   - Use `/models` command to select models you have loaded
   - Mix local and HF endpoints (local for fast tasks, HF for heavy lifting)
   - Match model strengths to tasks (32B for complex code, 4B for routing)

3. **Manage context:**
   - Use `/clear` when switching topics
   - `/save` specialist output before clearing
   - `/resume` previous conversations when needed
   - Context summarization handles long conversations automatically

4. **Start EnergyAnalyst when needed:**
   - Only required for energy policy queries
   - Clone from HuggingFace: `https://huggingface.co/asoba/EnergyAnalyst-v0.1`
   - System gracefully falls back to web search if not available

5. **Monitor performance:**
   - Execution times shown after each response
   - Multi-tool queries take longer but provide better answers
   - Use `/visualize` to check context usage

## Contributing

This is a personal project, but feel free to fork and adapt for your needs.

## License

See LICENSE file.

---

**Repository:** https://github.com/AsobaCloud/zorora
**EnergyAnalyst:** https://huggingface.co/asoba/EnergyAnalyst-v0.1
**Version:** 1.0.0
**Last Updated:** 2025-12-17
