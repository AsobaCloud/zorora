# UX Beautification - Detailed Implementation Spec

## Overview

Transform verbose logging output into clean, boxed progress displays with hierarchical tool visualization. This spec provides exact code, APIs, and file-by-file changes needed for implementation.

---

## Architecture

### Core Components

1. **ProgressEvent** - Event schema (dataclass)
2. **ProgressEventQueue** - Thread-safe event queue
3. **ProgressDisplay** - Pure event renderer (context manager)
4. **ToolExecutor hooks** - Emit events from tool execution

### Critical Invariants

1. **Screen Ownership**: ProgressDisplay runs ONLY when no prompt_toolkit session is active
2. **Event-Driven**: All progress updates go through event queue (no direct Rich calls from threads)
3. **Pure Renderer**: ProgressDisplay doesn't know about workflows/tools, only renders events

---

## File 1: `ui/progress_events.py` (NEW)

**Purpose**: Event schema and queue infrastructure

```python
"""Progress event system for UI updates."""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from enum import Enum
import queue
import time


class EventType(Enum):
    """Progress event types."""
    WORKFLOW_START = "workflow_start"
    WORKFLOW_COMPLETE = "workflow_complete"
    STEP_START = "step_start"
    STEP_COMPLETE = "step_complete"
    STEP_ERROR = "step_error"
    TOOL_START = "tool_start"
    TOOL_COMPLETE = "tool_complete"
    TOOL_ERROR = "tool_error"
    MESSAGE = "message"  # Generic status message


@dataclass
class ProgressEvent:
    """Progress event emitted by workflows and tools."""
    event_type: EventType
    message: str
    parent_id: Optional[str] = None  # For hierarchical display
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    
    def __post_init__(self):
        """Ensure event_type is EventType enum."""
        if isinstance(self.event_type, str):
            self.event_type = EventType(self.event_type)


class ProgressEventQueue:
    """Thread-safe queue for progress events."""
    
    def __init__(self, maxsize: int = 1000):
        """
        Initialize event queue.
        
        Args:
            maxsize: Maximum queue size (prevents memory issues)
        """
        self._queue = queue.Queue(maxsize=maxsize)
        self._closed = False
    
    def put(self, event: ProgressEvent):
        """
        Emit a progress event (thread-safe).
        
        Args:
            event: ProgressEvent to emit
            
        Raises:
            RuntimeError: If queue is closed
        """
        if self._closed:
            raise RuntimeError("ProgressEventQueue is closed")
        try:
            self._queue.put(event, block=False)
        except queue.Full:
            # Drop oldest event if queue full (prevent memory issues)
            try:
                self._queue.get_nowait()
                self._queue.put(event, block=False)
            except queue.Empty:
                pass
    
    def get(self, timeout: float = 0.1) -> Optional[ProgressEvent]:
        """
        Get next event from queue (thread-safe).
        
        Args:
            timeout: Timeout in seconds
            
        Returns:
            ProgressEvent or None if timeout
        """
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def drain(self, max_events: int = 100) -> list[ProgressEvent]:
        """
        Drain multiple events from queue (non-blocking).
        
        Args:
            max_events: Maximum events to drain
            
        Returns:
            List of ProgressEvent objects
        """
        events = []
        for _ in range(max_events):
            event = self.get(timeout=0)
            if event is None:
                break
            events.append(event)
        return events
    
    def close(self):
        """Close queue (no more events accepted)."""
        self._closed = True
    
    def is_closed(self) -> bool:
        """Check if queue is closed."""
        return self._closed
```

---

## File 2: `ui/__init__.py` (MODIFY)

**Changes**: Add ProgressDisplay class and integrate with existing ZororaUI

### Add imports (top of file)

```python
from ui.progress_events import ProgressEvent, ProgressEventQueue, EventType
from rich.live import Live
from rich.panel import Panel
from rich.tree import Tree
from rich.text import Text
from rich.spinner import Spinner
import threading
import time
```

### Add ProgressDisplay class (after ZororaUI class)

