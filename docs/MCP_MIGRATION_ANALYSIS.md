# MCP Migration Analysis: Zorora Deep Research Engine

> **Core Driver**: Better integration of tools and LLM
> **Date**: January 2026
> **Status**: Exploratory Analysis (No Code Changes)

---

## Executive Summary

Zorora is a local-first deep research engine built on **deterministic routing** rather than LLM orchestration. This architectural choice was deliberate—4B models struggle with JSON generation, tool chaining, and loop detection.

**Key Finding**: MCP solves **interoperability problems**, not **model quality problems**. Zorora's defensive code (parameter fixing, reference resolution, context injection) exists because small models need help—MCP doesn't change this.

**Final Recommendation**: **Do not adopt MCP.** External integration is not a product goal, and ONA ecosystem integration already works via the existing `RemoteCommand` pattern. Focus instead on:
1. Exposing deep research in terminal UI (`/deep` command)
2. Completing tool registry migration
3. Fixing naming inconsistencies (`use_codestral` → `use_coding_agent`)

This analysis includes an adversarial evaluation of whether MCP addresses any real problems in Zorora's architecture (Section 10).

---

## 1. Current State Assessment

### Architectural Philosophy

Zorora explicitly avoids LLM-based tool orchestration:

```
Traditional: Query → LLM plans → LLM calls tool 1 → LLM decides → LLM calls tool 2
Zorora:      Query → Pattern match → Execute fixed pipeline → Return result
```

This is the **"Code Over LLM"** principle—reliability through determinism.

### Existing Tool Categories

| Category | Tools | Retention Value |
|----------|-------|-----------------|
| **Research** | `academic_search`, `web_search`, `newsroom` | **Critical** - Core value proposition |
| **Specialist Models** | `use_coding_agent`, `use_reasoning_model`, `use_search_model` | **High** - Modular specialist routing |
| **File Operations** | `read_file`, `write_file`, `edit_file`, `list_files` | **Medium** - Standard utility |
| **External Integrations** | ONA Platform, Energy Analyst | **High** - Ecosystem connection |
| **Vision/Image** | `analyze_image`, `generate_image` | **Medium** - Modality expansion |

### Current Integration Pattern

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│ SimplifiedRouter│────▶│  Tool Registry   │────▶│  Tool Executor  │
│ (Pattern Match) │     │ (OpenAI Format)  │     │ (Arg Validation)│
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                                          │
                        ┌──────────────────┐              ▼
                        │   LLM Client     │◀────────────────────────
                        │ (Multi-Provider) │     Tool Results
                        └──────────────────┘
