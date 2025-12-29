# UX Beautification Plan - One-Shot Review

## Current Problem

**User sees this:**
```
2025-12-29 16:38:59,271 - turn_processor - INFO - User: what time is it in st. louis, missouri?
2025-12-29 16:38:59,274 - simplified_router - INFO - Routing to research workflow...
2025-12-29 16:38:59,274 - research_workflow - INFO - Starting research workflow...

Step 1/3: Fetching relevant newsroom articles...
2025-12-29 16:39:00,545 - tools.research.newsroom - WARNING - Newsroom API returned 401
2025-12-29 16:39:00,547 - research_workflow - INFO - Newsroom fetched: 46 chars
  ✓ Found 0 relevant articles

Step 2/3: Searching web...
2025-12-29 16:39:00,549 - tools.research.web_search - INFO - Using parallel search...
[... 20+ more log lines mixed with progress ...]
```

**Problems:**
- ❌ Verbose logging mixed with user output
- ❌ Basic text-only progress (no visual indicators)
- ❌ No real-time feedback during operations
- ❌ Can't see what tools are doing "under the hood"
- ❌ Hard to distinguish important info from noise

## Target UX (Inspired by Gemini CLI & Cursor)

**Gemini CLI:**
```
⠼ Expand your workspace with additional directories (/directory)... (esc to cancel, 18s)
```
- Animated spinner
- Contextual message
- Time elapsed
- Escape option

**Cursor:**
```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Option 3                                                                   │
└─────────────────────────────────────────────────────────────────────────────┘

  Creating a plan for Option 3: minimal move (safest).

  ⬢ Read, grepped 2 files, 1 grep
    Read tool_registry.py lines 1591-1595
    Grepped "from _|import _" in tool_registry.py
    Read _result_processor.py lines 2-21
```
- Boxed UI with clear boundaries
- Hierarchical tool visualization (⬢ = tool group)
- Indented sub-operations
- Clear phase separation

## Proposed Solution

### 1. Boxed Progress Display

**Visual Design:**
```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Research: what time is it in st. louis, missouri?                          │
└─────────────────────────────────────────────────────────────────────────────┘

  ⬢ Step 1/3: Fetching newsroom articles...
    ⚠ Newsroom unavailable (API 401) - skipping
    ✓ Completed (0.3s)

  ⬢ Step 2/3: Searching web...
    ⬢ Parallel search: "time it st. louis, missouri"
      ✓ Brave Search: 5 results (1.2s)
      ✓ DuckDuckGo: 5 results (1.5s)
    ⬢ Academic sources
      ✓ Scholar: 3 results (2.1s)
      ✓ PubMed: 3 results (2.8s)
    ✓ Merged 9 results (0.1s)

  ⬢ Step 3/3: Synthesizing findings...
    ⬡ Processing... (3.2s)
    ✓ Complete (21.1s total)
```

**Features:**
- ✅ Boxed borders (visual separation)
- ✅ Hierarchical structure (main steps → sub-operations)
- ✅ Status indicators (⬢ pending, ⬡ in-progress, ✓ complete, ✗ error)
- ✅ Time elapsed for each operation
- ✅ No log noise (only user-relevant info)

### 2. Real-Time Progress Updates

**Implementation:**
- Use Rich `Live` display for animated updates
- Show spinner while operations run
- Update status as each step completes
- Display partial results when available

**Example:**
```
  ⬡ Searching web... (1.2s)
    ⬡ Brave Search: fetching... (0.8s)
    ✓ DuckDuckGo: 5 results (1.5s)
    ✓ Brave Search: 5 results (1.2s)  ← Updates in real-time
```

### 3. Tool Execution Visualization

**Show tool calls as tree:**
```
  ⬢ web_search(query="time it st. louis, missouri...")
    ⬢ Parallel search providers
      ⬢ brave_search(query="...")
        ✓ 5 results (1.2s)
      ⬢ duckduckgo_search(query="...")
        ✓ 5 results (1.5s)
    ⬢ academic_search(site="scholar.google.com")
      ✓ 3 results (2.1s)
    ✓ Merged 9 results (0.1s)
```

**Benefits:**
- See what tools are being called
- Understand parallel operations
- Track execution time per tool
- Identify bottlenecks

### 4. Logging Separation

**Current:** Logs go to stdout (mixed with user output)

