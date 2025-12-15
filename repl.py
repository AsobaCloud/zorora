"""REPL main loop for interactive code assistant."""

from conversation import ConversationManager
from llm_client import LLMClient
from tool_executor import ToolExecutor
from tool_registry import ToolRegistry
from turn_processor import TurnProcessor
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