```

---

## 2. Tools to Retain

### Tier 1: Must Retain (Core Value)

These tools embody Zorora's unique value proposition and should be retained regardless of MCP adoption:

| Tool | Rationale |
|------|-----------|
| **`academic_search`** | Parallel 7-source academic search with Sci-Hub integration. 523 lines of domain-specific logic. No equivalent in any MCP marketplace. |
| **`web_search`** | Brave + DuckDuckGo with news intent detection. Custom failover logic. |
| **`newsroom`** | Asoba ecosystem integration. Proprietary API. |
| **Deep Research Workflow** | 4-phase pipeline (aggregate → score → cross-reference → synthesize). Core differentiator. |
| **Credibility Scoring** | Rules-based scoring system. Transparency guarantee. |

### Tier 2: High Value Retain

| Tool | Rationale |
|------|-----------|
| **`use_coding_agent`** | Modular coding specialist routing (model-agnostic). Tuned parameters per task type. |
| **`use_reasoning_model`** | Thinking model integration for complex synthesis. |
| **ONA Platform tools** | ML model observation (list/show/diff/promote/rollback). Ecosystem lock-in. |
| **Energy Analyst** | Domain-specific analysis. Custom HTTP integration. |

### Tier 3: Consider MCP Alternatives

| Tool | MCP Alternative Opportunity |
|------|----------------------------|
| `read_file`, `write_file`, `list_files` | Standard filesystem MCP server exists |
| `run_shell` | Standard shell MCP server exists |
| `analyze_image` | Vision MCP servers available |

---

## 3. MCP Framework Evaluation

### Framework Options

| Framework | Language | Maturity | Key Strength |
|-----------|----------|----------|--------------|
| **mcp-python** (Official) | Python | Production | Anthropic-maintained, reference implementation |
| **FastMCP** | Python | Stable | Decorator-based, Flask-like ergonomics |
| **mcp-framework** | TypeScript | Production | Strong typing, Zod validation |
| **Spring AI MCP** | Java | Emerging | Enterprise integration |

### Recommendation: **FastMCP**

**Rationale aligned with Zorora's goals:**

1. **Python Native**: Zorora is 100% Python. No language bridge friction.

2. **Minimal Boilerplate**: FastMCP's decorator pattern maps cleanly to existing tool functions:
   ```python
   # Current Zorora pattern
   def academic_search(query: str, max_results: int = 10) -> dict:
       ...

   # FastMCP migration (minimal change)
   @mcp.tool()
   def academic_search(query: str, max_results: int = 10) -> dict:
       ...
   ```

3. **Local-First Compatible**: FastMCP supports stdio transport (no network required), aligning with Zorora's privacy architecture.

4. **Gradual Migration Path**: Can run hybrid (MCP server + native tools) during transition.

5. **Active Development**: Regular releases, responsive maintainer.

---

## 4. MCP Integration Architecture

### Proposed Hybrid Model

Rather than full MCP replacement, Zorora should adopt a **hybrid architecture** where:

- **MCP Servers** expose tools to external clients (Claude Desktop, other MCP clients)
- **Internal Routing** remains deterministic (SimplifiedRouter preserved)
- **Custom Tools** (Tier 1) stay native; standard tools may optionally use MCP

```
                    ┌─────────────────────────────────┐
                    │        MCP Client Layer         │
                    │  (Claude Desktop, Cursor, etc.) │
                    └───────────────┬─────────────────┘
                                    │ MCP Protocol
                    ┌───────────────▼─────────────────┐
                    │      Zorora MCP Server          │
                    │  (FastMCP - exposes tools)      │
                    └───────────────┬─────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
        ▼                           ▼                           ▼
┌───────────────┐         ┌─────────────────┐         ┌─────────────────┐
│ Research Tools│         │ Specialist Tools│         │ External MCP    │
│ (Native)      │         │ (Native)        │         │ Servers         │
│ - academic    │         │ - coding_agent  │         │ - filesystem    │
│ - web_search  │         │ - reasoning     │         │ - shell         │
│ - newsroom    │         │ - search_model  │         │ - (optional)    │
└───────────────┘         └─────────────────┘         └─────────────────┘
```

### Why Hybrid?

1. **Preserve Determinism**: SimplifiedRouter continues to ensure reliable execution for REPL/Web UI users.

2. **Enable External Integration**: MCP exposure lets Claude Desktop or other AI assistants use Zorora's research capabilities.

3. **Avoid Regression**: 4B model limitations don't change. MCP orchestration would reintroduce the tool-chaining problems Zorora solved.

4. **Gradual Migration**: Test MCP integration without breaking existing interfaces.

---

## 5. Interaction Patterns

### Pattern A: Zorora as MCP Server (Recommended First Step)

External MCP clients can invoke Zorora tools:

```
Claude Desktop
    │
    │ MCP: tools/call "academic_search" {"query": "climate change", "max_results": 20}
    ▼
Zorora MCP Server
    │
    │ Internal: academic_search(query, max_results)
    ▼
Result returned via MCP protocol
```

**Benefits**:
- Zorora research becomes accessible to Claude Code, Claude Desktop, Cursor
- No changes to internal orchestration
- Additive capability, no regression risk

### Pattern B: Zorora as MCP Client (Future Consideration)

Zorora consumes external MCP servers for standard operations:

```
Zorora REPL
    │
    │ User: "create a file called notes.md"
    ▼
