# Zorora - Pocket Research Engine for AI & Energy

A lightweight research REPL optimized for knowledge acquisition, multi-source synthesis, and persistent storage. Built for macOS (Apple Silicon) with minimal RAM footprint.

## Overview

Zorora is a **focused research assistant** that helps you gather, synthesize, and save information about AI and energy topics. Rather than trying to be a general-purpose coding assistant, Zorora excels at one thing: **intelligent research workflows** that combine multiple sources and save findings for later retrieval.

### Design Philosophy

- **Deterministic over clever** - Code-controlled workflows, not LLM orchestration
- **Research-first** - Optimized for multi-source synthesis and citation management
- **RAM-efficient** - Runs on MacBook Air with 4B orchestrator model
- **Persistent knowledge** - Save and retrieve research findings locally
- **Simple and reliable** - Hardcoded pipelines that just work

## Architecture

### Simplified Routing

```
User Query
    ↓
Deterministic Decision Tree (pattern matching)
    ↓
    ├─→ RESEARCH WORKFLOW (newsroom + web + synthesis)
    │   └─→ Save to ~/.zorora/research/
    │
    ├─→ CODE WORKFLOW (code generation)
    │   └─→ Codestral specialist model
    │
    ├─→ FILE OPERATIONS (save/load/list)
    │   └─→ Research persistence system
    │
    └─→ SIMPLE Q&A (fallback)
        └─→ Direct model response
```

### Key Principles

- **No LLM-based orchestration** - Patterns determine routing, code controls execution
- **Hardcoded workflows** - Fixed pipelines for predictable results (newsroom → web → synthesis)
- **Persistent research** - Everything saved to `~/.zorora/research/` with metadata
- **Specialist models** - Codestral for code, reasoning model for synthesis
- **Hybrid inference** - Mix local models (4B orchestrator) with remote HuggingFace endpoints (32B Codestral)

## Features

- ✅ **Multi-source research** - Automatic newsroom + web search + synthesis
- ✅ **Research persistence** - Save/load findings with metadata and citations
- ✅ **Deterministic routing** - Pattern-based decision tree (no LLM routing failures)
- ✅ **Code generation** - Dedicated Codestral model for coding tasks
- ✅ **Hybrid deployment** - Local 4B orchestrator + remote 32B specialists
- ✅ **Vision/OCR** - Image analysis with VL models (optional)
- ✅ **Web search** - Real-time information via Brave Search API + DuckDuckGo fallback
- ✅ **Energy policy analysis** - Optional RAG system with 485+ policy documents
- ✅ **Rich UI** - Colored output, progress indicators, execution times
- ✅ **RAM-efficient** - Runs on MacBook Air M3 with 4B model

## Getting Started

### Prerequisites