**Proposed:**
- Logs → `.zorora/logs/` directory (file-based)
- User output → stdout (clean progress only)
- Add `--verbose` flag to show logs in console if needed

**Result:**
- Clean user experience (no log noise)
- Full logs still available for debugging
- Can review logs later if issues occur

## Implementation Plan

### Phase 1: Progress Display System (Week 1)
**Files to modify:**
- `ui/__init__.py` - Add `ProgressDisplay` class and event queue
- `ui/progress_events.py` (new) - Event schema and queue
- `research_workflow.py` - Use new progress system

**New components:**
- `ProgressEvent` dataclass (event schema)
- `ProgressEventQueue` (thread-safe queue)
- `ProgressDisplay` context manager (pure event renderer)
- `BoxedProgress` component (Rich Panel-based)
- `ToolTree` component (hierarchical display)

**Architecture:**
```python
# Event schema (ui/progress_events.py)
@dataclass
class ProgressEvent:
    event_type: str  # "step_start", "step_complete", "tool_call", etc.
    message: str
    parent_id: Optional[str]  # For hierarchical display
    metadata: Dict[str, Any]
    timestamp: float

# ProgressDisplay (ui/__init__.py)
class ProgressDisplay:
    def __init__(self, ui):
        self.ui = ui
        self.event_queue = queue.Queue()  # Thread-safe
        self.render_tree = {}  # Maintains state
        self.live_display = None
    
    def emit(self, event: ProgressEvent):
        """Thread-safe event emission"""
        self.event_queue.put(event)
    
    def _render_loop(self):
        """Main thread only - consumes events and renders"""
        # Ensure no active input session
        if self.ui.prompt_session and self.ui.prompt_session.is_running():
            raise RuntimeError("Cannot display progress during active input")
        
        with Live(...) as live:
            self.live_display = live
            while not self.done:
                # Consume events from queue
                events = self._drain_queue()
                for event in events:
                    self._process_event(event)
                # Update display
                self._update_display()
                time.sleep(0.1)  # Max 10 updates/sec
```

**API:**
```python
with ui.progress("Research workflow") as p:
    p.emit(ProgressEvent("step_start", "Fetching newsroom..."))
    # ... operation ...
    p.emit(ProgressEvent("step_complete", "Found 0 articles"))
    
    p.emit(ProgressEvent("step_start", "Searching web..."))
    p.emit(ProgressEvent("tool_start", "Brave Search", parent_id="web_search"))
    # ... operation ...
    p.emit(ProgressEvent("tool_complete", "5 results", parent_id="web_search"))
```

### Phase 2: Tool Execution Hooks (Week 1-2)
**Files to modify:**
- `tool_executor.py` - Add progress event emission (thread-safe)
- `ui/__init__.py` - Tool visualization handled by event renderer

**Changes:**
- `ToolExecutor.execute()` emits events to queue (no direct Rich calls)
- Events include tool name, arguments (truncated), duration, result size
- `ProgressDisplay` renders tool calls in tree format based on events
- All updates happen via event queue (no worker thread → Rich calls)

**Critical:**
- Tools run in worker threads but only emit events
- Main thread consumes events and renders
- No Rich calls from `ToolExecutor` or tool functions

### Phase 3: Workflow Integration (Week 2)
**Files to modify:**
- `research_workflow.py` - Full integration
- `turn_processor.py` - Code generation progress
- `workflows/develop_workflow.py` - Development progress

**Changes:**
- Replace all `ui.console.print()` with progress system
- Add hierarchical display for multi-step workflows
- Show phase transitions clearly

### Phase 4: Logging Separation (Week 2-3)
**Files to modify:**
- `config.py` - Add logging configuration
- All workflow files - Update log levels

**Changes:**
- Configure logging to write to `.zorora/logs/`
- Change `logger.info()` → `logger.debug()` for verbose ops
- Keep only important milestones as `logger.info()`
- Add `--verbose` CLI flag

### Phase 5: Polish (Week 3-4)
**Features:**
- Collapsible details (expand/collapse verbose info)
- Progress persistence (save for review)
- Estimated time remaining (ETA)
- Keyboard shortcuts for interaction

## Technical Details

### Dependencies
- **Rich**: Already in use ✅
- **prompt_toolkit**: Already in use ✅
- **No new dependencies needed** ✅