SimplifiedRouter → file operation detected
    │
    │ MCP: tools/call "write_file" (to external filesystem MCP server)
    ▼
Filesystem MCP Server executes
```

**Considerations**:
- Adds network/IPC latency for simple operations
- Dependency on external MCP server availability
- May be overkill for local-only deployment

### Pattern C: Federation (Advanced)

Zorora orchestrates multiple MCP servers:

```
Deep Research Query
    │
    ├─▶ Zorora Research Tools (native)
    │
    ├─▶ External Perplexity MCP Server (web augmentation)
    │
    └─▶ External Exa MCP Server (semantic search)
    │
    ▼
Aggregated Results → Credibility Scoring → Synthesis
```

**This aligns with the core driver**: Better tool-LLM integration by enabling access to a broader ecosystem of specialized tools.

---

## 6. Migration Considerations

### What MCP Solves for Zorora

| Challenge | MCP Solution |
|-----------|--------------|
| Tool discoverability | Standard `tools/list` protocol |
| Cross-application use | Claude Desktop, Cursor, etc. can use Zorora tools |
| Ecosystem access | Connect to MCP servers (databases, APIs, services) |
| Standardized interface | Replace bespoke OpenAI-format definitions |

### What MCP Does NOT Solve

| Challenge | Reality |
|-----------|---------|
| 4B model orchestration | MCP doesn't make small models better at planning |
| Tool chaining reliability | Still need deterministic pipelines |
| Local-first architecture | MCP adds protocol overhead |
| Research domain expertise | No MCP server matches `academic_search` |

### Migration Risks

1. **Latency**: MCP protocol overhead for every tool call
2. **Complexity**: Additional abstraction layer
3. **Debugging**: Tool calls now cross process boundaries
4. **Dependency**: FastMCP becomes critical dependency

---

## 7. Recommended Approach

### Phase 1: Expose Zorora as MCP Server (Low Risk, High Value)

1. Add FastMCP dependency
2. Create MCP server wrapper around existing tool registry
3. Expose research tools via MCP protocol
4. Test with Claude Desktop integration

**Deliverable**: Zorora tools accessible from any MCP client

### Phase 2: Evaluate External MCP Consumption (Medium Risk)

1. Identify candidate external MCP servers (filesystem, shell)
2. Prototype MCP client integration in Zorora
3. Benchmark latency vs native implementation
4. Decide whether complexity is justified

**Decision Point**: Is the ecosystem access worth the overhead?

### Phase 3: Federation Architecture (Future)

1. Design aggregation layer for multiple MCP sources
2. Integrate external research MCP servers (if valuable ones emerge)
3. Maintain credibility scoring across federated sources

---

## 8. Open Questions for Discussion

1. **Orchestration Model**: Should MCP clients (Claude Desktop) be trusted to orchestrate, or should Zorora always enforce its deterministic routing?

2. **Tool Granularity**: Should `academic_search` be one MCP tool, or should each source (PubMed, arXiv, etc.) be separate tools?

3. **State Management**: MCP is stateless by design. How do we handle research sessions that span multiple tool calls?

4. **Authentication**: How do we handle API keys (Brave, HuggingFace) when Zorora is an MCP server?

5. **Prioritization**: Should we prioritize being an MCP server (expose capabilities) or MCP client (consume ecosystem)?

---

## 9. Conclusion

MCP adoption for Zorora should be **additive, not transformative**. The core value—deterministic deep research with credibility scoring—should remain unchanged. MCP's primary benefit is **ecosystem integration**: letting external AI assistants leverage Zorora's unique research capabilities.

**Recommended Framework**: FastMCP (Python-native, minimal migration friction)

**Recommended First Step**: Implement Zorora as an MCP server exposing research tools

**Tools to Retain Natively**: All Tier 1 and Tier 2 tools (research, specialist models, external integrations)

**Core Principle**: Use MCP for integration, not orchestration.

---

## 10. Adversarial Analysis: What Problem Does MCP Actually Solve?

This section critically examines whether MCP addresses any real problems in Zorora's architecture, or whether the recommendation was based on pattern-matching ("Python REPL with tools → needs MCP") rather than actual code analysis.

### The Gemini Pattern-Match Problem

Generic AI recommendations often match surface patterns:
- "You have a Python REPL" ✓
- "You have tool calling" ✓
- "You have multiple tools" ✓
- → "Therefore you need MCP"

This reasoning ignores:
- **Why** the current architecture exists
- **What problems** it was designed to solve
- **Whether MCP** addresses those problems

### Zorora's Actual Problems (That Led to Current Design)

| Problem | Current Solution | Does MCP Fix It? |
|---------|------------------|------------------|
| 4B models generate wrong parameter names | `_fix_parameter_names()` defensive code | **No** - MCP doesn't improve model quality |
| 4B models output tool calls inconsistently | Multi-format parsing (XML, function_call, JSON) | **No** - MCP standardizes protocol, not model output |
| 4B models say "search for this topic" without context | Reference resolution from conversation history | **No** - MCP is stateless by design |
| 4B models don't pass context between tool calls | Auto-injection of previous tool outputs | **No** - MCP executes single tools, doesn't orchestrate |
| LLM-based routing is unreliable with small models | Deterministic `SimplifiedRouter` | **No** - MCP relies on client (LLM) to orchestrate |
| Tool results can bloat context window | Result truncation (10k chars) | **No** - MCP doesn't specify result limits |

**Conclusion**: Every piece of defensive code in Zorora exists because of **model quality limitations**. MCP is a **protocol standard**—it doesn't make models smarter.

### What MCP Actually Solves (In General)

| MCP Capability | Zorora Need? | Assessment |
|----------------|--------------|------------|
| **Tool discovery** (`tools/list`) | Low | Zorora's tools are fixed, not dynamic. No discovery needed. |
| **Standardized invocation** | Low | Already uses OpenAI-compatible format internally. |
| **Cross-application access** | Maybe | Could let Claude Desktop use Zorora tools. But is this a goal? |
| **Ecosystem consumption** | Low | Zorora is local-first. External MCP servers add latency and dependencies. |
| **Protocol standardization** | Low | Zorora controls both ends (REPL/Web UI ↔ tools). No interop needed. |

### The "Claude Desktop Integration" Argument

The strongest case for MCP is: "Expose Zorora's research tools to Claude Desktop."

**But consider:**
1. Claude Desktop already has web search. Why would users prefer Zorora's?
2. Zorora's value is the **orchestration** (deterministic routing, context injection, credibility scoring)—not just the raw tools.
3. Exposing tools via MCP without the orchestration gives a **degraded experience**.
4. Users who want Zorora's full capabilities should use Zorora directly.

### What Zorora's Architecture Already Does Well

| Aspect | Current State | MCP Improvement? |
|--------|---------------|------------------|
| **Tool modularity** | `tools/` directory, phased migration | None - already modular |
| **Tool definitions** | OpenAI-compatible JSON schema | Minimal - just different schema |
| **Provider abstraction** | Adapter pattern (LM Studio, HF, OpenAI, Anthropic) | None - already abstracted |
| **Workflow orchestration** | Deterministic routing, hardcoded pipelines | **Would regress** - MCP puts orchestration on client |
| **Research quality** | Context injection, reference resolution | **Would regress** - MCP is stateless |

### Actual Pain Points in Current Implementation

These are real issues—but MCP doesn't address them:

1. **Deep research not in terminal UI**
   - Gap: `/search` uses simple workflow, Web UI uses deep research engine
   - Fix: Add `/deep` command to REPL
   - MCP relevance: None

2. **Legacy tool registry duplication**
   - Gap: `tools/registry.py` imports from `tool_registry_legacy.py`
   - Fix: Complete the phased migration
   - MCP relevance: None

3. **Specialist tool naming confusion**
   - Gap: `use_codestral` is actually "coding agent" (model-agnostic)
   - Fix: Rename to `use_coding_agent`
   - MCP relevance: None

4. **No tool composition/chaining API**
   - Gap: Multi-tool workflows are hardcoded in `TurnProcessor`
   - Fix: Could create workflow DSL or composition layer
   - MCP relevance: **Partial** - MCP doesn't help, but a workflow layer could be exposed via MCP

### When MCP Would Actually Help

MCP becomes valuable if Zorora's goals change:

| Scenario | MCP Value |
|----------|-----------|
| "I want Claude Desktop users to access my research tools" | High |
| "I want to consume external tools (databases, APIs) via standard protocol" | Medium |
| "I want Zorora to be a tool server for multiple AI clients" | High |
| "I want to improve research quality for my REPL users" | **None** |
| "I want to fix model reliability issues" | **None** |
| "I want better tool orchestration" | **Negative** - MCP pushes orchestration to client |

### Honest Assessment

**MCP is a solution looking for a problem in Zorora's current architecture.**

The recommendation likely came from pattern-matching:
- "Python + REPL + tools" → "MCP is the modern standard"
- Without analyzing that Zorora's architecture was **deliberately designed** to work around the problems that MCP doesn't solve.

**If you want to improve Zorora**, the higher-value work is:
1. Expose deep research in terminal UI (`/deep` command)
2. Complete tool registry migration (eliminate legacy imports)
3. Improve credibility scoring algorithm
4. Add citation graph visualization
5. Enhance cross-referencing logic

**If you want external integration**, MCP makes sense—but recognize you're adding a new capability, not fixing an existing problem.

### Recommendation Revision

Given this analysis, the recommendation changes:

| Previous | Revised |
|----------|---------|
| "Adopt MCP with FastMCP" | "Defer MCP unless external integration becomes a goal" |
| "Expose tools as MCP server" | "Focus on internal improvements first" |
| "Consider MCP client for ecosystem" | "Avoid—adds complexity without clear value" |

**New recommendation**:
1. **Don't adopt MCP** — external integration is not a product goal
2. **Fix actual pain points** (deep research in terminal, legacy migration, naming)
3. **ONA ecosystem integration** already works via `RemoteCommand` pattern and HTTP client—no protocol change needed

### ONA Integration: Why MCP Adds No Value

The ONA Intelligence Layer integration already exists:

```python
# zorora/remote_command.py - existing pattern
class RemoteCommand:
    def execute(self, args, context) -> str

