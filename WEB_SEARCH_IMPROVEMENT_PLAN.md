# Web Search Enhancement Implementation Plan

## Current State Analysis

### Existing Implementation
- **Location**: `tool_registry.py` - `web_search()` function (lines 1241-1380)
- **Primary**: Brave Search API (if configured)
- **Fallback**: DuckDuckGo (`ddgs` library)
- **Return Format**: Plain text string with title, URL, description
- **Max Results**: 5 (default), up to 20 for Brave
- **Error Handling**: Basic retry logic (3 attempts for DuckDuckGo)
- **Result Truncation**: Yes (10,000 chars via `tool_executor.py`)
- **Dependencies**: `requests`, `ddgs` (already installed)

### Key Constraints
1. **Backward Compatibility**: Must maintain existing function signature `web_search(query: str, max_results: int = 5) -> str`
2. **Return Format**: Must return string (not dict/object) - used by orchestrator
3. **No Breaking Changes**: Existing calls must continue to work
4. **Tool Result Size**: Results truncated at 10,000 chars (non-specialist tool)
5. **Synchronous**: Current codebase uses synchronous `requests` (no async patterns)

---

## Implementation Plan

### Phase 1: Foundation & Infrastructure (Low Risk)

#### 1.1 Query Caching System
**Goal**: Cache frequent queries to reduce API calls and improve speed

**Implementation**:
- Create `_search_cache.py` module with in-memory cache
- Use `hashlib.md5` to create cache keys from queries
- Cache TTL: 1 hour for general queries, 24 hours for stable queries
- Cache size limit: 100 entries (LRU eviction)
- Config option: `WEB_SEARCH_CACHE_ENABLED = True`

**Files Modified**:
- `tool_registry.py` - Add cache check at start of `web_search()`
- `config.py` - Add cache configuration

**Risk**: Low - Can be disabled via config if issues arise

---

#### 1.2 Enhanced Result Formatting
**Goal**: Better structured output with metadata while maintaining string return

**Implementation**:
- Add metadata extraction (dates, domain, relevance hints)
- Enhanced formatting with markdown-style structure
- Optional JSON metadata in comments (for future parsing)
- Maintain backward compatibility with existing format

**Format Example**:
```
Web search results for: [query]

1. [Title]
   URL: [url]
   Domain: [domain] | Date: [date if available]
   [Description]

   [Additional metadata if available]
```

**Files Modified**:
- `tool_registry.py` - Enhance `_brave_search()` and `_duckduckgo_search()` formatting

**Risk**: Low - Only changes formatting, not structure

---

#### 1.3 Query Optimization & Intent Detection
**Goal**: Improve query quality before sending to search engines

**Implementation**:
- Create `_query_optimizer.py` helper module
- Detect query intent (news, technical, general)
- Basic query enhancement (add site: filters for technical queries)
- Query normalization (trim, remove redundant words)
- Config option: `WEB_SEARCH_QUERY_OPTIMIZATION = True`

**Files Created**:
- `_query_optimizer.py` - Query processing utilities

**Files Modified**:
- `tool_registry.py` - Apply optimization before search

**Risk**: Low - Can be disabled, non-breaking

---

### Phase 2: Multi-Source & Parallel Search (Medium Risk)

#### 2.1 Parallel Multi-Source Search
**Goal**: Search multiple sources simultaneously and aggregate results

**Implementation**:
- Use `concurrent.futures.ThreadPoolExecutor` for parallel requests
- Search Brave + DuckDuckGo simultaneously (if both available)
- Deduplicate results by URL
- Merge and rank results
- Config option: `WEB_SEARCH_PARALLEL_ENABLED = True`

**Files Modified**:
- `tool_registry.py` - Refactor `web_search()` to use parallel execution
- Add `_parallel_search()` helper function

**Risk**: Medium - Changes execution flow but maintains interface

**Dependencies**: None (uses stdlib `concurrent.futures`)

---

#### 2.2 Result Deduplication & Ranking
**Goal**: Remove duplicates and rank by relevance

**Implementation**:
- Deduplicate by URL (normalize URLs)
- Simple ranking: title match score, description match score
- Domain diversity: prefer results from different domains
- Config option: `WEB_SEARCH_MAX_DOMAIN_RESULTS = 2` (max results per domain)

**Files Modified**:
- `tool_registry.py` - Add `_deduplicate_results()` and `_rank_results()` helpers