```python
class ProgressDisplay:
    """
    Pure event renderer for progress display.
    
    Does NOT know about workflows or tools - only renders events.
    """
    
    def __init__(self, ui: 'ZororaUI', title: str = "Processing"):
        """
        Initialize progress display.
        
        Args:
            ui: ZororaUI instance
            title: Display title
        """
        self.ui = ui
        self.title = title
        self.event_queue = ProgressEventQueue()
        self.render_tree: Dict[str, Dict[str, Any]] = {}  # node_id -> {status, message, children, start_time}
        self.root_id = "root"
        self.done = False
        self.live_display = None
        self.render_thread = None
        self.start_time = time.time()
        
        # Initialize root node
        self.render_tree[self.root_id] = {
            "status": "pending",
            "message": title,
            "children": [],
            "start_time": self.start_time,
            "metadata": {}
        }
    
    def emit(self, event: ProgressEvent):
        """
        Emit a progress event (thread-safe).
        
        Args:
            event: ProgressEvent to emit
        """
        self.event_queue.put(event)
    
    def _check_screen_ownership(self):
        """
        Ensure no active input session (CRITICAL INVARIANT).
        
        Raises:
            RuntimeError: If prompt_toolkit session is active
        """
        if self.ui.prompt_session and hasattr(self.ui.prompt_session, 'is_running'):
            # Check if prompt_toolkit session is active
            # This is a safety check - should never happen if used correctly
            raise RuntimeError(
                "Cannot display progress during active input session. "
                "Ensure input is complete before starting progress display."
            )
    
    def _process_event(self, event: ProgressEvent):
        """
        Process a single event and update render tree.
        
        Args:
            event: ProgressEvent to process
        """
        node_id = event.metadata.get("node_id") or f"node_{len(self.render_tree)}"
        parent_id = event.parent_id or self.root_id
        
        if event.event_type == EventType.WORKFLOW_START:
            self.render_tree[self.root_id]["status"] = "in_progress"
            self.render_tree[self.root_id]["message"] = event.message
            self.render_tree[self.root_id]["start_time"] = event.timestamp
        
        elif event.event_type == EventType.WORKFLOW_COMPLETE:
            self.render_tree[self.root_id]["status"] = "complete"
            self.render_tree[self.root_id]["message"] = event.message
            self.done = True
        
        elif event.event_type == EventType.STEP_START:
            if node_id not in self.render_tree:
                self.render_tree[node_id] = {
                    "status": "in_progress",
                    "message": event.message,
                    "children": [],
                    "start_time": event.timestamp,
                    "metadata": event.metadata
                }
                if parent_id in self.render_tree:
                    self.render_tree[parent_id]["children"].append(node_id)
            else:
                self.render_tree[node_id]["status"] = "in_progress"
                self.render_tree[node_id]["message"] = event.message
                self.render_tree[node_id]["start_time"] = event.timestamp
        
        elif event.event_type == EventType.STEP_COMPLETE:
            if node_id in self.render_tree:
                self.render_tree[node_id]["status"] = "complete"
                self.render_tree[node_id]["message"] = event.message
                if "duration" not in self.render_tree[node_id]:
                    duration = event.timestamp - self.render_tree[node_id]["start_time"]
                    self.render_tree[node_id]["duration"] = duration
        
        elif event.event_type == EventType.STEP_ERROR:
            if node_id in self.render_tree:
                self.render_tree[node_id]["status"] = "error"
                self.render_tree[node_id]["message"] = event.message
        
        elif event.event_type == EventType.TOOL_START:
            if node_id not in self.render_tree:
                self.render_tree[node_id] = {
                    "status": "in_progress",
                    "message": event.message,
                    "children": [],
                    "start_time": event.timestamp,
                    "metadata": event.metadata
                }
                if parent_id in self.render_tree:
                    self.render_tree[parent_id]["children"].append(node_id)
        
        elif event.event_type == EventType.TOOL_COMPLETE:
            if node_id in self.render_tree:
                self.render_tree[node_id]["status"] = "complete"
                self.render_tree[node_id]["message"] = event.message
                duration = event.timestamp - self.render_tree[node_id]["start_time"]
                self.render_tree[node_id]["duration"] = duration
        
        elif event.event_type == EventType.TOOL_ERROR:
            if node_id in self.render_tree:
                self.render_tree[node_id]["status"] = "error"
                self.render_tree[node_id]["message"] = event.message
        
        elif event.event_type == EventType.MESSAGE:
            # Add as child of parent
            if parent_id in self.render_tree:
                self.render_tree[parent_id]["children"].append(node_id)
                self.render_tree[node_id] = {
                    "status": "info",
                    "message": event.message,
                    "children": [],
                    "start_time": event.timestamp,
                    "metadata": event.metadata
                }
    
    def _render_node(self, node_id: str, tree: Tree, visited: set) -> Tree:
        """
        Recursively render a node and its children.
        
        Args:
            node_id: Node ID to render
            tree: Rich Tree to add to
            visited: Set of visited node IDs (prevent cycles)
            
        Returns:
            Tree with node added
        """
        if node_id in visited:
            return tree
        visited.add(node_id)
        
        if node_id not in self.render_tree:
            return tree
        
        node_data = self.render_tree[node_id]
        status = node_data["status"]
        message = node_data["message"]
        duration = node_data.get("duration")
        
        # Status indicators
        if status == "pending":
            icon = "⬢"
            style = "dim cyan"
        elif status == "in_progress":
            icon = "⬡"
            style = "cyan"
        elif status == "complete":
            icon = "✓"
            style = "green"
        elif status == "error":
            icon = "✗"
            style = "red"
        else:
            icon = "•"
            style = "dim"
        
        # Build message with duration
        display_message = f"{icon} {message}"
        if duration is not None:
            display_message += f" ({duration:.1f}s)"
        
        # Add node to tree
        branch = tree.add(Text(display_message, style=style))
        
        # Render children
        for child_id in node_data["children"]:
            self._render_node(child_id, branch, visited)
        
        return tree
    
    def _create_display(self) -> Panel:
        """
        Create Rich Panel with current progress state.
        
        Returns:
            Rich Panel to display
        """
        # Build tree
        tree = Tree("")
        visited = set()
        self._render_node(self.root_id, tree, visited)
        
        # Calculate total elapsed time
        elapsed = time.time() - self.start_time
        
        # Create panel
        title = f"{self.title} ({elapsed:.1f}s)"
        panel = Panel(
            tree,
            title=title,
            border_style="cyan",
            padding=(1, 2)
        )
        
        return panel
    
    def _render_loop(self):
        """
        Main rendering loop (runs in main thread).
        
        Consumes events from queue and updates display.
        """
        self._check_screen_ownership()
        
        with Live(self._create_display(), console=self.ui.console, refresh_per_second=10) as live:
            self.live_display = live
            
            while not self.done:
                # Drain events from queue
                events = self.event_queue.drain(max_events=100)
                for event in events:
                    self._process_event(event)
                
                # Update display
                live.update(self._create_display())
                
                # Small sleep to prevent CPU spinning
                time.sleep(0.1)
            
            # Final update
            live.update(self._create_display())
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.done = True
        self.event_queue.close()
        
        # Wait for render loop to finish
        if self.live_display:
            time.sleep(0.2)  # Allow final render
        
        return False
```