# Registered commands: ml-list-challengers, ml-show-metrics, ml-diff, ml-promote, ml-rollback
```

This integration:
- Uses direct HTTP calls to ONA Platform API
- Has typed command classes with validation
- Includes actor/environment context
- Returns formatted results for REPL display

MCP would add:
- Protocol overhead (JSON-RPC over stdio/SSE)
- No new capability
- Complexity without benefit

**Conclusion**: MCP is not recommended for Zorora. The architecture is sound, the ONA integration works, and there's no external integration goal that would justify the protocol overhead.

---

## 11. Tool Calling Logic: Deep Dive

This section analyzes the current tool calling implementation to understand what MCP would replace, preserve, or complicate.

### Current Implementation Architecture

```
User Input
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│                      TurnProcessor.process()                     │
│  ┌─────────────────┐                                            │
│  │ SimplifiedRouter│ ◀── Deterministic pattern matching         │
│  │   .route()      │     (no LLM involved)                      │
│  └────────┬────────┘                                            │
│           │                                                      │
│           ▼                                                      │
│  ┌─────────────────┐                                            │
│  │ Workflow        │ ◀── Hardcoded pipelines:                   │
│  │ Selection       │     research, code, file_op, qa, etc.      │
│  └────────┬────────┘                                            │
│           │                                                      │
│           ▼                                                      │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    ToolExecutor.execute()                    ││
│  │  ┌────────────────────┐  ┌──────────────────────┐          ││
│  │  │ _fix_parameter_    │  │ _truncate_result()   │          ││
│  │  │ names()            │  │ (10k char limit)     │          ││
│  │  │ • task → path      │  │ (specialist exempt)  │          ││
│  │  │ • file → path      │  └──────────────────────┘          ││
│  │  │ • prompt → task    │                                     ││
│  │  └────────────────────┘                                     ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