### Performance
- Progress updates: < 1ms overhead per operation
- Use threading for non-blocking updates
- Batch updates if needed (max 10/sec)

### Backward Compatibility
- All changes opt-in via config flags
- Existing workflows continue to work
- Can disable progress display for CI/automation

---

## ⚠️ CRITICAL ARCHITECTURAL GUARDRAILS

### Guardrail #1: Screen Ownership Invariant

**THE RULE:**
> **During progress display, prompt_toolkit is NOT active. ProgressDisplay owns stdout exclusively while active.**

**Why this matters:**
- Cursor and Gemini CLI both enforce this strict sequencing
- Interleaving input and progress causes rendering bugs
- Without this, you get the exact class of bugs you just fixed

**Enforcement:**
```
1. Input (prompt_toolkit owns screen) → user submits
2. Progress display (ProgressDisplay owns screen) → exclusive
3. Output (Rich console) → display results
4. Back to input (prompt_toolkit owns screen)
```

**Implementation:**
- `ProgressDisplay` context manager MUST ensure no prompt_toolkit session is active
- Check `ui.prompt_session` state before rendering
- If active, wait for input completion before starting progress
- Never render progress while waiting for user input

**Code pattern:**
```python
def display_progress(self):
    # CRITICAL: Ensure no active input session
    if self.prompt_session and self.prompt_session.is_running():
        raise RuntimeError("Cannot display progress during active input")
    
    # Now safe to own stdout
    with Live(...) as live:
        # Render progress
```

---

### Guardrail #2: Centralized Event Queue

**THE RULE:**
> **Tools emit events to a queue. UI loop consumes events and renders. No direct Rich calls from worker threads.**

**Why this matters:**
- Rich `Live` is NOT thread-safe for concurrent updates
- Direct Rich calls from tool threads cause:
  - Flicker
  - Dropped updates
  - Corrupted render state

**Architecture:**
```
Tool threads → ProgressEvent queue → UI loop → Rich Live display
```

**Event Schema:**
```python
@dataclass
class ProgressEvent:
    event_type: str  # "step_start", "step_complete", "tool_call", etc.
    message: str
    parent_id: Optional[str]  # For hierarchical display
    metadata: Dict[str, Any]  # Tool name, duration, results, etc.
    timestamp: float
```

**Implementation:**
- Single `ProgressEventQueue` (thread-safe queue)
- Tools call `ui.emit_progress_event(event)` (thread-safe)
- `ProgressDisplay` runs in main thread, consumes queue
- Batch updates (max 10/sec) to prevent flicker

**Code pattern:**
```python
# In tool_executor.py (worker thread)
def execute(self, tool_name, arguments):
    self.ui.emit_progress_event(ProgressEvent(
        event_type="tool_start",
        message=f"Running {tool_name}",
        metadata={"tool": tool_name, "args": arguments}
    ))
    # ... execute tool ...
    self.ui.emit_progress_event(ProgressEvent(
        event_type="tool_complete",
        message=f"Completed {tool_name}",
        metadata={"tool": tool_name, "result_size": len(result)}
    ))

# In ui/__init__.py (main thread)
class ProgressDisplay:
    def __init__(self):
        self.event_queue = queue.Queue()
        self.render_tree = {}  # Maintains hierarchical state
    
    def _render_loop(self):
        while not self.done:
            try:
                event = self.event_queue.get(timeout=0.1)
                self._process_event(event)
                self._update_display()
            except queue.Empty:
                self._update_display()  # Refresh even if no new events
```

---

### Guardrail #3: Pure Event Renderer

**THE RULE:**
> **ProgressDisplay is a pure event renderer. It does NOT know about workflows, tools, or make decisions.**

**Why this matters:**
- Keeps `ProgressDisplay` reusable across all workflows
- Prevents coupling between UI and business logic
- Makes testing easier (just emit events)

**What ProgressDisplay DOES:**
- ✅ Consume events from queue
- ✅ Maintain hierarchical tree state
- ✅ Render tree to Rich Live display
- ✅ Handle screen ownership

**What ProgressDisplay DOES NOT:**
- ❌ Know about research workflows
- ❌ Know about tool execution
- ❌ Make routing decisions
- ❌ Format tool-specific messages

**Implementation:**
- Workflows emit semantic events: `step_start`, `tool_call`, `complete`
- `ProgressDisplay` renders based on event type
- Tool-specific formatting happens in workflow layer, not UI layer