### Add progress() method to ZororaUI class

```python
def progress(self, title: str = "Processing") -> ProgressDisplay:
    """
    Create a progress display context manager.
    
    Args:
        title: Display title
        
    Returns:
        ProgressDisplay context manager
        
    Example:
        with ui.progress("Research workflow") as p:
            p.emit(ProgressEvent(EventType.STEP_START, "Fetching..."))
    """
    return ProgressDisplay(self, title)
```

---

## File 3: `tool_executor.py` (MODIFY)

**Changes**: Add progress event emission to tool execution

### Add imports (top of file)

```python
from ui.progress_events import ProgressEvent, EventType
import uuid
```

### Modify execute() method

**Find this method:**
```python
def execute(self, tool_name: str, arguments: Dict[str, Any]) -> str:
```

**Add at the start of method (after tool_func check):**
```python
# Generate unique node ID for this tool execution
tool_node_id = f"tool_{uuid.uuid4().hex[:8]}"

# Emit tool start event
if self.ui:
    self.ui.emit_progress_event(ProgressEvent(
        event_type=EventType.TOOL_START,
        message=f"Running {tool_name}",
        parent_id=None,  # Will be set by workflow
        metadata={
            "node_id": tool_node_id,
            "tool": tool_name,
            "arguments": {k: str(v)[:50] for k, v in arguments.items()}  # Truncate args
        }
    ))
```

**Add before return statement:**
```python
# Emit tool complete event
if self.ui:
    result_size = len(result) if isinstance(result, str) else 0
    self.ui.emit_progress_event(ProgressEvent(
        event_type=EventType.TOOL_COMPLETE,
        message=f"Completed {tool_name}",
        parent_id=None,
        metadata={
            "node_id": tool_node_id,
            "tool": tool_name,
            "result_size": result_size,
            "success": not result.startswith("Error:") if isinstance(result, str) else True
        }
    ))
```

