"""UI module for rich terminal formatting and feedback."""

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from contextlib import contextmanager
from typing import Optional, Dict, Any
import time
import threading
import os
import sys

from config import (
    UI_ENABLED, UI_NO_COLOR, UI_MARKDOWN_RENDERING,
    UI_SPINNER_STYLE, UI_SHOW_TOKEN_COUNT, UI_THEME
)


class ZororaUI:
    """Handles all terminal UI rendering and feedback."""

    def __init__(self, no_color: bool = False):
        """Initialize UI with optional no-color mode."""
        self.no_color = no_color or os.getenv('NO_COLOR') is not None
        self.console = Console(
            force_terminal=sys.stdout.isatty() and not self.no_color,
            no_color=self.no_color
        )

    def display_welcome(self, model: str, version: str = "1.0.0"):
        """Display welcome banner."""
        from rich.align import Align

        welcome_text = Text()
        welcome_text.append("\n")
        welcome_text.append("Model: ", style="dim")
        welcome_text.append(f"{model}", style="cyan")
        welcome_text.append("\n\n")
        welcome_text.append("Type ", style="dim")
        welcome_text.append("exit", style="yellow")
        welcome_text.append(" or ", style="dim")
        welcome_text.append("Ctrl+C", style="yellow")
        welcome_text.append(" to quit.", style="dim")
        welcome_text.append("\n")

        panel = Panel(
            Align.center(welcome_text),
            title=f"Zorora REPL v{version}",
            title_align="center",
            border_style="blue",
            padding=(1, 2)
        )

        self.console.print(panel)
        self.console.print()

    def get_prompt(self, turn_count: int, tools_available: bool):
        """Display rich prompt."""
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
            self.console.print(Markdown(response, code_theme=UI_THEME))
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
