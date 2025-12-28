# Multi-Provider API Support - Technical Implementation Roadmap

## Executive Summary

This document outlines the technical implementation roadmap for adding ChatGPT API (OpenAI) and Claude API (Anthropic) support to Zorora's model selection system. This feature will extend the existing endpoint architecture to support multiple commercial API providers alongside the current local (LM Studio) and HuggingFace Inference Endpoints.

**Core Value Proposition:** Enable users to leverage commercial LLM APIs (ChatGPT, Claude) as alternatives or supplements to local models and HuggingFace endpoints, providing:
1. **Flexibility:** Choose from local, HuggingFace, OpenAI, or Anthropic models for each role
2. **Quality Options:** Access to GPT-4, Claude Opus, and other high-performance models
3. **Cost Management:** Mix local (free) and commercial (paid) models based on task requirements
4. **Unified Interface:** Same model selection workflow regardless of provider
5. **Consistent Patterns:** Follows existing `HF_ENDPOINTS` pattern exactly for minimal changes

**Deployment Model:**
- **API-based:** Uses external APIs (OpenAI, Anthropic) - requires internet and API keys
- **Backward Compatible:** Existing local and HF endpoint support remains unchanged
- **Optional:** Users can continue using only local/HF endpoints if desired
- **Cost-aware:** Users control which models use paid APIs

---

## Table of Contents