**Add error handling:**
```python
except Exception as e:
    # Emit tool error event
    if self.ui:
        self.ui.emit_progress_event(ProgressEvent(
            event_type=EventType.TOOL_ERROR,
            message=f"Error in {tool_name}: {str(e)[:100]}",
            parent_id=None,
            metadata={
                "node_id": tool_node_id,
                "tool": tool_name,
                "error": str(e)
            }
        ))
    return f"Error executing tool '{tool_name}': {e}"
```

### Add emit_progress_event() method to ZororaUI

**In `ui/__init__.py`, add to ZororaUI class:**
```python
def emit_progress_event(self, event: ProgressEvent):
    """
    Emit a progress event (thread-safe).
    
    This is a convenience method that routes events to the active
    ProgressDisplay if one exists, or ignores if none.
    
    Args:
        event: ProgressEvent to emit
    """
    # Store reference to active progress display
    # This is set when progress() context manager is entered
    if hasattr(self, '_active_progress') and self._active_progress:
        self._active_progress.emit(event)
```

**Modify progress() method to set active reference:**
```python
def progress(self, title: str = "Processing") -> ProgressDisplay:
    """
    Create a progress display context manager.
    
    Args:
        title: Display title
        
    Returns:
        ProgressDisplay context manager
    """
    display = ProgressDisplay(self, title)
    self._active_progress = display
    return display
```

**Add cleanup in ProgressDisplay.__exit__:**
```python
def __exit__(self, exc_type, exc_val, exc_tb):
    """Context manager exit."""
    self.done = True
    self.event_queue.close()
    
    # Clear active progress reference
    if hasattr(self.ui, '_active_progress'):
        self.ui._active_progress = None
    
    # Wait for render loop to finish
    if self.live_display:
        time.sleep(0.2)  # Allow final render
    
    return False
```

---

## File 4: `research_workflow.py` (MODIFY)

**Changes**: Replace console.print() with progress events

### Add imports (top of file)

```python
from ui.progress_events import ProgressEvent, EventType
import uuid
```

### Modify execute() method

**Find this section:**
```python
def execute(self, query: str, ui=None) -> str:
    logger.info(f"Starting research workflow for: {query[:80]}...")
    
    sources: List[Tuple[str, str]] = []
    
    # Step 1: Try newsroom (with query filtering)
    if ui:
        ui.console.print("\n[cyan]Step 1/3:[/cyan] Fetching relevant newsroom articles...")
    
    newsroom_result = self._fetch_newsroom(query)
    if newsroom_result:
        sources.append(("Newsroom", newsroom_result))
        if ui:
            ui.console.print(f"[green]  ✓ Found {self._count_articles(newsroom_result)} relevant articles[/green]")
    else:
        if ui:
            ui.console.print("[yellow]  ⚠ Newsroom unavailable, skipping[/yellow]")
        logger.warning("Newsroom fetch failed, continuing with web only")
    
    # Step 2: Web search (always)
    if ui:
        ui.console.print("\n[cyan]Step 2/3:[/cyan] Searching web...")
    
    search_query = self._extract_search_keywords(query)
    web_result = self._fetch_web(search_query)
    
    if web_result and not web_result.startswith("Error:"):
        sources.append(("Web", web_result))
        if ui:
            ui.console.print(f"[green]  ✓ Found web results[/green]")
    else:
        if ui:
            ui.console.print("[red]  ✗ Web search failed[/red]")
        logger.error(f"Web search failed: {web_result}")
    
    # Step 3: Synthesize
    if not sources:
        return "Error: Could not fetch any sources. Please check newsroom and web search availability."
    
    if ui:
        ui.console.print("\n[cyan]Step 3/3:[/cyan] Synthesizing findings...")
    
    result = self._synthesize(query, sources)
    
    if ui:
        ui.console.print("[green]  ✓ Research complete[/green]\n")
    
    return result
```

