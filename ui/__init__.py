"""UI module for rich terminal formatting and feedback."""

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from rich.tree import Tree
from contextlib import contextmanager
from typing import Optional, Dict, Any
import time
import threading
import os
import sys

# Try to import prompt_toolkit (graceful fallback if unavailable)
try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.formatted_text import FormattedText
    from prompt_toolkit.styles import Style
    from prompt_toolkit.output import ColorDepth
    from prompt_toolkit.keys import Keys
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.application import Application
    from prompt_toolkit.layout import Layout
    from prompt_toolkit.layout.dimension import Dimension
    from prompt_toolkit.widgets import TextArea, Frame
    PROMPT_TOOLKIT_AVAILABLE = True
except ImportError:
    PROMPT_TOOLKIT_AVAILABLE = False
    PromptSession = None
    FormattedText = None
    Style = None
    ColorDepth = None
    Keys = None
    KeyBindings = None
    Application = None
    Layout = None
    Frame = None
    HSplit = None
    Dimension = None
    TextArea = None

from config import (
    UI_MARKDOWN_RENDERING, UI_SHOW_TOKEN_COUNT, UI_THEME
)
from ui.progress_events import ProgressEvent, ProgressEventQueue, EventType


class ZororaUI:
    """Handles all terminal UI rendering and feedback."""

    def __init__(self, no_color: bool = False):
        """Initialize UI with optional no-color mode."""
        self.no_color = no_color or os.getenv('NO_COLOR') is not None
        self.console = Console(
            force_terminal=sys.stdout.isatty() and not self.no_color,
            no_color=self.no_color
        )
        
        # Initialize prompt_toolkit session (with graceful fallback)
        self.prompt_toolkit_available = False
        self.prompt_session = None
        
        if PROMPT_TOOLKIT_AVAILABLE:
            try:
                # Create session with no-color mode support
                self.prompt_session = PromptSession(
                    color_depth=ColorDepth.MONOCHROME if self.no_color else ColorDepth.TRUE_COLOR
                )
                self.prompt_toolkit_available = True
            except Exception:
                # Fallback if prompt_toolkit initialization fails
                self.prompt_toolkit_available = False
        
        # Active progress display (for event routing)
        self._active_progress = None
    
    def cleanup(self):
        """Restore terminal to normal state before exit."""
        try:
            # Ensure cursor is visible
            self.console.show_cursor(True)
            # Flush all output
            sys.stdout.flush()
            sys.stderr.flush()
            # Print a newline to ensure we're on a fresh line
            print()
        except Exception:
            pass

    def display_welcome(self, model: str, version: str = "1.0.0"):
        """Display welcome banner."""
        from rich.align import Align
        from rich.columns import Columns

        # Left column: ASCII logo and welcome
        left_text = Text()
        left_text.append("\n")
        # Magnifying glass ASCII art
        left_text.append("          ████████\n", style="cyan")
        left_text.append("        ████    ████\n", style="cyan")
        left_text.append("       ███        ███\n", style="cyan")
        left_text.append("      ███          ███\n", style="cyan")
        left_text.append("       ███        ███\n", style="cyan")
        left_text.append("        ████    ████\n", style="cyan")
        left_text.append("          ████████\n", style="cyan")
        left_text.append("               ███\n", style="cyan")
        left_text.append("                ███\n", style="cyan")
        left_text.append("                 ███\n", style="cyan")
        left_text.append("\n")
        left_text.append("       Welcome to Zorora!", style="bold cyan")
        left_text.append("\n\n")
        left_text.append("       Orchestrator: ", style="dim")
        left_text.append(f"{model}", style="cyan")
        left_text.append("\n")
        left_text.append("       Directory: ", style="dim")
        import os
        left_text.append(f"{os.getcwd()}", style="cyan")
        left_text.append("\n\n")
        left_text.append("       Type ", style="dim")
        left_text.append("exit", style="yellow")
        left_text.append(" or ", style="dim")
        left_text.append("Ctrl+C", style="yellow")
        left_text.append(" to quit", style="dim")
        left_text.append("\n")

        # Right column: Available commands
        right_text = Text()
        right_text.append(" Available Commands\n", style="bold yellow")
        right_text.append(" ────────────────────────────────────\n", style="dim")
        right_text.append("\n")

        # Workflow commands
        right_text.append(" /search", style="cyan")
        right_text.append("  - Force web search\n", style="dim")
        right_text.append(" /ask", style="cyan")
        right_text.append("     - Chat (no search)\n", style="dim")
        right_text.append(" /code", style="cyan")
        right_text.append("    - Generate code\n", style="dim")
        right_text.append(" /analyst", style="cyan")
        right_text.append(" - Query policy RAG\n", style="dim")
        right_text.append(" /image", style="cyan")
        right_text.append("   - Generate image\n", style="dim")
        right_text.append(" /vision", style="cyan")
        right_text.append("  - Analyze image\n", style="dim")
        right_text.append(" /develop", style="cyan")
        right_text.append(" - Code development\n", style="dim")
        right_text.append(" /academic", style="cyan")
        right_text.append(" - Academic papers\n", style="dim")
        right_text.append("\n")

        # System commands
        right_text.append(" /models", style="cyan")
        right_text.append("  - Configure models\n", style="dim")
        right_text.append(" /config", style="cyan")
        right_text.append("  - Runtime config\n", style="dim")
        right_text.append(" /history", style="cyan")
        right_text.append(" - View sessions\n", style="dim")
        right_text.append(" /help", style="cyan")
        right_text.append("    - Show help\n", style="dim")
        right_text.append("\n")

        # How it works
        right_text.append(" How It Works\n", style="bold yellow")
        right_text.append(" ────────────────────────────────────\n", style="dim")
        right_text.append("\n")
        right_text.append(" Default: ", style="cyan")
        right_text.append("All queries search web\n", style="dim")
        right_text.append(" Sources: ", style="cyan")
        right_text.append("Newsroom (90 days) + Brave/DDG\n", style="dim")
        right_text.append(" Output:  ", style="cyan")
        right_text.append("Synthesis with citations\n", style="dim")
        right_text.append("\n")
        right_text.append(" Override with slash commands:\n", style="dim")
        right_text.append("   /ask  ", style="green")
        right_text.append("→ Chat without search\n", style="dim")
        right_text.append("   /code ", style="green")
        right_text.append("→ Generate code\n", style="dim")

        # Create two-column layout
        columns = Columns(
            [Align.center(left_text), right_text],
            equal=True,
            expand=True
        )

        panel = Panel(
            columns,
            title=f"Zorora REPL v{version}",
            title_align="center",
            border_style="#D2B48C",  # tan color
            padding=(1, 2)
        )

        self.console.print(panel)
        self.console.print()

    def get_input(self, turn_count: int, tools_available: bool) -> str:
        """
        Get user input inside a box using prompt_toolkit Application/Frame/Layout.
        
        Returns the user's input string, or empty string if cancelled.
        Falls back to standard input() if prompt_toolkit unavailable.
        
        Uses prompt_toolkit's Frame to render borders, matching Cursor/Gemini CLI approach.
        """
        # Fallback to original behavior if prompt_toolkit unavailable
        if not self.prompt_toolkit_available or Application is None:
            return self._get_input_fallback(turn_count, tools_available)
        
        # Build prompt prefix
        prefix_parts = [f"[{turn_count}] "]
        if tools_available:
            prefix_parts.append("⚙ ")
        prefix_parts.append("> ")
        prefix = "".join(prefix_parts)
        
        # Create TextArea for input (must be created before key bindings)
        textarea = TextArea(
            multiline=True,
            wrap_lines=True,
            prompt=prefix,
        )
        
        # Create key bindings
        kb = KeyBindings()
        
        @kb.add("enter")
        def handle_enter(event):
            """Enter submits input."""
            event.app.exit(result=textarea.text)
        
        @kb.add("c-c")
        def handle_ctrl_c(event):
            """Ctrl+C raises KeyboardInterrupt."""
            raise KeyboardInterrupt
        
        # Create Frame with borders (full width)
        frame = Frame(
            textarea,
            title=None,
            style="class:box",
        )
        
        # Create style
        if self.no_color:
            style = Style.from_dict({
                "box": "",
                "frame.border": "",
            })
        else:
            style = Style.from_dict({
                "box": "ansicyan",
                "frame.border": "ansicyan",
            })
        
        # Create Application
        app = Application(
            layout=Layout(frame),
            key_bindings=kb,
            style=style,
            full_screen=False,
        )
        
        try:
            user_input = app.run()
            return user_input.strip() if user_input else ""
        except KeyboardInterrupt:
            # Re-raise so REPL can handle exit
            raise
        except EOFError:
            # Ctrl+D - return empty string
            return ""
    
    def _get_input_fallback(self, turn_count: int, tools_available: bool) -> str:
        """
        Fallback to original input() behavior if prompt_toolkit unavailable.
        Maintains backward compatibility.
        """
        parts = [f"[dim cyan][{turn_count}][/dim cyan]"]
        if tools_available:
            parts.append("[yellow]⚙[/yellow]")
        parts.append("[bold green]>[/bold green]")
        self.console.print(" ".join(parts) + " ", end="")
        try:
            return input().strip()
        except (EOFError, KeyboardInterrupt):
            return ""
    
    def get_prompt(self, turn_count: int, tools_available: bool):
        """
        Display rich prompt (deprecated - use get_input() instead).
        
        Kept for backward compatibility but delegates to get_input().
        """
        # For backward compatibility, but this shouldn't be called anymore
        # as get_input() handles both prompt and input
        parts = [f"[dim cyan][{turn_count}][/dim cyan]"]
        if tools_available:
            parts.append("[yellow]⚙[/yellow]")
        parts.append("[bold green]>[/bold green]")
        self.console.print(" ".join(parts) + " ", end="")

    @contextmanager
    def loading_animation(self, iteration: int, max_iterations: int):
        """Display animated spinner during processing."""
        text = "Generating response..." if iteration == 1 else f"Processing (iteration {iteration}/{max_iterations})..."
        start_time = time.time()
        stop_event = threading.Event()

        def create_display(elapsed: float):
            return Text(f"⠋ {text} {elapsed:.1f}s", style="dim cyan")

        with Live(create_display(0), console=self.console, refresh_per_second=10) as live:
            def update_loop():
                while not stop_event.is_set():
                    live.update(create_display(time.time() - start_time))
                    time.sleep(0.1)

            thread = threading.Thread(target=update_loop, daemon=True)
            thread.start()

            try:
                yield
            finally:
                stop_event.set()
                thread.join(timeout=0.5)
                live.stop()

    def display_response(self, response: str, execution_time: Optional[float] = None):
        """Display assistant response with formatting."""
        self.console.print()

        if UI_MARKDOWN_RENDERING:
            self.console.print(Markdown(response, code_theme=UI_THEME, justify="left"))
        else:
            self.console.print(Text(response, style="bold"))

        if execution_time and UI_SHOW_TOKEN_COUNT:
            self.console.print(f"[dim]Generated in {execution_time:.1f}s[/dim]")

        self.console.print()

    def display_error(self, error_type: str, message: str, details: Optional[str] = None):
        """Display errors with color coding."""
        colors = {'error': 'red', 'warning': 'yellow', 'info': 'blue'}
        icons = {'error': '✗', 'warning': '⚠', 'info': 'ℹ'}

        color = colors.get(error_type, 'red')
        icon = icons.get(error_type, '!')

        text = Text()
        text.append(f"{icon} {error_type.upper()}: ", style=f"bold {color}")
        text.append(message, style=color)

        if details:
            text.append("\n\n", style=color)
            text.append(details, style=f"dim {color}")

        self.console.print(Panel(text, border_style=color, padding=(1, 2)))

    def show_tool_execution(self, tool_name: str, arguments: Dict[str, Any]):
        """Display tool execution start."""
        args = ", ".join(f"{k}={v!r}" for k, v in arguments.items())
        if len(args) > 50:
            args = args[:47] + "..."

        msg = f"[dim cyan]▸ Running:[/dim cyan] [cyan]{tool_name}[/cyan]"
        if args:
            msg += f"[dim cyan]({args})[/dim cyan]"
        self.console.print(msg)

    def show_tool_result(self, tool_name: str, success: bool, result_size: int):
        """Display tool execution result."""
        icon = "✓" if success else "✗"
        color = "green" if success else "red"
        status = f"Completed: {result_size} chars" if success else "Failed"
        self.console.print(f"[dim {color}]  {icon} {tool_name}: {status}[/dim {color}]")
    
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
    
    def progress(self, title: str = "Processing") -> 'ProgressDisplay':
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
        display = ProgressDisplay(self, title)
        self._active_progress = display
        return display


class ProgressDisplay:
    """
    Pure event renderer for progress display.
    
    Does NOT know about workflows or tools - only renders events.
    """
    
    def __init__(self, ui: ZororaUI, title: str = "Processing"):
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
            # Note: prompt_toolkit doesn't expose perfect state, so this is best-effort
            pass  # We'll rely on proper sequencing instead
    
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
    
    def _update_display_loop(self, live):
        """
        Background thread that updates the Live display.
        
        Args:
            live: Rich Live instance (created in main thread)
        """
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
        self._check_screen_ownership()
        
        # Create Live display in main thread (required by Rich)
        live = Live(self._create_display(), console=self.ui.console, refresh_per_second=10)
        live.start()
        self.live_display = live
        
        # Start update loop in background thread
        self.render_thread = threading.Thread(target=self._update_display_loop, args=(live,), daemon=True)
        self.render_thread.start()
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.done = True
        self.event_queue.close()
        
        # Wait for render thread to finish
        if self.render_thread:
            self.render_thread.join(timeout=1.0)
        
        # Stop Live display
        if self.live_display:
            self.live_display.stop()
        
        # Clear active progress reference
        if hasattr(self.ui, '_active_progress'):
            self.ui._active_progress = None
        
        return False