### Key Components Examined

#### 1. Parameter Fixing (`tool_executor.py:173-206`)

The executor includes defensive code to fix common parameter name mistakes:

```python
fixes = {
    "read_file": {"task": "path", "file": "path", "filename": "path"},
    "write_file": {"task": "path", "file": "path", "filename": "path"},
    "use_codestral": {"task": "code_context", "prompt": "code_context"},
    "use_reasoning_model": {"prompt": "task", "question": "task"},
    ...
}
```

**Why this exists**: 4B models frequently output wrong parameter names. Rather than fail, Zorora auto-corrects.

**MCP impact**: MCP standardizes tool definitions but doesn't prevent models from generating wrong parameter names. This logic would likely need to remain as a pre-processing step before MCP tool execution.

#### 2. Multi-Format Tool Call Parsing (`turn_processor.py:55-130`)

TurnProcessor handles multiple tool call formats because models are inconsistent:

| Format | Pattern | Example |
|--------|---------|---------|
| **XML-style** | `<tool_call>{"name": "...", "arguments": {...}}</tool_call>` | Qwen-style |
| **Function call** | `function_call: tool_name("arg")` | OpenAI-ish |
| **JSON object** | `{"tool": "...", "input": "..."}` | Generic |

**Why this exists**: Different models output tool calls differently, even when prompted consistently.