**Code pattern:**
```python
# In research_workflow.py
with ui.progress("Research workflow") as p:
    p.emit(ProgressEvent("step_start", "Fetching newsroom..."))
    # ... do work ...
    p.emit(ProgressEvent("step_complete", "Found 0 articles"))

# ProgressDisplay just renders events - doesn't know it's "research"
```

### Configuration
Add to `config.py`:
```python
UI_PROGRESS_ENABLED = True      # Enable/disable progress display
UI_PROGRESS_VERBOSE = False      # Show detailed tool calls by default
UI_PROGRESS_COLLAPSIBLE = True   # Allow expanding/collapsing details
UI_PROGRESS_PERSIST = False      # Save progress events to disk
UI_PROGRESS_SHOW_ETA = True      # Show estimated time remaining
```

## Files to Modify

### Core UI Components
- `ui/__init__.py` - Add progress display classes
- `ui/progress_events.py` (new) - Progress event system

### Workflow Files
- `research_workflow.py` - Research progress
- `turn_processor.py` - Code generation progress
- `workflows/develop_workflow.py` - Development progress
- `tool_executor.py` - Tool execution hooks

### Configuration
- `config.py` - Progress display options
- `main.py` / `repl.py` - Logging configuration

## Success Criteria

### User Experience
- ✅ Users can clearly see what's happening
- ✅ Progress is visually appealing and informative
- ✅ No confusion between logs and user output
- ✅ Real-time feedback during long operations

### Performance
- ✅ Progress display adds < 50ms overhead
- ✅ No noticeable slowdown in workflows

### Developer Experience
- ✅ Easy to add progress to new workflows
- ✅ Consistent API across all workflows
- ✅ Logging still available for debugging

## Example: Complete Before/After

### Before (Current)
```
2025-12-29 16:38:59,271 - turn_processor - INFO - User: what time is it in st. louis, missouri?
2025-12-29 16:38:59,273 - conversation_persistence - INFO - Saved conversation to /Users/shingi/Workbench/zorora/.zorora/conversations/session_2025-12-29_16-35-16.json
2025-12-29 16:38:59,274 - simplified_router - INFO - Routing to research workflow (newsroom + web + synthesis)
2025-12-29 16:38:59,274 - turn_processor - INFO - Routed to workflow: research
2025-12-29 16:38:59,274 - research_workflow - INFO - Starting research workflow for: what time is it in st. louis, missouri?...

Step 1/3: Fetching relevant newsroom articles...
2025-12-29 16:39:00,545 - tools.research.newsroom - WARNING - Newsroom API returned 401
2025-12-29 16:39:00,547 - research_workflow - INFO - Newsroom fetched: 46 chars
  ✓ Found 0 relevant articles

Step 2/3: Searching web...
2025-12-29 16:39:00,549 - research_workflow - INFO - Search keywords: time it st. louis, missouri?
2025-12-29 16:39:00,549 - tools.research.web_search - INFO - Using parallel search (Brave + DuckDuckGo) for: time it st. louis, missouri...
2025-12-29 16:39:00,549 - tools.research.web_search - INFO - Parallel search (raw): time it st. louis, missouri...
2025-12-29 16:39:00,550 - tools.research.web_search - INFO - Brave Search API call: time it st. louis, missouri...
2025-12-29 16:39:00,550 - tools.research.academic_search - INFO - DuckDuckGo search: time it st. louis, missouri... (attempt 1/3)
2025-12-29 16:39:01,303 - tools.research.web_search - INFO - Brave Search returned 5 results for: time it st. louis, missouri...
2025-12-29 16:39:01,306 - tools.research.web_search - INFO - Parallel search: brave returned 5 results
2025-12-29 16:39:01,363 - tools.research.academic_search - INFO - DuckDuckGo returned 5 results for: time it st. louis, missouri...
2025-12-29 16:39:01,366 - tools.research.web_search - INFO - Parallel search: duckduckgo returned 5 results
2025-12-29 16:39:01,367 - tools.research.web_search - INFO - Parallel search: Merged 2 result sets into 9 results
2025-12-29 16:39:01,367 - tools.research.web_search - INFO - Searching academic sources (Scholar + PubMed) for: time it st. louis, missouri...
2025-12-29 16:39:01,367 - tools.research.academic_search - INFO - DuckDuckGo search: site:scholar.google.com time it st. louis, missouri... (attempt 1/3)
2025-12-29 16:39:02,384 - tools.research.academic_search - INFO - Scholar search returned 3 results for: time it st. louis, missouri...
2025-12-29 16:39:02,387 - tools.research.academic_search - INFO - DuckDuckGo search: site:pubmed.ncbi.nlm.nih.gov time it st. louis, missouri... (attempt 1/3)
2025-12-29 16:39:03,569 - tools.research.academic_search - INFO - PubMed search returned 3 results for: time it st. louis, missouri...
2025-12-29 16:39:03,569 - tools.research.web_search - INFO - Merged 6 academic results with 5 web results
2025-12-29 16:39:03,570 - research_workflow - INFO - Web search completed: 5911 chars
  ✓ Found web results

Step 3/3: Synthesizing findings...
  ✓ Research complete

2025-12-29 16:39:20,334 - conversation_persistence - INFO - Saved conversation to /Users/shingi/Workbench/zorora/.zorora/conversations/session_2025-12-29_16-35-16.json
```