**Replace with:**
```python
def execute(self, query: str, ui=None) -> str:
    logger.info(f"Starting research workflow for: {query[:80]}...")
    
    # Generate workflow node ID
    workflow_id = f"workflow_{uuid.uuid4().hex[:8]}"
    
    # Start progress display
    if ui:
        with ui.progress(f"Research: {query[:60]}...") as progress:
            # Emit workflow start
            progress.emit(ProgressEvent(
                event_type=EventType.WORKFLOW_START,
                message=f"Research: {query[:60]}...",
                metadata={"workflow_id": workflow_id, "query": query}
            ))
            
            sources: List[Tuple[str, str]] = []
            
            # Step 1: Try newsroom
            step1_id = f"step1_{uuid.uuid4().hex[:8]}"
            progress.emit(ProgressEvent(
                event_type=EventType.STEP_START,
                message="Step 1/3: Fetching newsroom articles...",
                parent_id=workflow_id,
                metadata={"node_id": step1_id, "step": 1}
            ))
            
            newsroom_result = self._fetch_newsroom(query)
            if newsroom_result:
                sources.append(("Newsroom", newsroom_result))
                article_count = self._count_articles(newsroom_result)
                progress.emit(ProgressEvent(
                    event_type=EventType.STEP_COMPLETE,
                    message=f"Found {article_count} relevant articles",
                    parent_id=workflow_id,
                    metadata={"node_id": step1_id, "article_count": article_count}
                ))
            else:
                progress.emit(ProgressEvent(
                    event_type=EventType.STEP_ERROR,
                    message="Newsroom unavailable (API 401) - skipping",
                    parent_id=workflow_id,
                    metadata={"node_id": step1_id}
                ))
                logger.warning("Newsroom fetch failed, continuing with web only")
            
            # Step 2: Web search
            step2_id = f"step2_{uuid.uuid4().hex[:8]}"
            progress.emit(ProgressEvent(
                event_type=EventType.STEP_START,
                message="Step 2/3: Searching web...",
                parent_id=workflow_id,
                metadata={"node_id": step2_id, "step": 2}
            ))
            
            search_query = self._extract_search_keywords(query)
            web_result = self._fetch_web(search_query)
            
            if web_result and not web_result.startswith("Error:"):
                sources.append(("Web", web_result))
                progress.emit(ProgressEvent(
                    event_type=EventType.STEP_COMPLETE,
                    message="Found web results",
                    parent_id=workflow_id,
                    metadata={"node_id": step2_id}
                ))
            else:
                progress.emit(ProgressEvent(
                    event_type=EventType.STEP_ERROR,
                    message="Web search failed",
                    parent_id=workflow_id,
                    metadata={"node_id": step2_id}
                ))
                logger.error(f"Web search failed: {web_result}")
            
            # Step 3: Synthesize
            if not sources:
                progress.emit(ProgressEvent(
                    event_type=EventType.WORKFLOW_COMPLETE,
                    message="Error: No sources available",
                    parent_id=None,
                    metadata={"workflow_id": workflow_id, "error": True}
                ))
                return "Error: Could not fetch any sources. Please check newsroom and web search availability."
            
            step3_id = f"step3_{uuid.uuid4().hex[:8]}"
            progress.emit(ProgressEvent(
                event_type=EventType.STEP_START,
                message="Step 3/3: Synthesizing findings...",
                parent_id=workflow_id,
                metadata={"node_id": step3_id, "step": 3}
            ))
            
            result = self._synthesize(query, sources)
            
            progress.emit(ProgressEvent(
                event_type=EventType.STEP_COMPLETE,
                message="Synthesis complete",
                parent_id=workflow_id,
                metadata={"node_id": step3_id}
            ))
            
            progress.emit(ProgressEvent(
                event_type=EventType.WORKFLOW_COMPLETE,
                message="Research complete",
                parent_id=None,
                metadata={"workflow_id": workflow_id}
            ))
            
            return result
    else:
        # No UI - fallback to old behavior
        sources: List[Tuple[str, str]] = []
        newsroom_result = self._fetch_newsroom(query)
        if newsroom_result:
            sources.append(("Newsroom", newsroom_result))
        search_query = self._extract_search_keywords(query)
        web_result = self._fetch_web(search_query)
        if web_result and not web_result.startswith("Error:"):
            sources.append(("Web", web_result))
        if not sources:
            return "Error: Could not fetch any sources."
        result = self._synthesize(query, sources)
        return result
```

---

## File 5: `turn_processor.py` (MODIFY)

**Changes**: Update research workflow call to pass UI

**Find this line:**
```python
if workflow == "research":
    # Multi-source research workflow (newsroom + web + synthesis)
    result = self.research_workflow.execute(user_input, ui=self.ui)
```

**Ensure UI is passed** (should already be correct, but verify)

---

## File 6: `config.py` (MODIFY)

**Add configuration options:**