- **Python 3.8+** installed
- **LM Studio** running on `http://localhost:1234`
  - Download: [lmstudio.ai](https://lmstudio.ai)
  - Load a 4B model (e.g., Qwen3-VL-4B, Qwen3-4B)
- **HuggingFace token** (optional) - For remote Codestral endpoint

### Installation

Install Zorora directly from GitHub:

```bash
pip install git+https://github.com/AsobaCloud/zorora.git
```

This installs the `zorora` command globally - you can run it from anywhere!

### Quick Start

1. **Start LM Studio** and load a 4B model (Qwen3-VL-4B recommended)

2. **Run Zorora:**
```bash
zorora
```

3. **Start researching:**
```
[1] ⚙ > Based on the newsroom as well as web search, what are the 5 or 6 major themes of 2025 in South America?
```

That's it! Zorora automatically:
- Fetches newsroom headlines
- Searches the web
- Synthesizes findings with citations
- Optionally saves results for later

## The Four Workflows

### 1. Research Workflow

**When triggered:** Queries that ask questions, mention sources, or request information

**What happens:**
1. Fetch newsroom headlines (if available)
2. Search the web (always)
3. Synthesize both sources with citations
4. Return comprehensive answer

**Examples:**
```
> Based on the newsroom as well as web search, what are the major AI trends in 2025?
> What's happening with battery storage in California?
> Tell me about recent developments in renewable energy policy
```

**Pipeline (hardcoded, no LLM planning):**
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

### 2. Code Workflow

**When triggered:** Requests to write, generate, or create code

**What happens:**
1. Route to Codestral specialist model
2. Generate code with explanation
3. Return formatted code

**Examples:**
```
> Write a Python function to validate email addresses
> Create a script that generates interactive charts
> Generate a class for parsing CSV files
```

**Model:** Local or remote Codestral (configurable via `/models`)

### 3. File Operations Workflow

**When triggered:** Commands to save, load, list, or show research

**What happens:**
1. Execute file operation (save/load/list/delete)
2. Interact with `~/.zorora/research/` directory
3. Return confirmation or content

**Examples:**
```
> Save this as "california_battery_storage"
> Load my research on AI trends
> List all my saved research
> Show me what I saved about FERC Order 2222
```

**Storage format:**
```markdown
---
{
  "topic": "California Battery Storage",
  "timestamp": "2025-12-20T15:30:00",
  "query": "battery storage in California",
  "sources": ["Newsroom", "Web"]
}
---

[Your research content with citations...]
```

### 4. Simple Q&A Workflow

**When triggered:** Simple questions that don't need research or code

**What happens:**
1. Direct query to reasoning model
2. Single-turn response
3. No tool use

**Examples:**
```
> What is a virtual power plant?
> Explain how demand response works
> Define capacity market
```

## Research Persistence

### Saving Research

**Automatic prompt after synthesis:**
```
[1] ⚙ > What are AI trends in 2025?
[Research synthesis with citations...]

Would you like to save this research? (yes/no)
> yes
Topic name: AI Trends 2025
Saved to: ~/.zorora/research/ai_trends_2025.md
```

**Manual save:**
```
[2] ⚙ > Save this as "ai_trends_2025"
Saved to: ~/.zorora/research/ai_trends_2025.md
```

### Loading Research

```
[3] ⚙ > Load my research on AI trends
[Displays content from ~/.zorora/research/ai_trends_2025.md]
```

### Listing Research

```
[4] ⚙ > List all my saved research

Saved Research (3 files):
─────────────────────────────────────────────────────────
1. AI Trends 2025
   Query: "AI trends in 2025"
   Saved: 2025-12-20 15:30:00
   File: ai_trends_2025.md

2. California Battery Storage
   Query: "battery storage in California"
   Saved: 2025-12-19 10:15:00
   File: california_battery_storage.md

3. FERC Order 2222
   Query: "FERC Order 2222 requirements"
   Saved: 2025-12-18 14:45:00
   File: ferc_order_2222.md
```

### Storage Location

All research is saved to `~/.zorora/research/` with:
- **Filename:** Slugified topic name (e.g., `ai_trends_2025.md`)
- **Format:** Markdown with JSON frontmatter
- **Metadata:** Topic, timestamp, original query, sources used
- **Content:** Synthesized findings with citations

## Available Tools

### Research Tools
- `get_newsroom_headlines()` - Fetch latest newsroom articles (if configured)
- `web_search(query)` - Search web via Brave API + DuckDuckGo fallback

### Code Tools
- `use_codestral(code_context)` - Generate code with specialist model
  - Supports local or HF endpoints
  - Use for: Writing functions, refactoring, code reviews

### File Persistence Tools
- `save_research(topic, content, query, sources)` - Save findings to file
- `load_research(topic)` - Load previously saved research
- `list_research()` - Show all saved research with metadata
- `delete_research(topic)` - Remove saved research file

### General Tools
- `use_reasoning_model(task)` - Direct reasoning/analysis
- `use_energy_analyst(query)` - Energy policy RAG (optional, requires API server)
- `analyze_image(path, task)` - Image analysis with VL model (optional)

## Slash Commands

### Model Configuration
- `/models` - Interactive model selector
  - Choose orchestrator model (4B recommended)
  - Configure Codestral endpoint (local or HuggingFace)
  - Add/manage HuggingFace inference endpoints
  - Update HF token
  - Changes saved to `config.py`

### Conversation Management
- `/history` - Browse saved conversation sessions
  - Shows session ID, message count, start time
  - Conversations auto-saved to `.zorora/conversations/`

- `/config` - Show current routing configuration
  - Display active workflow patterns
  - Show configured models and endpoints

- `/clear` - Clear conversation context
  - Resets to fresh state

### Other
- `/help` - Show available commands
- `exit`, `quit`, `q`, `Ctrl+C` - Exit the REPL

## Usage Examples

### Multi-Source Research

```
[1] ⚙ > Based on the newsroom as well as web search, what are the 5 or 6 major themes of 2025 in South America?

Step 1/3: Fetching newsroom articles...
  ✓ Found 12 articles

Step 2/3: Searching web...
  ✓ Found web results

Step 3/3: Synthesizing findings...
  ✓ Research complete

Based on analysis of newsroom and web sources, here are the 6 major themes of 2025 in South America:

1. **Renewable Energy Expansion** [Newsroom]
   - Brazil's offshore wind targets doubled to 35 GW by 2035
   - Chile's green hydrogen exports reached $2.1B in Q1 2025

2. **AI Adoption in Agriculture** [Web]
   - Argentina deployed AI crop monitoring across 5M hectares
   - Precision agriculture reduced water usage by 40%

[... more synthesized findings with citations ...]

Sources: Newsroom (12 articles), Web (8 results)

Would you like to save this research? (yes/no)
> yes
Topic name: South America 2025 Themes
Saved to: ~/.zorora/research/south_america_2025_themes.md
```

### Code Generation

```
[2] ⚙ > Write a Python function that parses energy consumption CSV files and calculates monthly totals

[Routes to Codestral...]

Here's a function that handles energy consumption CSV parsing:

```python
import pandas as pd
from datetime import datetime
from typing import Dict

def calculate_monthly_energy(csv_path: str) -> Dict[str, float]:
    """
    Parse energy consumption CSV and calculate monthly totals.

    Args:
        csv_path: Path to CSV file with columns [timestamp, kwh]

    Returns:
        Dictionary mapping month to total kWh consumption
    """
    df = pd.read_csv(csv_path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['month'] = df['timestamp'].dt.to_period('M')

    monthly_totals = df.groupby('month')['kwh'].sum().to_dict()
    return {str(k): v for k, v in monthly_totals.items()}
```

The function uses pandas for efficient data processing...

[3] ⚙ > Save this as "energy_parser.py"
Saved code to: energy_parser.py
```

### Saving and Loading Research

```
[4] ⚙ > Load my research on South America themes

Loaded from: ~/.zorora/research/south_america_2025_themes.md
Saved on: 2025-12-20 16:45:00
Original query: "major themes of 2025 in South America"

Based on analysis of newsroom and web sources, here are the 6 major themes...
[Full content displayed]

[5] ⚙ > List all my saved research

Saved Research (5 files):
─────────────────────────────────────────────────────────
1. South America 2025 Themes
   Query: "major themes of 2025 in South America"
   Saved: 2025-12-20 16:45:00

2. AI Trends 2025
   Query: "AI trends in 2025"
   Saved: 2025-12-20 15:30:00

[... more entries ...]
```

### Energy Policy Analysis

```
[6] ⚙ > What are FERC Order 2222 requirements for battery storage?

[Routes to EnergyAnalyst if available, otherwise web search...]

FERC Order 2222 Requirements for Battery Storage:

1. **Market Participation** [Policy Document]
   - DERs ≥100 kW can participate in wholesale markets
   - Aggregated resources allowed with 100 kW minimum

2. **Technical Requirements** [FERC Order 2222]
   - Metering and telemetry standards
   - Bidding parameters and dispatch instructions

[... more policy analysis with document citations ...]

Sources: FERC Order 2222 (2020), ISO/RTO compliance filings
```

## Configuration

### Basic Setup (Recommended)

Use the interactive `/models` command:

```
[1] ⚙ > /models

Zorora Model Configuration
────────────────────────────────────────

Current Configuration:
  Orchestrator: qwen/qwen3-vl-4b (local)
  Codestral:    qwen-coder-32b (HuggingFace)
  Reasoning:    qwen/qwen3-4b-thinking-2507 (local)

Options:
  1. Change orchestrator model
  2. Configure Codestral endpoint
  3. Add HuggingFace endpoint
  4. Update HF token
  5. Save and exit

Select option:
```

### Manual Configuration

Edit `config.py`:

**Orchestrator Model (4B recommended for RAM efficiency):**
```python
MODEL = "qwen/qwen3-vl-4b"  # Small VL model for vision support
```

**Specialist Models:**
```python
SPECIALIZED_MODELS = {
    "codestral": {
        "model": "qwen/qwen3-vl-4b",
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
}
```

**HuggingFace Endpoints (for 32B Codestral):**
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
    "codestral": "qwen-coder-32b",  # Use HF for code generation
}
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
- Automatically used if Brave Search unavailable
- No API key required
- Built-in rate limiting and retry logic

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

Configure the endpoint with `/models` command.

## Module Structure

```
zorora/
├── main.py                      # Entry point
├── repl.py                      # REPL loop and slash commands
├── config.py                    # Configuration and model settings
├── config.example.py            # Template (safe to commit)
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
└── model_selector.py           # Interactive model configuration
```

## How It Works

### 1. Deterministic Routing

When you submit a query, `simplified_router.py` uses pattern matching to decide the workflow:

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

### 2. Hardcoded Workflows

Once routed, workflows execute fixed pipelines:

**Research Workflow:**
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

**Code Workflow:**
```python
result = tool_executor.execute("use_codestral", {"code_context": user_input})
```

**File Workflow:**
```python
if action == "save":
    path = research_persistence.save(topic, content, query, sources)
elif action == "load":
    data = research_persistence.load(topic)
```

### 3. No Multi-Iteration Loops

Unlike complex orchestration systems, Zorora executes workflows **once** and returns the result. No planning, no iteration loops, no LLM deciding "should I call another tool?"

**Old approach (unreliable with 4B models):**
```
Query → LLM plans → LLM calls tool 1 → LLM decides next step → LLM calls tool 2 → ...
```

**New approach (deterministic):**
```
Query → Pattern match → Execute fixed pipeline → Return result
```

### 4. Synthesis with Citations

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

## Performance

- **Routing decision:** 0ms (pattern matching, no LLM)
- **Research workflow:** 10-60 seconds total
  - Newsroom fetch: 2-5s
  - Web search: 1-3s
  - Synthesis: 5-30s (local reasoning model)
- **Code generation:** 10-90 seconds (local: 10-30s, HF 32B: 60-90s)
- **File operations:** <100ms (local disk I/O)
- **RAM usage:** 4-6 GB (4B orchestrator model)

## Troubleshooting

### LM Studio Not Connected
```
Error: Could not connect to LM Studio...
```
**Solution:** Start LM Studio and load a model on port 1234

### Research Workflow Not Triggered
```
[Routes to simple Q&A instead of research...]
```
**Solution:** Include research keywords in your query:
- "Based on newsroom and web search..."
- "What are..."
- "Tell me about..."
- Add `/config` to see routing patterns

### Newsroom Not Available
```
Step 1/3: Fetching newsroom articles...
  ⚠ Newsroom unavailable, skipping
```
**Solution:** This is normal - workflow continues with web search only

### Can't Save Research
```
Error: Could not save research...
```
**Solution:** Check `~/.zorora/research/` directory exists and is writable

### HuggingFace Endpoint Errors
```
Error: LLM API client error (HTTP 400)
```
**Solution:**
- Check HF endpoint URL in `/models` or `config.py`
- Verify HF token is valid
- Check endpoint is running (not paused)

### Web Search Rate Limiting
```
Error: Web search failed - rate limited
```
**Solution:**
- Brave API: Check your API key and quota (2000/month free tier)
- DuckDuckGo: Automatic retry with exponential backoff

## Best Practices

1. **Use research keywords:**
   - Start queries with "What", "Why", "How", "Tell me"
   - Mention "newsroom" or "web search" explicitly
   - Ask questions rather than give commands

2. **Save important findings:**
   - Say "yes" when prompted to save after synthesis
   - Or use: "Save this as [topic_name]"
   - Research files stored in `~/.zorora/research/`

3. **Load previous research:**
   - "Load my research on [topic]"
   - "List all my saved research"
   - "Show me what I saved about [topic]"

4. **Separate code from research:**
   - Use "Write/Create/Generate" for code tasks
   - These route to Codestral automatically
   - Code output can be saved with "Save this as filename.py"

5. **Configure once, use forever:**
   - Run `/models` once to set up HF endpoints
   - Use 4B local model for orchestrator (RAM efficiency)
   - Use 32B HF endpoint for Codestral (code quality)

6. **Monitor research storage:**
   - Check `~/.zorora/research/` periodically
   - Delete old research with: "Delete my research on [topic]"
   - Each file is self-contained markdown with metadata

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

## Contributing

This is a personal project, but feel free to fork and adapt for your needs.

## License

See LICENSE file.

---

**Repository:** https://github.com/AsobaCloud/zorora
**EnergyAnalyst:** https://huggingface.co/asoba/EnergyAnalyst-v0.1
**Version:** 1.0.0
**Last Updated:** 2025-12-20