### After (Proposed)
```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Research: what time is it in st. louis, missouri?                          │
└─────────────────────────────────────────────────────────────────────────────┘

  ⬢ Step 1/3: Fetching newsroom articles...
    ⚠ Newsroom unavailable (API 401) - skipping
    ✓ Completed (0.3s)

  ⬢ Step 2/3: Searching web...
    ⬢ Parallel search: "time it st. louis, missouri"
      ✓ Brave Search: 5 results (1.2s)
      ✓ DuckDuckGo: 5 results (1.5s)
    ⬢ Academic sources
      ✓ Scholar: 3 results (2.1s)
      ✓ PubMed: 3 results (2.8s)
    ✓ Merged 9 results (0.1s)

  ⬢ Step 3/3: Synthesizing findings...
    ⬡ Processing... (3.2s)
    ✓ Complete (21.1s total)

[Response appears here...]
```

**Improvements:**
- ✅ Clean, boxed UI
- ✅ Hierarchical structure
- ✅ No log noise
- ✅ Clear status indicators
- ✅ Time tracking
- ✅ Visual appeal

## Architectural Decisions (Post-Review)

### ✅ Screen Ownership: Explicit Sequencing
- **Input** → **Progress** → **Output** → **Input**
- No interleaving
- ProgressDisplay checks for active input session before rendering

### ✅ Event-Driven Architecture
- Tools emit events to thread-safe queue
- Main thread consumes and renders
- No Rich calls from worker threads

### ✅ Pure Event Renderer
- ProgressDisplay doesn't know about workflows
- Workflows emit semantic events
- UI renders based on event type

---

## Questions for Review

1. **Visual Design**: Does the boxed UI with hierarchical structure look good?
2. **Information Density**: Too much detail, or just right?
3. **Logging**: Should logs go to file by default, or keep some in console?
4. **Performance**: Is < 50ms overhead acceptable?
5. **Backward Compatibility**: Should progress display be opt-in or default?
6. **Advanced Features**: Which Phase 5 features are most important?
   - Collapsible details?
   - Progress persistence?
   - ETA calculations?
   - Keyboard shortcuts?
7. **Event Schema**: Does the ProgressEvent schema cover all use cases?
8. **Queue Size**: Should we limit queue size to prevent memory issues?

## Next Steps

1. **Review this plan** - Provide feedback on approach
2. **Approve/Modify** - Confirm or suggest changes
3. **Prototype** - Build small prototype for validation
4. **Implement** - Follow phased approach above
5. **Test** - User testing and refinement

---

**Status**: ✅ Architecture validated, guardrails added
**Estimated Implementation**: 3-4 weeks
**Risk Level**: Low (backward compatible, opt-in features, explicit guardrails)

---

## Post-Review Changes Made

Based on architectural review, added:

1. ✅ **Screen Ownership Invariant** - Explicit sequencing rule
2. ✅ **Centralized Event Queue** - Thread-safe event routing
3. ✅ **Pure Event Renderer** - ProgressDisplay doesn't know about workflows
4. ✅ **Event Schema** - Structured ProgressEvent dataclass
5. ✅ **Implementation Patterns** - Code examples showing guardrails

These guardrails prevent the exact class of bugs identified in the review.
