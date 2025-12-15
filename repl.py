"""REPL main loop for interactive code assistant."""

from conversation import ConversationManager
from llm_client import LLMClient
from tool_executor import ToolExecutor
from tool_registry import ToolRegistry
from turn_processor import TurnProcessor
from model_selector import ModelSelector
from config import load_system_prompt
import config
from ui import ZororaUI


class REPL:
    """Read-Eval-Print Loop for Claude Code-like interaction."""

    def __init__(self):
        """Initialize REPL with all required components."""
        # Initialize UI
        self.ui = ZororaUI(no_color=config.UI_NO_COLOR)

        # Initialize components
        self.tool_registry = ToolRegistry()
        self.tool_executor = ToolExecutor(self.tool_registry)
        self.llm_client = LLMClient()
        self.conversation = ConversationManager(load_system_prompt())
        self.turn_processor = TurnProcessor(
            self.conversation,
            self.llm_client,
            self.tool_executor,
            self.tool_registry,
            ui=self.ui
        )
        self.model_selector = ModelSelector(self.llm_client, self.ui)

    def _handle_slash_command(self, command: str):
        """Handle slash commands."""
        cmd = command.lower().strip()

        if cmd == "/models":
            self.model_selector.run()
        elif cmd == "/help":
            self._show_help()
        else:
            self.ui.console.print(f"[red]Unknown command: {command}[/red]")
            self.ui.console.print("[dim]Type /help for available commands[/dim]")

    def _show_help(self):
        """Display help information."""
        help_text = """
[bold cyan]Available Commands:[/bold cyan]

  [cyan]/models[/cyan]  - Select models for orchestrator and specialist tools
  [cyan]/help[/cyan]    - Show this help message
  [cyan]exit[/cyan]     - Exit the REPL
        """
        self.ui.console.print(help_text)

    def run(self):
        """Run the REPL loop."""
        self.ui.display_welcome(model=config.MODEL, version="1.0.0")

        try:
            turn_count = 0
            while True:
                turn_count += 1

                # Display rich prompt
                tools_available = True  # Can be dynamically determined
                self.ui.get_prompt(turn_count, tools_available)
                user_input = input().strip()

                if not user_input:
                    turn_count -= 1  # Don't count empty inputs
                    continue
                if user_input.lower() in ("exit", "quit", "q"):
                    self.ui.console.print("\n[dim]Exiting.[/dim]")
                    break

                # Handle slash commands
                if user_input.startswith("/"):
                    self._handle_slash_command(user_input)
                    turn_count -= 1  # Don't count slash commands
                    continue

                # Determine if tools should be available
                tools_available = self.turn_processor.should_provide_tools(user_input)

                # Process turn
                try:
                    response, execution_time = self.turn_processor.process(user_input, tools_available)
                    self.ui.display_response(response, execution_time)
                except Exception as e:
                    self.ui.display_error('error', str(e))

        except KeyboardInterrupt:
            self.ui.console.print("\n\n[dim]Exiting.[/dim]")
        except Exception as e:
            self.ui.display_error('error', f"Fatal error: {e}")