```python
# Progress display options
UI_PROGRESS_ENABLED = True      # Enable/disable progress display
UI_PROGRESS_VERBOSE = False     # Show detailed tool calls by default
UI_PROGRESS_COLLAPSIBLE = True  # Allow expanding/collapsing details (future)
UI_PROGRESS_PERSIST = False     # Save progress events to disk (future)
UI_PROGRESS_SHOW_ETA = True     # Show estimated time remaining (future)
```

---

## File 7: Logging Configuration (MODIFY)

**Create/modify**: `main.py` or `repl.py` - Add logging configuration

**Add at startup (after imports):**
```python
import logging
from pathlib import Path

# Configure logging to write to file (not stdout)
log_dir = Path.home() / ".zorora" / "logs"
log_dir.mkdir(parents=True, exist_ok=True)

log_file = log_dir / f"zorora_{datetime.now().strftime('%Y%m%d')}.log"

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        # Only add StreamHandler if --verbose flag is set
    ]
)

# If --verbose flag, also log to console
import sys
if '--verbose' in sys.argv or '-v' in sys.argv:
    console_handler = logging.StreamHandler(sys.stderr)  # Use stderr, not stdout
    console_handler.setLevel(logging.INFO)
    logging.getLogger().addHandler(console_handler)
```

---

## Testing Checklist

### Unit Tests

1. **ProgressEvent**
   - [ ] Event creation with all fields
   - [ ] EventType enum conversion
   - [ ] Timestamp auto-generation

2. **ProgressEventQueue**
   - [ ] Thread-safe put/get
   - [ ] Queue full handling (drops oldest)
   - [ ] Close prevents new events
   - [ ] Drain returns multiple events

3. **ProgressDisplay**
   - [ ] Screen ownership check raises error if input active
   - [ ] Event processing updates render tree correctly
   - [ ] Hierarchical rendering works
   - [ ] Status indicators correct (pending/in_progress/complete/error)
   - [ ] Duration calculation accurate

### Integration Tests

1. **Research Workflow**
   - [ ] Progress displays during execution
   - [ ] Events emitted in correct order
   - [ ] Tool events appear in tree
   - [ ] Final state shows complete

2. **Tool Execution**
   - [ ] Tool start/complete events emitted
   - [ ] Error events emitted on failure
   - [ ] Events include correct metadata

3. **Screen Ownership**
   - [ ] Progress cannot start during input
   - [ ] Input cannot start during progress
   - [ ] Clean transition between modes

### Manual Testing

1. **Visual Verification**
   - [ ] Boxed UI displays correctly
   - [ ] Hierarchical tree renders properly
   - [ ] Status indicators visible
   - [ ] Time elapsed updates
   - [ ] No flicker or corruption

2. **Logging Separation**
   - [ ] No log output in console (without --verbose)
   - [ ] Logs written to file
   - [ ] --verbose flag shows logs in stderr

3. **Performance**
   - [ ] No noticeable slowdown
   - [ ] Progress updates smooth
   - [ ] Memory usage reasonable

---

## Implementation Order

1. **Day 1**: Create `ui/progress_events.py` (event schema + queue)
2. **Day 2**: Add `ProgressDisplay` to `ui/__init__.py`
3. **Day 3**: Add tool execution hooks to `tool_executor.py`
4. **Day 4**: Update `research_workflow.py` to use progress events
5. **Day 5**: Configure logging separation
6. **Day 6**: Testing and bug fixes
7. **Day 7**: Polish and documentation

---

## Rollback Plan

If issues arise:

1. **Disable progress display**: Set `UI_PROGRESS_ENABLED = False` in config
2. **Fallback**: Research workflow falls back to old `console.print()` if `ui=None`
3. **No breaking changes**: All changes are additive, existing code still works

---

## Known Limitations

1. **prompt_toolkit integration**: Screen ownership check is best-effort (prompt_toolkit doesn't expose perfect state)
2. **Event queue size**: Limited to 1000 events (prevents memory issues)
3. **Render frequency**: Max 10 updates/sec (prevents flicker)
4. **Thread safety**: Assumes single ProgressDisplay active at a time

---

## Future Enhancements (Out of Scope)

- Collapsible details (expand/collapse)
- Progress persistence (save to disk)
- ETA calculations
- Keyboard shortcuts
- Multiple concurrent progress displays

---

**Status**: Ready for implementation
**Estimated Time**: 1 week
**Risk**: Low (backward compatible, opt-in)
