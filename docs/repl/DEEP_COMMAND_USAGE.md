# Deep Research Command (`/deep`)

## Overview

The `/deep` command provides access to Zorora's deep research workflow from the terminal (REPL), offering full feature parity with the Web UI research capabilities.

## Usage

```
/deep <research query>
```

**Examples:**
```
/deep What are the latest developments in battery storage technology?
/deep Based on newsroom and web search, what's happening with renewable energy policies in the EU?
/deep Tell me about recent AI trends in 2025 based on academic and news sources
```

## Features

### Multi-Source Synthesis
- **Academic Sources** - Searches 7 academic databases
- **Web Search** - Uses Brave + DuckDuckGo for comprehensive web coverage
- **Newsroom** - Access to Asoba's proprietary newsroom API
- **Credibility Scoring** - Automatic source reliability assessment
- **Cross-Reference Detection** - Identifies corroborating information across sources
- **Full Article Extraction** - Retrieves complete content when available

### Research Process
1. **Query Refinement** - Decomposes complex queries into targeted sub-questions
2. **Parallel Source Aggregation** - Simultaneously searches all available sources
3. **Evidence Ranking** - Prioritizes by relevance first, credibility second
4. **Structured Synthesis** - Creates outline → section expansion with quality gates
5. **Citation Management** - Inline citations using [Source Title] format
6. **Deterministic Fallback** - Structured output when model synthesis fails quality gates

## Configuration

Research depth and behavior are configured in `config.py`:

```python
# Depth profiles control research comprehensiveness
DEPTH_PROFILES = {
    1: {"max_results_per_source": 10, "max_sources": 5},    # Quick
    2: {"max_results_per_source": 25, "max_sources": 10},   # Standard
    3: {"max_results_per_source": 50, "max_sources": 20}    # Comprehensive
}

# Model budgets and synthesis settings
REASONING_MODEL = "qwen/qwen2.5:32b"  # For synthesis
MAX_TOKENS = 4000
TEMPERATURE = 0.1
```

## Shared Architecture

The `/deep` command shares the same execution path as the Web UI research:

- **Shared Service**: `engine/deep_research_service.py` handles the core research pipeline
- **Consistent Synthesis**: Both interfaces use identical synthesis contracts
- **Unified Storage**: Research findings saved to `~/.zorora/research/` with metadata
- **Cross-Interface Access**: Research initiated in one interface can be accessed in the other

## Output Format

Results include:
- **Synthesis**: Structured findings with inline citations
- **Sources**: Complete source list with metadata (title, URL, credibility, etc.)
- **Research Metadata**: Query, timestamp, depth level, source counts
- **Follow-up Capability**: Session ID enables contextual chat continuation

## Related Commands

- `/ask` - Simple questions without web search (for known information)
- `/research` - Legacy research command (equivalent to `/deep` depth=1)
- Research history access via `/api/research/<id>` endpoints

## Performance Expectations

- **Depth 1**: 10-25 seconds (quick overview)
- **Depth 2**: 20-45 seconds (standard research)
- **Depth 3**: 45-90 seconds (comprehensive analysis)
- **RAM Usage**: Consistent 4-6 GB regardless of depth