**MCP impact**: MCP clients handle this parsing—the protocol standardizes the format. However, if Zorora remains the "brain" (not just tool server), this parsing stays.

#### 3. Reference Resolution (`turn_processor.py:132-231`)

Resolves vague references like "this topic" to actual content:

```python
reference_patterns = [
    r'\bthis\s+topic\b',
    r'\bthe\s+plan\b',
    r'\babove\b',
    r'\bprevious\b',
    ...
]
```

**Why this exists**: Models often say "search for this topic" without specifying what "this" means. Zorora looks at `last_specialist_output` or conversation history to resolve.

**MCP impact**: MCP is stateless by design. Reference resolution requires session state. This would need to be handled by the MCP client (e.g., Claude Desktop) or preserved in Zorora's orchestration layer.

#### 4. Context Injection (`turn_processor.py:601-685`)

Automatically injects previous tool outputs into specialist tool calls:

```python
# Example: If reasoning model is called after academic_search,
# inject the search results into the reasoning task
arguments[param_name] = f"{context_str}\n\n---\nTask: {original_value}"
```

**Why this exists**: Small models don't reliably pass context between tool calls. Zorora compensates by auto-injecting.

**MCP impact**: This is Zorora-specific orchestration logic. MCP doesn't handle multi-step workflows—it just executes individual tools. If an MCP client orchestrates, they'd need equivalent logic or accept degraded quality.

#### 5. Result Truncation (`tool_executor.py:208-228`)

```python
MAX_TOOL_RESULT_SIZE = 10000  # characters

# Specialist tools exempt (return full response)
if tool_name in SPECIALIST_TOOLS:
    return result
```

**Why this exists**: Prevents context window bloat from large tool outputs.

**MCP impact**: MCP doesn't specify result size limits. This would need to be in the MCP server implementation or client-side.

### What MCP Standardizes vs. What It Doesn't