1. [Architectural Principles](#architectural-principles)
2. [System Architecture](#system-architecture)
3. [Design Decisions & Defensive Reasoning](#design-decisions--defensive-reasoning)
4. [Implementation Phases](#implementation-phases)
5. [Detailed Technical Specifications](#detailed-technical-specifications)
6. [Testing Strategy](#testing-strategy)
7. [Performance Considerations](#performance-considerations)
8. [Risk Mitigation](#risk-mitigation)
9. [Migration Path](#migration-path)

---

## Architectural Principles

### 1. **Unified Endpoint Abstraction**

**Principle:** All model providers (local, HuggingFace, OpenAI, Anthropic) are accessed through a unified endpoint abstraction layer.

**Defensive Reasoning:**
- **Consistency:** Same code path for all providers reduces complexity
- **Maintainability:** Single abstraction to update when adding new providers
- **Testability:** Can mock the abstraction layer for testing
- **Flexibility:** Easy to add new providers (e.g., Google Gemini, Cohere) later
- **User Experience:** Model selection UI works identically for all providers

**Current Architecture:**
```
MODEL_ENDPOINTS = {
    "orchestrator": "local",           # LM Studio
    "codestral": "qwen-coder-32b",    # HF endpoint
    "reasoning": "local",
}
```

**Extended Architecture:**
```
MODEL_ENDPOINTS = {
    "orchestrator": "gpt-4",          # OpenAI API (looked up in OPENAI_ENDPOINTS)
    "codestral": "qwen-coder-32b",    # HF endpoint (unchanged, looked up in HF_ENDPOINTS)
    "reasoning": "claude-opus",       # Anthropic API (looked up in ANTHROPIC_ENDPOINTS)
    "search": "local",                # LM Studio (unchanged)
}
```

**Provider Detection Pattern (matches existing HF pattern):**
- `"local"` → LM Studio (localhost:1234) - special case
- `"qwen-coder-32b"` → Check if in `HF_ENDPOINTS` dict → HuggingFace endpoint
- `"gpt-4"` → Check if in `OPENAI_ENDPOINTS` dict → OpenAI API (new)
- `"claude-opus"` → Check if in `ANTHROPIC_ENDPOINTS` dict → Anthropic API (new)
- If not found in any dict → Fallback to local with warning

---

### 2. **API Compatibility Layer**

**Principle:** Abstract API differences (OpenAI vs Anthropic formats) behind a compatibility layer.

**Defensive Reasoning:**
- **OpenAI Format:** Uses `/v1/chat/completions` with `messages` array
- **Anthropic Format:** Uses `/v1/messages` with different message structure
- **Tool Calling:** OpenAI uses `tools` array, Anthropic uses `tool_use` blocks
- **Streaming:** Different SSE formats
- **Error Handling:** Different error response structures

**Solution:** Create provider-specific adapters that normalize to a common interface.

**Adapter Pattern:**
```python
class LLMClient:
    def __init__(self, provider_type: str, ...):
        if provider_type == "openai":
            self.adapter = OpenAIAdapter(...)
        elif provider_type == "anthropic":
            self.adapter = AnthropicAdapter(...)
        elif provider_type == "local" or provider_type.startswith("hf:"):
            self.adapter = OpenAICompatibleAdapter(...)  # Existing
    
    def chat_complete(self, messages, tools=None):
        return self.adapter.chat_complete(messages, tools)
```

---

### 3. **Configuration-Driven Provider Setup**

**Principle:** Provider credentials and endpoints configured in `config.py`, similar to existing HF endpoints.

**Defensive Reasoning:**
- **Security:** API keys stored in config (not committed to git)
- **Flexibility:** Users configure only providers they want to use
- **Consistency:** Matches existing HF_ENDPOINTS pattern
- **Documentation:** Clear examples in config.example.py

**Configuration Structure:**
```python
# OpenAI API Configuration (matches HF_ENDPOINTS pattern)
OPENAI_API_KEY = ""  # Optional, can be set via /models UI or environment variable OPENAI_API_KEY
OPENAI_ENDPOINTS = {
    "gpt-4": {
        "model": "gpt-4",
        "timeout": 60,
        "enabled": True,
    },
    "gpt-4-turbo": {
        "model": "gpt-4-turbo-preview",
        "timeout": 60,
        "enabled": True,
    },
    "gpt-3.5-turbo": {
        "model": "gpt-3.5-turbo",
        "timeout": 30,
        "enabled": True,
    },
    # Add more OpenAI models here as needed
}

# Anthropic API Configuration (matches HF_ENDPOINTS pattern)
ANTHROPIC_API_KEY = ""  # Optional, can be set via /models UI or environment variable ANTHROPIC_API_KEY
ANTHROPIC_ENDPOINTS = {
    "claude-opus": {
        "model": "claude-3-opus-20240229",
        "timeout": 120,
        "enabled": True,
    },
    "claude-sonnet": {
        "model": "claude-3-sonnet-20240229",
        "timeout": 60,
        "enabled": True,
    },
    "claude-haiku": {
        "model": "claude-3-haiku-20240307",
        "timeout": 30,
        "enabled": True,
    },
    # Add more Anthropic models here as needed
}
```

---

### 4. **Backward Compatibility First**

**Principle:** All existing functionality (local, HF endpoints) must continue working without changes.

**Defensive Reasoning:**
- **Zero Breaking Changes:** Existing users unaffected
- **Gradual Adoption:** Users can add commercial APIs incrementally
- **Risk Mitigation:** If commercial APIs fail, fallback to local/HF
- **Testing:** Can test new providers without affecting existing workflows

**Compatibility Guarantees:**
- Existing `MODEL_ENDPOINTS` values (`"local"`, HF keys) work unchanged
- `LLMClient` default behavior unchanged (local LM Studio)
- `model_selector.py` UI works with new providers
- Tool registry specialist client creation unchanged

---

### 5. **Cost Awareness & Rate Limiting**

**Principle:** Provide visibility into API costs and implement rate limiting to prevent unexpected charges.

**Defensive Reasoning:**
- **User Protection:** Prevent accidental high costs from runaway requests
- **Transparency:** Show which models cost money vs free
- **Budget Control:** Allow users to set spending limits
- **Fair Usage:** Respect API rate limits

**Cost Indicators:**
- Model selector UI shows simple cost indicator: "Free" or "Paid"
- Displayed alongside model origin (e.g., "OpenAI: gpt-4 (Paid)")
- No detailed token counting or cost estimation (can add later if needed)

**Error Handling:**
- Clear error messages if API key missing or invalid
- Clear error messages if API unavailable
- No automatic fallback (user explicitly selected the model)
- Respects user's explicit model choice

---

## System Architecture

### **High-Level Architecture**

```
┌─────────────────────────────────────────────────────────────┐
│                    Model Selection Layer                      │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │         ModelSelector (model_selector.py)          │    │
│  │  - Lists models from all providers                 │    │
│  │  - Unified UI for selection                        │    │
│  │  - Updates MODEL_ENDPOINTS config                 │    │
│  └────────────────────────────────────────────────────┘    │
│                           │                                  │
│           ┌───────────────┴───────────────┐                 │
│           ▼                               ▼                 │
│  ┌─────────────────┐           ┌──────────────────┐        │
│  │  Provider       │           │  Provider        │        │
│  │  Discovery      │           │  Discovery       │        │
│  │  (list models)  │           │  (list models)   │        │
│  └─────────────────┘           └──────────────────┘        │
│           │                               │                  │
│           ▼                               ▼                  │
│  ┌────────────────────────────────────────────────────┐    │
│  │         LLMClient (llm_client.py)                    │    │
│  │  - Unified interface for all providers              │    │
│  │  - Provider adapter selection                       │    │
│  │  - Request/response normalization                   │    │
│  └────────────────────────────────────────────────────┘    │
│                           │                                  │
│           ┌───────────────┴───────────────┐                 │
│           ▼                               ▼                 │
│  ┌─────────────────┐           ┌──────────────────┐        │
│  │  OpenAIAdapter  │           │ AnthropicAdapter  │        │
│  │  - OpenAI API   │           │ - Anthropic API   │        │
│  │  - Format conv  │           │ - Format conv    │        │
│  └─────────────────┘           └──────────────────┘        │
│           │                               │                  │
│           ▼                               ▼                  │
│  ┌────────────────────────────────────────────────────┐    │
│  │         Existing: OpenAICompatibleAdapter           │    │
│  │  - LM Studio (local)                               │    │
│  │  - HuggingFace Endpoints                           │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### **File Structure**

```
zorora/
├── llm_client.py                    # MODIFIED: Add provider abstraction
├── config.py                        # MODIFIED: Add OpenAI/Anthropic config
├── model_selector.py                # MODIFIED: Support new providers
│
├── providers/                       # NEW: Provider-specific adapters
│   ├── __init__.py
│   ├── base.py                      # Abstract base adapter
│   ├── openai_adapter.py           # OpenAI API adapter
│   ├── anthropic_adapter.py        # Anthropic API adapter
│   └── openai_compatible_adapter.py # Existing (local/HF) - refactored
│
├── tool_registry_legacy.py          # MODIFIED: Use new provider system
├── repl.py                          # MODIFIED: Use new provider system
│
└── docs/
    └── MULTI_PROVIDER_API_IMPLEMENTATION.md  # This document
```

### **Configuration Structure**

```python
# config.py additions

# OpenAI API Configuration
OPENAI_API_KEY = ""  # Set via /models or environment variable
OPENAI_ENDPOINTS = {
    "gpt-4": {
        "model": "gpt-4",
        "timeout": 60,
        "enabled": True,
        "max_tokens": 4096,
    },
    "gpt-4-turbo": {
        "model": "gpt-4-turbo-preview",
        "timeout": 60,
        "enabled": True,
        "max_tokens": 4096,
    },
    "gpt-3.5-turbo": {
        "model": "gpt-3.5-turbo",
        "timeout": 30,
        "enabled": True,
        "max_tokens": 2048,
    },
}

# Anthropic API Configuration
ANTHROPIC_API_KEY = ""  # Set via /models or environment variable
ANTHROPIC_ENDPOINTS = {
    "claude-opus": {
        "model": "claude-3-opus-20240229",
        "timeout": 120,
        "enabled": True,
        "max_tokens": 4096,
    },
    "claude-sonnet": {
        "model": "claude-3-sonnet-20240229",
        "timeout": 60,
        "enabled": True,
        "max_tokens": 4096,
    },
    "claude-haiku": {
        "model": "claude-3-haiku-20240307",
        "timeout": 30,
        "enabled": True,
        "max_tokens": 4096,
    },
}

# Model Endpoint Mapping (extended)
# NOTE: Endpoint keys are simple strings (no prefixes) looked up in provider dicts
MODEL_ENDPOINTS = {
    "orchestrator": "local",              # LM Studio
    "codestral": "qwen-coder-32b",       # HF endpoint (looked up in HF_ENDPOINTS)
    "reasoning": "gpt-4",                 # OpenAI API (looked up in OPENAI_ENDPOINTS)
    "search": "claude-haiku",             # Anthropic API (looked up in ANTHROPIC_ENDPOINTS)
    "intent_detector": "local",
    "vision": "local",
    "image_generation": "local",
}
```

---

## Design Decisions & Defensive Reasoning

### Decision 1: Provider Adapter Pattern (Not Monolithic Client)

**Decision:** Create separate adapter classes for each provider instead of adding conditional logic to `LLMClient`.

**Alternatives Considered:**
1. **Monolithic LLMClient (REJECTED):** Would become 500+ lines with if/else chains
2. **Provider Adapters (CHOSEN):** Clean separation, easy to test, extensible

**Defensive Reasoning:**

**Why NOT Monolithic:**
- **Maintainability:** 500+ line file with nested conditionals is hard to maintain
- **Testing:** Hard to test individual providers in isolation
- **Extensibility:** Adding new provider requires modifying core client
- **Readability:** Code becomes unreadable with provider-specific logic mixed

**Why Adapter Pattern WINS:**
- **Separation of Concerns:** Each adapter handles one provider's quirks
- **Testability:** Test each adapter independently
- **Extensibility:** Add new provider = add new adapter file
- **Readability:** Clear, focused code per provider
- **Reusability:** Adapters can be reused elsewhere

**Implementation:**
```python
# providers/base.py
class BaseAdapter:
    def chat_complete(self, messages, tools=None):
        raise NotImplementedError
    
    def list_models(self):
        raise NotImplementedError

# providers/openai_adapter.py
class OpenAIAdapter(BaseAdapter):
    def __init__(self, api_key, model, ...):
        self.api_key = api_key
        self.model = model
    
    def chat_complete(self, messages, tools=None):
        # OpenAI-specific implementation
        ...

# llm_client.py
class LLMClient:
    def __init__(self, provider_type, ...):
        if provider_type == "openai":
            self.adapter = OpenAIAdapter(...)
        elif provider_type == "anthropic":
            self.adapter = AnthropicAdapter(...)
        # ...
```

---

### Decision 2: Endpoint Key Format: Simple Strings Looked Up in Dicts (Matches HF Pattern Exactly)

**Decision:** Use simple endpoint keys (e.g., `"gpt-4"`) that are looked up in provider-specific dicts, exactly matching the existing `HF_ENDPOINTS` pattern.

**Alternatives Considered:**
1. **Prefixed Keys (REJECTED):** `"openai-gpt-4"` - adds unnecessary complexity, doesn't match existing pattern
2. **Separate Fields (REJECTED):** `{"provider": "openai", "model": "gpt-4"}` - breaks existing pattern
3. **Simple Keys with Dict Lookup (CHOSEN):** `"gpt-4"` looked up in `OPENAI_ENDPOINTS` - matches `HF_ENDPOINTS` pattern exactly

**Defensive Reasoning:**

**Why NOT Prefixed Keys:**
- **Inconsistency:** Doesn't match existing HF pattern (HF uses `"qwen-coder-32b"`, not `"hf:qwen-coder-32b"`)
- **Complexity:** Requires parsing logic that doesn't exist for HF endpoints
- **Breaking Pattern:** Would require different lookup logic than existing code

**Why NOT Separate Fields:**
- **Breaking Change:** Would require refactoring `MODEL_ENDPOINTS` structure
- **Complexity:** More fields to manage in config
- **Inconsistency:** Different from existing HF endpoint pattern

**Why Simple Keys with Dict Lookup WINS:**
- **Exact Match:** Follows existing `HF_ENDPOINTS` pattern perfectly
- **Minimal Changes:** Same lookup logic: `if endpoint_key in config.OPENAI_ENDPOINTS`
- **Backward Compatible:** `"local"` and existing HF keys work unchanged
- **Consistency:** All providers use same pattern: simple key → dict lookup
- **Codebase Continuity:** Leverages existing code patterns exactly

**Endpoint Key Format (matches existing pattern):**
- `"local"` → LM Studio (special case, checked first)
- `"qwen-coder-32b"` → Checked in `HF_ENDPOINTS` dict → HuggingFace endpoint
- `"gpt-4"` → Checked in `OPENAI_ENDPOINTS` dict → OpenAI API (new)
- `"claude-opus"` → Checked in `ANTHROPIC_ENDPOINTS` dict → Anthropic API (new)
- If not found in any dict → Fallback to local with warning (existing behavior)

**IMPORTANT:** Endpoint keys MUST be unprefixed simple strings (e.g., `"gpt-4"`, not `"openai-gpt-4"`). Prefixed keys are deprecated examples only and MUST NOT be implemented. Lookup order determines provider: check `OPENAI_ENDPOINTS` first, then `ANTHROPIC_ENDPOINTS`, then `HF_ENDPOINTS`.

**Lookup Logic (matches existing `_create_specialist_client` pattern):**
```python
# Existing pattern for HF endpoints:
if endpoint_key == "local":
    # Use LM Studio
elif endpoint_key in config.HF_ENDPOINTS:
    hf_config = config.HF_ENDPOINTS[endpoint_key]
    # Use HF endpoint

# Extended pattern (same logic, additional dicts):
if endpoint_key == "local":
    # Use LM Studio
elif endpoint_key in config.HF_ENDPOINTS:
    hf_config = config.HF_ENDPOINTS[endpoint_key]
    # Use HF endpoint
elif endpoint_key in config.OPENAI_ENDPOINTS:
    openai_config = config.OPENAI_ENDPOINTS[endpoint_key]
    # Use OpenAI API
elif endpoint_key in config.ANTHROPIC_ENDPOINTS:
    anthropic_config = config.ANTHROPIC_ENDPOINTS[endpoint_key]
    # Use Anthropic API
else:
    # Fallback to local (existing behavior)
```

---

### Decision 3: Model Discovery: Configured Dicts (Matches HF Pattern Exactly)

**Decision:** Use configured endpoint dicts for model discovery, exactly matching the existing `HF_ENDPOINTS` pattern. No API discovery needed.

**Alternatives Considered:**
1. **API Discovery (REJECTED):** Adds complexity, doesn't match existing pattern
2. **Configured Dicts (CHOSEN):** Matches `HF_ENDPOINTS` pattern exactly

**Defensive Reasoning:**

**Why NOT API Discovery:**
- **Inconsistency:** HF endpoints don't use API discovery - they use configured `HF_ENDPOINTS` dict
- **Complexity:** Requires API calls, caching, error handling
- **Pattern Mismatch:** Doesn't follow existing codebase patterns
- **Anthropic Limitation:** Anthropic doesn't provide models API anyway

**Why Configured Dicts WINS:**
- **Exact Match:** Follows `HF_ENDPOINTS` pattern perfectly
- **Consistency:** All providers use same pattern: iterate through configured dict
- **Simplicity:** No API calls needed, just iterate `config.OPENAI_ENDPOINTS.items()`
- **User Control:** Users configure which models they want to use (like HF endpoints)
- **Codebase Continuity:** Leverages existing `get_available_models()` pattern exactly

**Implementation (matches existing HF pattern):**
```python
# Existing pattern for HF endpoints:
for endpoint_key, endpoint_config in config.HF_ENDPOINTS.items():
    if not endpoint_config.get("enabled", True):
        continue
    models.append({
        "name": endpoint_config["model_name"],
        "origin": f"HF: {endpoint_key}"
    })

# Extended pattern (same logic, additional dicts):
# OpenAI models
for endpoint_key, endpoint_config in config.OPENAI_ENDPOINTS.items():
    if not endpoint_config.get("enabled", True):
        continue
    models.append({
        "name": endpoint_config["model"],
        "origin": f"OpenAI: {endpoint_key}"
    })

# Anthropic models (same pattern)
for endpoint_key, endpoint_config in config.ANTHROPIC_ENDPOINTS.items():
    if not endpoint_config.get("enabled", True):
        continue
    models.append({
        "name": endpoint_config["model"],
        "origin": f"Anthropic: {endpoint_key}"
    })
```

**Note:** OpenAI does provide a models API, but we'll use configured dicts for consistency with existing pattern. Users can add models to `OPENAI_ENDPOINTS` as needed (just like they do with `HF_ENDPOINTS`).

---

### Decision 4: Unified Message Format (Normalize to OpenAI Format)

**Decision:** Convert all provider formats to OpenAI's message format internally, then convert to provider format when calling API.

**Alternatives Considered:**
1. **Provider-Native Formats (REJECTED):** Would require format conversion in every tool
2. **Unified Format (CHOSEN):** Single format internally, convert at adapter boundary

**Defensive Reasoning:**

**Why NOT Provider-Native:**
- **Complexity:** Every tool would need to handle multiple formats
- **Bugs:** Format conversion errors scattered throughout codebase
- **Maintenance:** Changes to message structure require updates everywhere

**Why Unified Format WINS:**
- **Simplicity:** Tools work with one format
- **Consistency:** Same message structure everywhere
- **Maintainability:** Format conversion isolated to adapters
- **Testing:** Test with one format, works for all providers

**Message Format (OpenAI Standard):**
```python
messages = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Hello!"},
    {"role": "assistant", "content": "Hi there!"},
]
```

**Adapter Conversion:**
- **OpenAI:** Use as-is (native format)
- **Anthropic:** Convert to Anthropic format (different role names, structure)
- **HF/Local:** Use as-is (OpenAI-compatible)

---

### Decision 5: Tool Calling Compatibility Layer

**Decision:** Normalize tool calling formats across providers, converting between OpenAI `tools` array and Anthropic `tool_use` blocks.

**Alternatives Considered:**
1. **Provider-Specific Tools (REJECTED):** Would require separate tool definitions per provider
2. **Normalized Tools (CHOSEN):** Define tools once in OpenAI format, convert in adapters

**Defensive Reasoning:**

**Why NOT Provider-Specific:**
- **Duplication:** Same tool defined multiple times
- **Maintenance:** Update tools in multiple places
- **Inconsistency:** Risk of tools diverging between providers

**Why Normalized Tools WINS:**
- **DRY Principle:** Define once, use everywhere
- **Consistency:** Same tools work for all providers
- **Maintainability:** Update tools in one place
- **Testing:** Test tools once, works for all providers

**Tool Format (OpenAI Standard):**
```python
tools = [
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search the web",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"}
                }
            }
        }
    }
]
```

**Adapter Conversion:**
- **OpenAI:** Use as-is
- **Anthropic:** Convert to Anthropic tool schema (different structure)
- **HF/Local:** Use as-is (OpenAI-compatible)

**Tool Result Ownership (MUST be explicit):**
- **Adapters return tool calls only:** Adapters extract tool calls from provider responses and return them in OpenAI format. Adapters do NOT execute tools or inject tool results.
- **Tool execution:** Tool execution is handled exclusively by existing tool registry logic (`tool_registry_legacy.py`, `tool_executor.py`).
- **Result reinjection:** After tool execution, tool results are appended to the messages array by the existing orchestrator/tool registry code (not by adapters).
- **Adapter responsibility:** Convert provider-specific tool call format → OpenAI tool call format.
- **Caller responsibility:** Execute tools, append results to messages, continue conversation loop.

---

## Implementation Phases

### Phase 1: Foundation - Provider Abstraction Layer

**Goal:** Create the provider adapter infrastructure without changing existing functionality.

**Tasks:**
1. **Create `providers/` directory structure**
   - `providers/__init__.py`
   - `providers/base.py` - Abstract base adapter
   - `providers/openai_compatible_adapter.py` - Refactor existing logic

2. **Refactor `LLMClient` to use adapters**
   - Extract local/HF logic to `OpenAICompatibleAdapter`
   - `LLMClient` becomes thin wrapper that selects adapter
   - Maintain 100% backward compatibility

3. **Update `_create_specialist_client()` in `tool_registry_legacy.py`**
   - Use new adapter system
   - No behavior changes, just internal refactor

4. **Update `_create_orchestrator_client()` in `repl.py`**
   - Use new adapter system
   - No behavior changes, just internal refactor

5. **Testing:**
   - Verify all existing functionality works unchanged
   - Test local LM Studio endpoint
   - Test HF endpoints
   - No new features yet, just refactoring

**Success Criteria:**
- ✅ All existing tests pass
- ✅ Local models work identically
- ✅ HF endpoints work identically
- ✅ No user-visible changes

**Estimated Time:** 2-3 days

---

### Phase 2: OpenAI API Integration

**Goal:** Add OpenAI (ChatGPT) API support.

**Tasks:**
1. **Create `providers/openai_adapter.py`**
   - Implement `BaseAdapter` interface
   - Handle OpenAI API format (messages, tools, streaming)
   - Error handling and retries
   - Rate limiting

2. **Add OpenAI configuration to `config.py`**
   - `OPENAI_API_KEY` (optional, can be env var)
   - `OPENAI_ENDPOINTS` dictionary
   - Default models: gpt-4, gpt-4-turbo, gpt-3.5-turbo

3. **Update `LLMClient` to support OpenAI endpoints**
   - Parse `"openai-<model>"` endpoint keys
   - Create `OpenAIAdapter` instances
   - Handle API key from config or environment

4. **Update `model_selector.py`**
   - Add OpenAI models to available models list
   - Fetch models from OpenAI API (with caching)
   - Display OpenAI models in selection UI
   - Handle API key configuration

5. **Update endpoint parsing logic**
   - `parse_endpoint_key()` function
   - Support `"openai-<model>"` format
   - Backward compatible with existing keys

6. **Testing:**
   - Test OpenAI API calls (gpt-3.5-turbo for cost)
   - Test model listing
   - Test tool calling
   - Test error handling (invalid key, rate limits)
   - Test fallback to local if OpenAI unavailable

**Success Criteria:**
- ✅ Can select OpenAI models in `/models` UI
- ✅ OpenAI models work for all roles (orchestrator, codestral, etc.)
- ✅ Tool calling works with OpenAI
- ✅ Error handling graceful (fallback to local)
- ✅ API key stored securely in config

**Estimated Time:** 3-4 days

---

### Phase 3: Anthropic API Integration

**Goal:** Add Anthropic (Claude) API support.

**Tasks:**
1. **Create `providers/anthropic_adapter.py`**
   - Implement `BaseAdapter` interface
   - Handle Anthropic API format (different message structure)
   - Convert between OpenAI and Anthropic formats
   - Tool calling conversion (OpenAI `tools` → Anthropic `tool_use`)
   - Error handling and retries

2. **Add Anthropic configuration to `config.py`**
   - `ANTHROPIC_API_KEY` (optional, can be env var)
   - `ANTHROPIC_ENDPOINTS` dictionary
   - Default models: claude-opus, claude-sonnet, claude-haiku

3. **Update `LLMClient` to support Anthropic endpoints**
   - Parse `"anthropic-<model>"` endpoint keys
   - Create `AnthropicAdapter` instances
   - Handle API key from config or environment

4. **Update `model_selector.py`**
   - Add Anthropic models to available models list
   - Use configured `ANTHROPIC_ENDPOINTS` (no API discovery)
   - Display Anthropic models in selection UI
   - Handle API key configuration

5. **Message format conversion**
   - Convert OpenAI message format → Anthropic format
   - Handle system messages (Anthropic uses different approach)
   - Convert assistant responses back to OpenAI format

6. **Tool calling conversion**
   - Convert OpenAI `tools` array → Anthropic tool schema
   - Convert Anthropic `tool_use` blocks → OpenAI tool calls format
   - Handle tool results format differences

7. **Testing:**
   - Test Anthropic API calls (claude-haiku for cost)
   - Test model listing (from config)
   - Test tool calling with format conversion
   - Test error handling (invalid key, rate limits)
   - Test fallback to local if Anthropic unavailable

**Success Criteria:**
- ✅ Can select Anthropic models in `/models` UI
- ✅ Anthropic models work for all roles
- ✅ Tool calling works with format conversion
- ✅ Message format conversion correct
- ✅ Error handling graceful (fallback to local)
- ✅ API key stored securely in config

**Estimated Time:** 4-5 days (more complex due to format conversion)

---

### Phase 4: Model Selector UI Enhancements

**Goal:** Enhance `/models` UI to show provider information and costs.

**Tasks:**
1. **Update `model_selector.py` display**
   - Show provider type (Local, HF, OpenAI, Anthropic)
   - Show cost indicator (Free vs Paid)
   - Group models by provider
   - Show API key status (configured vs not configured)

2. **Add provider configuration UI**
   - Configure OpenAI API key interactively
   - Configure Anthropic API key interactively
   - Mask keys in display (show first 4, last 4 chars)
   - Validate API keys (test connection)

3. **Update model listing (matches existing HF pattern)**
   - Show OpenAI models from `OPENAI_ENDPOINTS` dict (same pattern as HF)
   - Show Anthropic models from `ANTHROPIC_ENDPOINTS` dict (same pattern as HF)
   - Show local models from LM Studio (existing)
   - Show HF models from `HF_ENDPOINTS` dict (existing)
   - Handle errors gracefully (show warning, don't crash)

4. **Update config file writing**
   - **Config Write Semantics (MUST be explicit):**
     - Write method: Full file rewrite (read entire file, modify in memory, write atomically)
     - Atomicity: Write to temporary file, then rename (or use file locking if available)
     - If write fails: Show error message, do NOT update in-memory config state
     - If file is read-only: Show error, do NOT proceed with update
     - Environment variables: If user configures via env vars, still write to config.py for persistence (user can choose to use env vars instead)
     - Order: Preserve existing config.py structure and comments, only modify specified values
   - Write `OPENAI_API_KEY` to config.py (if provided via UI)
   - Write `ANTHROPIC_API_KEY` to config.py (if provided via UI)
   - Write `OPENAI_ENDPOINTS` if user adds custom models (append to existing dict)
   - Write `ANTHROPIC_ENDPOINTS` if user adds custom models (append to existing dict)
   - Update `MODEL_ENDPOINTS` with new provider keys (modify existing dict entries)

5. **Testing:**
   - Test UI with all provider types
   - Test API key configuration
   - Test model selection for each provider
   - Test error handling (invalid keys, network errors)

**Success Criteria:**
- ✅ UI clearly shows provider and cost for each model
- ✅ Can configure API keys interactively
- ✅ Model selection works for all providers
- ✅ Config file updates correctly
- ✅ Error messages helpful

**Estimated Time:** 2-3 days

---

### Phase 5: Error Handling & Clear Messages

**Goal:** Robust error handling with clear user messages (no automatic fallbacks).

**Tasks:**
1. **Error message clarity**
   - Clear error if API key missing or invalid
   - Clear error if API unavailable
   - Clear error if model not found in endpoint dict
   - User-friendly messages (not technical stack traces)

2. **API key validation**
   - Test API keys on configuration (optional test call)
   - Validate format (OpenAI: `sk-...`, Anthropic: `sk-ant-...`)
   - Show clear error if invalid format
   - Check environment variables as fallback (like HF_TOKEN pattern)

3. **Network error handling**
   - Timeout handling (configurable per provider via endpoint config)
   - Connection error handling
   - **Retry Policy (MUST be explicit):**
     - Retry up to 3 times (total of 4 attempts: initial + 3 retries)
     - Retry on: network errors (ConnectionError, Timeout), HTTP 429 (rate limit), HTTP 5xx (server errors)
     - Do NOT retry on: HTTP 4xx (client errors except 429), authentication errors (401, 403)
     - Exponential backoff: Start at 500ms, double each retry (500ms, 1000ms, 2000ms)
     - Add jitter: ±20% random variation to prevent thundering herd
     - Retries are per-request (not per-adapter instance)
   - Clear error messages (user explicitly selected the model, respect their choice)

4. **Rate limiting handling**
   - Detect rate limit errors (429 status)
   - Exponential backoff with jitter
   - Show user-friendly error message
   - Log for debugging

5. **Testing:**
   - Test error messages (missing key, invalid key, network errors)
   - Test rate limiting
   - Test timeout scenarios
   - Verify no automatic fallbacks (user's explicit choice respected)

**Success Criteria:**
- ✅ Clear error messages for all failure scenarios
- ✅ Rate limiting handled correctly
- ✅ No crashes on API errors
- ✅ User's explicit model choice respected (no automatic fallback)
- ✅ Logging helpful for debugging

**Estimated Time:** 1-2 days

---

### Phase 6: Documentation & Examples

**Goal:** Complete documentation and usage examples.

**Tasks:**
1. **Update README.md**
   - Add OpenAI/Anthropic setup instructions
   - Add API key configuration guide
   - Add cost considerations section

2. **Update config.example.py**
   - Add OpenAI configuration examples
   - Add Anthropic configuration examples
   - Add comments explaining each provider

3. **Create usage examples**
   - Example: Using GPT-4 for reasoning
   - Example: Using Claude for code generation
   - Example: Mixing local and commercial models

4. **Update COMMANDS.md**
   - Document `/models` command with new providers
   - Document API key configuration

5. **Create troubleshooting guide**
   - Common API errors and solutions
   - Rate limiting issues
   - Cost management tips

**Success Criteria:**
- ✅ Documentation complete and accurate
- ✅ Examples work out of the box
- ✅ Troubleshooting guide helpful
- ✅ Setup instructions clear

**Estimated Time:** 1-2 days

---

## Detailed Technical Specifications

### Provider Adapter Interface

**File:** `providers/base.py`

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class BaseAdapter(ABC):
    """Abstract base class for LLM provider adapters."""
    
    @abstractmethod
    def chat_complete(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> Dict[str, Any]:
        """
        Send chat completion request.
        
        Args:
            messages: List of message dicts (OpenAI format)
            tools: Optional list of tool definitions (OpenAI format)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            
        Returns:
            Response dict in OpenAI format:
            {
                "choices": [{
                    "message": {
                        "content": "...",
                        "tool_calls": [...]
                    },
                    "finish_reason": "stop"
                }],
                "usage": {"prompt_tokens": 10, "completion_tokens": 20}
            }
        """
        pass
    
    @abstractmethod
    def list_models(self) -> List[str]:
        """
        List available models from this provider.
        
        Returns:
            List of model identifiers
        """
        pass
    
    @abstractmethod
    def chat_complete_stream(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ):
        """
        Stream chat completion response.
        
        **MUST NOT support tool calls during streaming.** If tools are provided,
        streaming MUST be disabled and fall back to non-streaming chat_complete().
        
        Yields:
            UTF-8 text chunks as plain strings (not structured objects).
            Each chunk is a partial completion of the assistant's response.
            Chunks are concatenated to form the full response.
        
        **Contract:**
        - Yields only text content (str), never tool calls
        - If tools parameter is not None, raise ValueError or fall back to non-streaming
        - Chunks are incremental (each chunk extends previous chunks)
        - Completion signaled by generator exhaustion (StopIteration); empty string chunks are optional and may be yielded but are not required
        """
        pass
```

---

### OpenAI Adapter Implementation

**File:** `providers/openai_adapter.py`

```python
import requests
from typing import List, Dict, Any, Optional
from providers.base import BaseAdapter

class OpenAIAdapter(BaseAdapter):
    """Adapter for OpenAI API (ChatGPT)."""
    
    def __init__(
        self,
        api_key: str,
        model: str,
        timeout: int = 60,
        base_url: str = "https://api.openai.com/v1",
    ):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.base_url = base_url.rstrip("/")
        self.chat_url = f"{self.base_url}/chat/completions"
    
    def chat_complete(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> Dict[str, Any]:
        """Send chat completion request to OpenAI API."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        
        response = requests.post(
            self.chat_url,
            json=payload,
            headers=headers,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()
    
    def list_models(self) -> List[str]:
        """List available OpenAI models (from configured OPENAI_ENDPOINTS dict)."""
        # Note: We use configured dicts for consistency with HF_ENDPOINTS pattern
        # Users configure which OpenAI models they want to use in OPENAI_ENDPOINTS
        import config
        if hasattr(config, 'OPENAI_ENDPOINTS'):
            return list(config.OPENAI_ENDPOINTS.keys())
        return []
    
    def chat_complete_stream(self, messages, tools=None):
        """
        Stream chat completion from OpenAI API.
        
        **MUST NOT support tool calls during streaming.** If tools parameter
        is not None, MUST raise ValueError.
        
        Yields:
            UTF-8 text chunks (str) as they arrive from OpenAI SSE stream.
            Each chunk is incremental content from the assistant response.
        """
        if tools is not None:
            raise ValueError("Tool calls are not supported during streaming. Use chat_complete() instead.")
        
        # Implementation: Set stream=True in payload, parse SSE stream
        # Yield only content deltas as plain strings
        # Implementation details match existing llm_client.py chat_complete_stream pattern
        pass
```

---

### Anthropic Adapter Implementation

**File:** `providers/anthropic_adapter.py`

```python
import requests
from typing import List, Dict, Any, Optional
from providers.base import BaseAdapter

class AnthropicAdapter(BaseAdapter):
    """Adapter for Anthropic API (Claude)."""
    
    def __init__(
        self,
        api_key: str,
        model: str,
        timeout: int = 60,
        base_url: str = "https://api.anthropic.com/v1",
    ):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.base_url = base_url.rstrip("/")
        self.messages_url = f"{self.base_url}/messages"
    
    def _convert_messages_to_anthropic(
        self, messages: List[Dict[str, Any]]
    ) -> tuple[List[Dict[str, Any]], Optional[str]]:
        """
        Convert OpenAI message format to Anthropic format.
        
        **System Message Handling:**
        - If multiple system messages are present, concatenate them with "\\n\\n"
        - Pass as single Anthropic "system" field (not in messages array)
        - If no system messages, system_content is None
        
        **Message Format:**
        - OpenAI "user" → Anthropic "user" (unchanged)
        - OpenAI "assistant" → Anthropic "assistant" (unchanged)
        - OpenAI "system" → Extracted to system_content (not in messages array)
        
        Returns:
            Tuple of (anthropic_messages, system_content)
        """
        anthropic_messages = []
        system_parts = []
        
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            
            if role == "system":
                system_parts.append(content)
            elif role == "user":
                anthropic_messages.append({
                    "role": "user",
                    "content": content,
                })
            elif role == "assistant":
                anthropic_messages.append({
                    "role": "assistant",
                    "content": content,
                })
        
        # Concatenate multiple system messages
        system_content = "\n\n".join(system_parts) if system_parts else None
        
        return anthropic_messages, system_content
    
    def _convert_tools_to_anthropic(
        self, tools: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Convert OpenAI tools format to Anthropic format."""
        anthropic_tools = []
        
        for tool in tools:
            if tool.get("type") == "function":
                func = tool["function"]
                anthropic_tools.append({
                    "name": func["name"],
                    "description": func["description"],
                    "input_schema": func["parameters"],
                })
        
        return anthropic_tools
    
    def _convert_response_to_openai(
        self, anthropic_response: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Convert Anthropic response format to OpenAI format.
        
        **Conversion Rules (MUST be deterministic):**
        
        1. **Content Blocks:**
           - Extract all "text" type blocks from Anthropic response
           - Concatenate text blocks with "\\n" separator
           - Set as OpenAI message "content" field
        
        2. **Tool Calls:**
           - Extract all "tool_use" type blocks from Anthropic response
           - Convert each tool_use block to OpenAI tool_call format:
             {
                 "id": tool_use["id"],
                 "type": "function",
                 "function": {
                     "name": tool_use["name"],
                     "arguments": json.dumps(tool_use["input"])
                 }
             }
           - Collect all tool calls into single "tool_calls" array
           - Set in OpenAI message "tool_calls" field
        
        3. **Finish Reason:**
           - Map Anthropic "stop_reason" to OpenAI "finish_reason":
             - "end_turn" → "stop"
             - "max_tokens" → "length"
             - "tool_use" → "tool_calls"
             - Default → "stop"
        
        4. **Usage:**
           - Extract "usage" from Anthropic response if present
           - Map to OpenAI format: {"prompt_tokens": X, "completion_tokens": Y}
        
        5. **Multiple Blocks:**
           - If response contains both text and tool_use blocks:
             - Text blocks → concatenated into "content"
             - Tool_use blocks → all collected into "tool_calls"
             - Both fields present in final message
        
        Returns:
            OpenAI-format response dict with structure:
            {
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": "...",  # Concatenated text blocks
                        "tool_calls": [...]  # All tool_use blocks converted
                    },
                    "finish_reason": "stop" | "tool_calls" | "length"
                }],
                "usage": {"prompt_tokens": X, "completion_tokens": Y}
            }
        """
        import json
        
        # Extract content blocks
        content_parts = []
        tool_calls = []
        
        # Anthropic response structure: {"content": [{"type": "text", "text": "..."}, ...]}
        content_blocks = anthropic_response.get("content", [])
        
        for block in content_blocks:
            if block.get("type") == "text":
                content_parts.append(block.get("text", ""))
            elif block.get("type") == "tool_use":
                tool_calls.append({
                    "id": block.get("id", ""),
                    "type": "function",
                    "function": {
                        "name": block.get("name", ""),
                        "arguments": json.dumps(block.get("input", {}))
                    }
                })
        
        # Build OpenAI format message
        message = {
            "role": "assistant",
            "content": "\n".join(content_parts) if content_parts else None
        }
        
        if tool_calls:
            message["tool_calls"] = tool_calls
        
        # Map finish reason
        stop_reason = anthropic_response.get("stop_reason", "end_turn")
        finish_reason_map = {
            "end_turn": "stop",
            "max_tokens": "length",
            "tool_use": "tool_calls"
        }
        finish_reason = finish_reason_map.get(stop_reason, "stop")
        
        # Extract usage
        usage = anthropic_response.get("usage", {})
        openai_usage = {
            "prompt_tokens": usage.get("input_tokens", 0),
            "completion_tokens": usage.get("output_tokens", 0)
        }
        
        return {
            "choices": [{
                "message": message,
                "finish_reason": finish_reason
            }],
            "usage": openai_usage
        }
    
    def chat_complete(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> Dict[str, Any]:
        """Send chat completion request to Anthropic API."""
        anthropic_messages, system_content = self._convert_messages_to_anthropic(messages)
        
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": self.model,
            "messages": anthropic_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        
        if system_content:
            payload["system"] = system_content
        
        if tools:
            anthropic_tools = self._convert_tools_to_anthropic(tools)
            payload["tools"] = anthropic_tools
        
        response = requests.post(
            self.messages_url,
            json=payload,
            headers=headers,
            timeout=self.timeout,
        )
        response.raise_for_status()
        anthropic_data = response.json()
        
        # Convert to OpenAI format
        return self._convert_response_to_openai(anthropic_data)
    
    def list_models(self) -> List[str]:
        """List available Anthropic models (from config, no API endpoint)."""
        # Anthropic doesn't provide models API
        # Return models from configured ANTHROPIC_ENDPOINTS
        import config
        if hasattr(config, 'ANTHROPIC_ENDPOINTS'):
            return list(config.ANTHROPIC_ENDPOINTS.keys())
        return []
    
    def chat_complete_stream(self, messages, tools=None):
        """
        Stream chat completion from Anthropic API.
        
        **MUST NOT support tool calls during streaming.** If tools parameter
        is not None, MUST raise ValueError.
        
        Yields:
            UTF-8 text chunks (str) as they arrive from Anthropic SSE stream.
            Each chunk is incremental content from the assistant response.
            Only "text" type blocks are yielded (tool_use blocks are ignored).
        """
        if tools is not None:
            raise ValueError("Tool calls are not supported during streaming. Use chat_complete() instead.")
        
        # Implementation: Set stream=True in payload, parse Anthropic SSE stream
        # Yield only "text" block deltas as plain strings
        # Ignore "tool_use" blocks (streaming doesn't support tools)
        pass
```

---

### Client Creation Pattern (Matches Existing `_create_specialist_client`)

**File:** `tool_registry_legacy.py` (modified `_create_specialist_client` function)

**Note:** This shows the pattern for extending existing functions, not creating new abstractions. The actual implementation modifies `_create_specialist_client()` and `_create_orchestrator_client()` directly.

```python
def _create_specialist_client(role: str, model_config: Dict[str, Any]):
    """
    Create an LLMClient for a specialist role, using local, HF, OpenAI, or Anthropic endpoint.
    Matches existing pattern exactly, extended with new provider lookups.
    """
    from llm_client import LLMClient
    import config
    import os

    # Check if we have endpoint mappings (existing logic)
    endpoint_key = "local"
    if hasattr(config, 'MODEL_ENDPOINTS') and role in config.MODEL_ENDPOINTS:
        endpoint_key = config.MODEL_ENDPOINTS[role]

    # If local, use LM Studio (existing logic)
    if endpoint_key == "local":
        return LLMClient(
            api_url=config.API_URL,
            model=model_config["model"],
            max_tokens=model_config["max_tokens"],
            temperature=model_config["temperature"],
            timeout=model_config["timeout"]
        )

    # Check OpenAI endpoints (new, matches HF pattern)
    if hasattr(config, 'OPENAI_ENDPOINTS') and endpoint_key in config.OPENAI_ENDPOINTS:
        openai_config = config.OPENAI_ENDPOINTS[endpoint_key]
        # Get API key from config or environment variable
        api_key = config.OPENAI_API_KEY if hasattr(config, 'OPENAI_API_KEY') and config.OPENAI_API_KEY else os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(f"OPENAI_API_KEY not configured for endpoint '{endpoint_key}'")
        
        return LLMClient(
            api_url="https://api.openai.com/v1/chat/completions",
            model=openai_config.get("model", endpoint_key),
            max_tokens=model_config["max_tokens"],
            temperature=model_config["temperature"],
            timeout=openai_config.get("timeout", model_config["timeout"]),
            auth_token=api_key
        )

    # Check Anthropic endpoints (new, matches HF pattern)
    if hasattr(config, 'ANTHROPIC_ENDPOINTS') and endpoint_key in config.ANTHROPIC_ENDPOINTS:
        anthropic_config = config.ANTHROPIC_ENDPOINTS[endpoint_key]
        # Get API key from config or environment variable
        api_key = config.ANTHROPIC_API_KEY if hasattr(config, 'ANTHROPIC_API_KEY') and config.ANTHROPIC_API_KEY else os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(f"ANTHROPIC_API_KEY not configured for endpoint '{endpoint_key}'")
        
        # Use Anthropic adapter (would need to extend LLMClient or create adapter)
        # For now, this shows the lookup pattern - actual implementation may vary
        return create_anthropic_client(
            api_key=api_key,
            model=anthropic_config.get("model", endpoint_key),
            model_config=model_config,
            timeout=anthropic_config.get("timeout", model_config["timeout"])
        )

    # Check HF endpoints (existing logic)
    if hasattr(config, 'HF_ENDPOINTS') and endpoint_key in config.HF_ENDPOINTS:
        hf_config = config.HF_ENDPOINTS[endpoint_key]
        return LLMClient(
            api_url=hf_config["url"],
            model=hf_config["model_name"],
            max_tokens=model_config["max_tokens"],
            temperature=model_config["temperature"],
            timeout=hf_config.get("timeout", model_config["timeout"]),
            auth_token=config.HF_TOKEN if hasattr(config, 'HF_TOKEN') else None
        )

    # Fallback to local if endpoint not found (existing behavior)
    logger.warning(f"Endpoint '{endpoint_key}' not found for role '{role}', falling back to local")
    return LLMClient(
        api_url=config.API_URL,
        model=model_config["model"],
        max_tokens=model_config["max_tokens"],
        temperature=model_config["temperature"],
        timeout=model_config["timeout"]
    )
```

**Key Pattern:**
- Simple dict lookups: `if endpoint_key in config.OPENAI_ENDPOINTS`
- Matches existing HF pattern exactly
- API keys from config or environment (like HF_TOKEN pattern)
- Fallback to local if not found (existing behavior)

---

### Model Selector Updates

**File:** `model_selector.py` (modified sections)

```python
def get_available_models(self) -> List[Dict[str, str]]:
    """Fetch available models from all providers."""
    models = []
    
    # Local models (LM Studio)
    try:
        local_models = self.llm_client.list_models()
        for model in local_models:
            models.append({
                "name": model,
                "origin": "Local (LM Studio)",
                "provider": "local",
                "cost": "Free",
            })
    except Exception as e:
        self.ui.console.print(f"[yellow]Warning: Could not fetch LM Studio models: {e}[/yellow]")
    
    # HuggingFace endpoints
    import config
    if hasattr(config, 'HF_ENDPOINTS') and hasattr(config, 'HF_TOKEN'):
        for endpoint_key, endpoint_config in config.HF_ENDPOINTS.items():
            if not endpoint_config.get("enabled", True):
                continue
            models.append({
                "name": endpoint_config["model_name"],
                "origin": f"HF: {endpoint_key}",
                "provider": f"hf:{endpoint_key}",
                "cost": "Free (HF Inference)",
            })
    
    # OpenAI models (from config, matches HF pattern)
    import os
    openai_key = None
    if hasattr(config, 'OPENAI_API_KEY') and config.OPENAI_API_KEY:
        openai_key = config.OPENAI_API_KEY
    elif os.getenv("OPENAI_API_KEY"):
        openai_key = os.getenv("OPENAI_API_KEY")
    
    if openai_key and hasattr(config, 'OPENAI_ENDPOINTS'):
        for endpoint_key, endpoint_config in config.OPENAI_ENDPOINTS.items():
            if not endpoint_config.get("enabled", True):
                continue
            models.append({
                "name": endpoint_config.get("model", endpoint_key),
                "origin": f"OpenAI: {endpoint_key}",
                "provider": endpoint_key,  # Simple key, not prefixed
                "cost": "Paid",
            })
    
    # Anthropic models (from config, matches HF pattern)
    anthropic_key = None
    if hasattr(config, 'ANTHROPIC_API_KEY') and config.ANTHROPIC_API_KEY:
        anthropic_key = config.ANTHROPIC_API_KEY
    elif os.getenv("ANTHROPIC_API_KEY"):
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    
    if anthropic_key and hasattr(config, 'ANTHROPIC_ENDPOINTS'):
        for endpoint_key, endpoint_config in config.ANTHROPIC_ENDPOINTS.items():
            if not endpoint_config.get("enabled", True):
                continue
            models.append({
                "name": endpoint_config.get("model", endpoint_key),
                "origin": f"Anthropic: {endpoint_key}",
                "provider": endpoint_key,  # Simple key, not prefixed
                "cost": "Paid",
            })
    
    return models
```

---

## Testing Strategy

### Unit Tests

**File:** `tests/test_providers.py`

```python
import pytest
from providers.openai_adapter import OpenAIAdapter
from providers.anthropic_adapter import AnthropicAdapter
from providers.openai_compatible_adapter import OpenAICompatibleAdapter

def test_openai_adapter_chat_complete():
    """Test OpenAI adapter chat completion."""
    adapter = OpenAIAdapter(api_key="test-key", model="gpt-3.5-turbo")
    # Mock API response
    # Verify format conversion

def test_anthropic_adapter_message_conversion():
    """Test Anthropic message format conversion."""
    adapter = AnthropicAdapter(api_key="test-key", model="claude-haiku")
    messages = [{"role": "system", "content": "Test"}]
    anthropic_msgs, system = adapter._convert_messages_to_anthropic(messages)
    # Verify conversion correct

def test_endpoint_key_lookup():
    """Test endpoint key lookup in dicts (matches HF pattern)."""
    import config
    # Test that endpoint keys are looked up in correct dicts
    assert "gpt-4" in config.OPENAI_ENDPOINTS
    assert "claude-opus" in config.ANTHROPIC_ENDPOINTS
    assert "qwen-coder-32b" in config.HF_ENDPOINTS
```

### Integration Tests

**File:** `tests/test_integration.py`

```python
def test_model_selector_with_openai():
    """Test model selector lists OpenAI models."""
    # Requires valid OPENAI_API_KEY in test config
    selector = ModelSelector(...)
    models = selector.get_available_models()
    assert any(m["provider"].startswith("openai") for m in models)

def test_llm_client_with_openai():
    """Test LLMClient works with OpenAI endpoint."""
    # Test that endpoint key "gpt-4" is looked up in OPENAI_ENDPOINTS
    # and creates appropriate client
    client = _create_specialist_client("reasoning", {"model": "gpt-4", ...})
    response = client.chat_complete([{"role": "user", "content": "Hello"}])
    assert "choices" in response

def test_error_handling():
    """Test error handling if API key missing."""
    # Test that clear error is raised if OPENAI_API_KEY not configured
    # No automatic fallback - user explicitly selected the model
```

### Manual Testing Checklist

- [ ] Configure OpenAI API key via `/models`
- [ ] Select OpenAI model for orchestrator role
- [ ] Verify OpenAI model works for chat completion
- [ ] Verify tool calling works with OpenAI
- [ ] Configure Anthropic API key via `/models`
- [ ] Select Anthropic model for reasoning role
- [ ] Verify Anthropic model works for chat completion
- [ ] Verify tool calling works with Anthropic (format conversion)
- [ ] Test fallback if API key invalid
- [ ] Test fallback if API unavailable
- [ ] Test rate limiting handling
- [ ] Verify existing local models still work
- [ ] Verify existing HF endpoints still work
- [ ] Test model selector UI with all providers
- [ ] Verify config.py updates correctly

---

## Performance Considerations

### API Latency

**OpenAI API:**
- Typical latency: 500ms - 2s (depends on model)
- Streaming: Reduces perceived latency
- Rate limits: Varies by tier (free tier: 3 RPM)

**Anthropic API:**
- Typical latency: 1s - 3s (depends on model)
- Streaming: Available
- Rate limits: Varies by tier

**Mitigation:**
- Use streaming for better UX
- Cache model lists (1 hour TTL)
- Implement request queuing for rate limits
- Users can manually select local models for low-latency needs (no automatic fallback)

### Cost Optimization

**Strategies:**
1. **Hybrid Approach:** Use local for simple tasks, commercial for complex
2. **Model Selection:** Use cheaper models (gpt-3.5-turbo, claude-haiku) when possible
3. **Caching:** Cache responses for repeated queries
4. **Token Limits:** Set appropriate max_tokens to prevent over-generation

**Cost Tracking:**
- Log token usage per provider
- Estimate costs (if provider provides pricing)
- Warn user if high usage detected

---

## Risk Mitigation

### Risk 1: API Key Exposure

**Risk:** API keys stored in config.py could be committed to git.

**Mitigation:**
- `config.py` already in `.gitignore`
- `config.example.py` has placeholder keys
- Documentation warns against committing keys
- Consider environment variables as alternative

### Risk 2: Unexpected API Costs

**Risk:** Users could incur high costs from API usage.

**Mitigation:**
- Clear cost indicators in UI
- Optional cost tracking/logging
- Rate limiting to prevent runaway requests
- Documentation on cost management
- Default to local models (free)

### Risk 3: API Availability

**Risk:** Commercial APIs could be unavailable, breaking workflows.

**Mitigation:**
- **NO AUTOMATIC FALLBACK:** Once a user explicitly selects a model (via `/models` UI or config), that choice is respected. If the API is unavailable, show clear error message - do NOT automatically fall back to another provider.
- Graceful error handling with clear messages
- Retry logic with exponential backoff (see Phase 5 specifications)
- Users can manually reconfigure via `/models` if needed
- Default to local models for new installations (before user configures)

### Risk 4: Format Conversion Bugs

**Risk:** Anthropic format conversion could introduce bugs.

**Mitigation:**
- Comprehensive unit tests for conversion
- Integration tests with real API
- Fallback to OpenAI-compatible providers if conversion fails
- Clear error messages if conversion fails

### Risk 5: Breaking Changes to Existing Code

**Risk:** Refactoring could break existing functionality.

**Mitigation:**
- Phase 1: Pure refactoring, no new features
- Comprehensive testing before each phase
- Backward compatibility guarantees
- Gradual rollout (test with one provider first)

---

## Migration Path

### For Existing Users

**No Action Required:**
- Existing `MODEL_ENDPOINTS` configuration works unchanged
- Local models continue working
- HF endpoints continue working

**Optional Migration:**
1. Run `/models` command
2. Optionally configure OpenAI/Anthropic API keys
3. Optionally select commercial models for some roles
4. Continue using local/HF for other roles

### For New Users

**Setup Steps:**
1. Install Zorora
2. Configure LM Studio (local models)
3. Optionally configure OpenAI API key
4. Optionally configure Anthropic API key
5. Use `/models` to select models for each role

**Recommended Configuration:**
- **Orchestrator:** Local (fast, free)
- **Reasoning:** OpenAI GPT-4 or Claude Opus (high quality)
- **Code Generation:** Local or HF (free)
- **Search:** Local (fast, free)

---

## Success Metrics

### Phase 1 (Foundation)
- ✅ All existing tests pass
- ✅ No user-visible changes
- ✅ Code coverage maintained

### Phase 2 (OpenAI)
- ✅ Can use OpenAI models for all roles
- ✅ Tool calling works
- ✅ Error handling graceful

### Phase 3 (Anthropic)
- ✅ Can use Anthropic models for all roles
- ✅ Format conversion correct
- ✅ Tool calling works

### Phase 4 (UI)
- ✅ Model selector shows all providers
- ✅ API key configuration works
- ✅ User experience smooth

### Phase 5 (Error Handling)
- ✅ Clear error messages for all scenarios
- ✅ Rate limiting handled
- ✅ No crashes on errors
- ✅ User's explicit model choice respected

### Phase 6 (Documentation)
- ✅ Documentation complete
- ✅ Examples work
- ✅ Setup clear

---

## Conclusion

This implementation plan provides a comprehensive roadmap for adding ChatGPT (OpenAI) and Claude (Anthropic) API support to Zorora while maintaining backward compatibility and following established architectural patterns. The phased approach minimizes risk and allows incremental testing and validation.

**Key Benefits:**
- **Flexibility:** Users can choose the best model for each task
- **Quality:** Access to high-performance commercial models
- **Cost Control:** Mix free and paid models based on needs
- **Consistency:** Follows existing `HF_ENDPOINTS` pattern exactly
- **Minimal Changes:** Extends existing code, doesn't replace it
- **Extensibility:** Easy to add more providers in future (same pattern)

**Next Steps:**
1. Review and approve this plan
2. Begin Phase 1 (Foundation)
3. Test thoroughly before proceeding to next phase
4. Gather user feedback after each phase

---

**Document Version:** 1.0  
**Last Updated:** 2025-01-XX  
**Author:** Implementation Planning  
**Status:** Awaiting Approval