**Risk**: Low - Post-processing, doesn't affect API calls

---

### Phase 3: Content Extraction & Summarization (Higher Risk)

#### 3.1 Content Extraction from Top Results
**Goal**: Fetch and extract content from top 2-3 results

**Implementation**:
- Add `beautifulsoup4` dependency for HTML parsing
- Fetch full page content from top results (configurable: 1-3 results)
- Extract main content (remove nav, ads, etc.)
- Extract structured data (JSON-LD, microdata)
- Truncate extracted content to prevent bloat
- Config option: `WEB_SEARCH_EXTRACT_CONTENT = False` (opt-in)

**Files Modified**:
- `tool_registry.py` - Add `_extract_page_content()` helper
- `setup.py` - Add `beautifulsoup4` dependency

**Risk**: Medium-High - Adds network calls, potential timeouts, requires new dependency

**Dependencies**: `beautifulsoup4>=4.11.0` (new)

---

#### 3.2 Integration with Search/Reasoning Models
**Goal**: Use existing models to synthesize search results

**Implementation**:
- Add optional synthesis step using `use_search_model()` or `use_reasoning_model()`
- Only synthesize if results exceed certain threshold
- Config option: `WEB_SEARCH_SYNTHESIZE = False` (opt-in)

**Files Modified**:
- `tool_registry.py` - Add optional synthesis call after search

**Risk**: Medium - Adds LLM calls, increases latency and cost

---

### Phase 4: Specialized Search Types (Low-Medium Risk)

#### 4.1 News Search Support
**Goal**: Use Brave's news endpoint for news queries

**Implementation**:
- Detect news intent in query
- Use Brave News API endpoint if available
- Format news results with dates prominently
- Config option: `WEB_SEARCH_NEWS_ENABLED = True`

**Files Modified**:
- `tool_registry.py` - Add `_brave_news_search()` function
- `config.py` - Add news endpoint configuration

**Risk**: Low-Medium - New API endpoint, but optional

---

#### 4.2 Image Search Support
**Goal**: Add image search capability

**Implementation**:
- Use Brave Image Search API endpoint
- Return image URLs with metadata
- Config option: `WEB_SEARCH_IMAGE_ENABLED = False` (opt-in)

**Files Modified**:
- `tool_registry.py` - Add `_brave_image_search()` function
- Consider separate tool: `web_image_search()` (future)

**Risk**: Low - Separate function, doesn't affect web_search

---

### Phase 5: Advanced Features (Lower Priority)

#### 5.1 Rate Limiting & Connection Pooling
**Goal**: Better API usage management

**Implementation**:
- Track API usage per provider
- Implement rate limiting with exponential backoff
- Use `requests.Session()` for connection pooling
- Config options for rate limits

**Files Modified**:
- `tool_registry.py` - Add rate limiting logic
- Create `_rate_limiter.py` helper module

**Risk**: Low - Internal improvements

---

#### 5.2 Source Verification & Cross-Referencing
**Goal**: Verify facts across multiple sources

**Implementation**:
- Extract key facts from results
- Cross-reference claims across sources
- Flag unverified information
- Config option: `WEB_SEARCH_VERIFY_FACTS = False` (opt-in, uses LLM)

**Files Modified**:
- `tool_registry.py` - Add fact extraction and verification

**Risk**: Medium - Adds complexity and LLM calls

---

## Implementation Order (Recommended)

### Sprint 1: Foundation (Low Risk, High Value)
1. ✅ Query caching system
2. ✅ Enhanced result formatting
3. ✅ Query optimization

### Sprint 2: Multi-Source (Medium Risk, High Value)
4. ✅ Parallel multi-source search
5. ✅ Result deduplication & ranking

### Sprint 3: Content Extraction (Higher Risk, Medium Value)
6. ⚠️ Content extraction (opt-in via config)
7. ⚠️ Integration with models (opt-in via config)

### Sprint 4: Specialized Search (Low-Medium Risk, Medium Value)
8. ✅ News search support
9. ✅ Image search support (separate tool)

### Sprint 5: Advanced Features (Lower Priority)
10. Rate limiting & connection pooling
11. Source verification (opt-in)

---

## Configuration Changes

### New Config Options in `config.py`:

```python
# Web Search Enhancement Configuration
WEB_SEARCH = {
    # Caching
    "cache_enabled": True,
    "cache_ttl_hours": 1,  # General queries
    "cache_ttl_stable_hours": 24,  # Stable queries (e.g., "Python documentation")
    "cache_max_entries": 100,
    
    # Query Optimization
    "query_optimization": True,
    "intent_detection": True,
    
    # Multi-Source
    "parallel_enabled": True,
    "max_domain_results": 2,  # Max results per domain
    
    # Content Extraction (opt-in)
    "extract_content": False,  # Set to True to enable
    "extract_top_n": 2,  # Extract from top N results
    
    # Synthesis (opt-in)
    "synthesize_results": False,  # Use LLM to synthesize
    "synthesize_threshold": 5,  # Min results to synthesize
    
    # Specialized Search
    "news_enabled": True,
    "image_enabled": False,
    
    # Rate Limiting
    "rate_limit_enabled": True,
    "brave_rate_limit": 66,  # queries per day (free tier: 2000/month)
    "ddg_rate_limit": 100,  # queries per hour (estimated)
}
```

---

## Dependencies

### New Dependencies Required:
- `beautifulsoup4>=4.11.0` - For HTML parsing (content extraction)
- `lxml>=4.9.0` - HTML parser backend (optional, faster)

### Already Available:
- `requests>=2.28.0` ✅
- `ddgs>=9.0.0` ✅
- `hashlib` (stdlib) ✅
- `concurrent.futures` (stdlib) ✅
- `json` (stdlib) ✅
- `re` (stdlib) ✅

---

## Testing Strategy

### Unit Tests
- Test query optimization
- Test caching (hit/miss)
- Test deduplication
- Test result ranking
- Test parallel search

### Integration Tests
- Test with real Brave API (if available)
- Test with DuckDuckGo fallback
- Test error handling
- Test rate limiting

### Manual Testing
- Test with various query types
- Test with disabled features (config)
- Test backward compatibility

---

## Backward Compatibility Guarantees

1. **Function Signature**: `web_search(query: str, max_results: int = 5) -> str` unchanged
2. **Return Format**: Still returns string (enhanced formatting, but still string)
3. **Error Handling**: Same error format ("Error: ...")
4. **Default Behavior**: All new features opt-in via config (default: disabled for risky features)
5. **Tool Definition**: No changes to tool definition in `TOOLS_DEFINITION`

---

## Risk Mitigation

### High-Risk Features (Opt-In Only)
- Content extraction: `WEB_SEARCH_EXTRACT_CONTENT = False` (default)
- Synthesis: `WEB_SEARCH_SYNTHESIZE = False` (default)
- Image search: Separate tool, doesn't affect `web_search`

### Medium-Risk Features (Configurable)
- Parallel search: Can disable if issues
- Query optimization: Can disable if breaking queries

### Low-Risk Features (Default Enabled)
- Caching: Can disable if cache issues
- Enhanced formatting: Only improves output
- Deduplication: Post-processing only

---

## File Structure

```
tool_registry.py          # Main web_search() function (modified)
_query_optimizer.py       # New: Query optimization utilities
_search_cache.py          # New: Caching system
_rate_limiter.py          # New: Rate limiting (future)
config.py                 # Modified: Add WEB_SEARCH config
setup.py                  # Modified: Add beautifulsoup4 dependency
requirements.txt          # Modified: Add beautifulsoup4
```

---

## Success Metrics

1. **Performance**: 50% reduction in API calls (via caching)
2. **Quality**: 30% improvement in result relevance (via optimization + ranking)
3. **Reliability**: 99% success rate (via parallel + fallback)
4. **Backward Compatibility**: 100% - all existing calls work unchanged

---

## Next Steps

1. **Review Plan**: Get approval for implementation approach
2. **Sprint 1**: Implement foundation features (caching, formatting, optimization)
3. **Test Sprint 1**: Validate no breaking changes
4. **Sprint 2**: Implement multi-source search
5. **Iterate**: Continue with remaining sprints based on feedback

---

## Questions for Review

1. Should content extraction be opt-in (default: False) or opt-out (default: True)?
2. Should synthesis be available, or skip entirely?
3. Should we add separate tools (`web_news_search`, `web_image_search`) or extend `web_search`?
4. What's the priority order? (Suggested: Sprint 1 → Sprint 2 → Sprint 3 → Sprint 4 → Sprint 5)