| Aspect | MCP Standardizes | Zorora-Specific |
|--------|------------------|-----------------|
| Tool definitions | ✅ Schema format | Parameter fixing logic |
| Tool invocation | ✅ Protocol | Multi-format parsing |
| Tool results | ✅ Response format | Truncation rules |
| Session state | ❌ Stateless | Reference resolution |
| Multi-step workflows | ❌ Single tools | Context injection |
| Orchestration | ❌ Client responsibility | SimplifiedRouter |

### MCP Options for Tool Calling

#### Option A: Zorora as Thin MCP Server (Minimal Change)

```
MCP Client (Claude Desktop) ──MCP──▶ Zorora MCP Server
                                           │
                                    ┌──────▼──────┐
                                    │ Tool        │
                                    │ Functions   │
                                    │ (unchanged) │
                                    └─────────────┘
```

**What changes**:
- Add FastMCP decorator to tool functions
- Expose tools via MCP protocol

**What stays**:
- Tool implementations unchanged
- Parameter fixing (in tool wrapper)
- Result truncation (in tool wrapper)

**What's lost**:
- Reference resolution (client's problem)
- Context injection (client's problem)
- Deterministic routing (client orchestrates)

#### Option B: Zorora Retains Orchestration + Exposes MCP

```
                    ┌─────────────────────────┐
                    │   External MCP Clients  │
                    └───────────┬─────────────┘
                                │ MCP Protocol
                    ┌───────────▼─────────────┐
                    │   Zorora MCP Server     │◀─┐
                    │   (tool exposure only)  │  │
                    └───────────┬─────────────┘  │
                                │                │
                    ┌───────────▼─────────────┐  │ Internal calls
REPL/Web UI ───────▶│   TurnProcessor         │  │ (not via MCP)
                    │   + SimplifiedRouter     │──┘
                    │   + ToolExecutor         │
                    │   (full orchestration)  │
                    └─────────────────────────┘
```

**What changes**:
- Add MCP server layer for external access
- Internal path unchanged

**What stays**:
- All current logic preserved for REPL/Web UI users
- Reference resolution, context injection, parameter fixing

**Tradeoff**: Two code paths—MCP exposure is "dumber" than internal use.

#### Option C: MCP Client for External Tools (Consume Ecosystem)

```
┌─────────────────────────────────────────────────────────────────┐
│                        TurnProcessor                             │
│                                                                  │
│   ┌─────────────┐     ┌────────────────────────────────────┐   │
│   │ Native      │     │ MCP Client                          │   │
│   │ Tools       │     │ ┌────────────┐  ┌────────────┐     │   │
│   │ • academic  │     │ │ Filesystem │  │ Database   │     │   │
│   │ • web_search│     │ │ MCP Server │  │ MCP Server │     │   │
│   │ • newsroom  │     │ └────────────┘  └────────────┘     │   │
│   └─────────────┘     └────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

**What changes**:
- Add MCP client capability
- Route some tools to external MCP servers

**Consideration**: Adds latency and complexity for tools that work fine natively.

### Recommendation for Tool Calling

**Preserve the defensive logic.** The parameter fixing, reference resolution, and context injection exist because 4B models need help. MCP doesn't solve model quality—it solves interoperability.

**Expose via MCP as Option B.** Keep full orchestration for REPL/Web UI. Add MCP server layer for external clients who want to use Zorora's research tools. Accept that MCP clients won't get the same quality without Zorora's orchestration.

**Consider MCP client selectively.** Only consume external MCP servers if they provide genuine value (e.g., a Perplexity MCP server for additional web context). Don't replace working native tools with MCP equivalents for purity.

---

## Appendix: Key File References

| Component | Path |
|-----------|------|
| Tool Registry | `tools/registry.py` |
| Tool Executor | `tool_executor.py` |
| Router | `simplified_router.py` |
| LLM Client | `llm_client.py` |
| Research Engine | `engine/research_engine.py` |
| Academic Search | `tools/research/academic_search.py` |
| Deep Research Workflow | `workflows/deep_research/workflow.py` |
