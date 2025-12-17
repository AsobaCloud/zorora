"""REPL main loop for interactive code assistant."""

from conversation import ConversationManager
from conversation_persistence import ConversationPersistence
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

        # Initialize persistence
        self.persistence = ConversationPersistence()

        # Initialize components
        self.tool_registry = ToolRegistry()
        self.tool_executor = ToolExecutor(self.tool_registry)
        self.llm_client = self._create_orchestrator_client()
        self.conversation = ConversationManager(
            system_prompt=load_system_prompt(),
            persistence=self.persistence,
            auto_save=True
        )
        self.turn_processor = TurnProcessor(
            self.conversation,
            self.llm_client,
            self.tool_executor,
            self.tool_registry,
            ui=self.ui
        )
        self.model_selector = ModelSelector(self.llm_client, self.ui)

    def _create_orchestrator_client(self):
        """Create LLMClient for orchestrator, using local or remote endpoint."""
        # Check if we have endpoint mappings
        endpoint_key = "local"
        if hasattr(config, 'MODEL_ENDPOINTS') and "orchestrator" in config.MODEL_ENDPOINTS:
            endpoint_key = config.MODEL_ENDPOINTS["orchestrator"]

        # If local, use LM Studio
        if endpoint_key == "local":
            return LLMClient()

        # Otherwise, use HF endpoint
        if hasattr(config, 'HF_ENDPOINTS') and endpoint_key in config.HF_ENDPOINTS:
            hf_config = config.HF_ENDPOINTS[endpoint_key]
            return LLMClient(
                api_url=hf_config["url"],
                model=hf_config["model_name"],
                max_tokens=config.MAX_TOKENS,
                timeout=hf_config.get("timeout", config.TIMEOUT),
                temperature=config.TEMPERATURE,
                auth_token=config.HF_TOKEN if hasattr(config, 'HF_TOKEN') else None
            )

        # Fallback to local if endpoint not found
        import logging
        logging.getLogger(__name__).warning(f"Endpoint '{endpoint_key}' not found for orchestrator, falling back to local")
        return LLMClient()

    def _handle_slash_command(self, command: str):
        """Handle slash commands."""
        cmd = command.lower().strip()

        if cmd == "/models":
            self.model_selector.run()
        elif cmd == "/help":
            self._show_help()
        elif cmd == "/clear":
            self._clear_context()
        elif cmd == "/visualize":
            self._visualize_context()
        elif cmd == "/history":
            self._show_history()
        elif cmd.startswith("/resume"):
            # Extract session ID from command
            parts = command.split(maxsplit=1)
            if len(parts) < 2:
                self.ui.console.print("[red]Usage: /resume <session_id>[/red]")
                self.ui.console.print("[dim]Use /history to see available sessions[/dim]")
            else:
                session_id = parts[1].strip()
                self._resume_session(session_id)
        elif cmd.startswith("/save"):
            # Extract filename from command
            parts = command.split(maxsplit=1)
            if len(parts) < 2:
                self.ui.console.print("[red]Usage: /save <filename>[/red]")
                self.ui.console.print("[dim]Example: /save plan.md[/dim]")
            else:
                filename = parts[1].strip()
                self._save_output(filename)
        else:
            self.ui.console.print(f"[red]Unknown command: {command}[/red]")
            self.ui.console.print("[dim]Type /help for available commands[/dim]")

    def _show_help(self):
        """Display help information."""
        help_text = """
[bold cyan]Available Commands:[/bold cyan]

  [cyan]/models[/cyan]                  - Select models for orchestrator and specialist tools
  [cyan]/save <filename>[/cyan]        - Save last specialist output to file (e.g., /save plan.md)
  [cyan]/history[/cyan]                 - List all saved conversation sessions
  [cyan]/resume <session_id>[/cyan]    - Resume a previous conversation session
  [cyan]/clear[/cyan]                   - Clear conversation context (reset to fresh state)
  [cyan]/visualize[/cyan]               - Show context usage statistics
  [cyan]/help[/cyan]                    - Show this help message
  [cyan]exit[/cyan]                     - Exit the REPL
        """
        self.ui.console.print(help_text)

    def _clear_context(self):
        """Clear conversation context."""
        self.conversation.clear()
        self.ui.console.print("[green]✓[/green] Conversation context cleared")

    def _visualize_context(self):
        """Display context usage visualization."""
        stats = self.conversation.get_context_stats()

        # Calculate percentages
        if stats["max_messages"]:
            msg_percent = (stats["message_count"] / stats["max_messages"]) * 100
        else:
            msg_percent = 0

        # Create visualization
        from rich.panel import Panel
        from rich.text import Text

        viz = Text()
        viz.append(f"Messages: {stats['message_count']}", style="cyan")
        if stats["max_messages"]:
            viz.append(f" / {stats['max_messages']}", style="dim")
            viz.append(f" ({msg_percent:.1f}%)\n", style="yellow" if msg_percent > 75 else "green")
        else:
            viz.append(" (unlimited)\n", style="dim")

        viz.append(f"Est. Tokens: ~{stats['estimated_tokens']:,}", style="cyan")

        # Show bar visualization for messages
        if stats["max_messages"]:
            bar_width = 30
            filled = int((stats["message_count"] / stats["max_messages"]) * bar_width)
            bar = "█" * filled + "░" * (bar_width - filled)
            color = "red" if msg_percent > 90 else "yellow" if msg_percent > 75 else "green"
            viz.append(f"\n{bar}", style=color)

        panel = Panel(viz, title="Context Usage", border_style="cyan")
        self.ui.console.print(panel)

    def _save_output(self, filename: str):
        """Save last specialist output to a file."""
        # Check if there's any specialist output to save
        if not self.turn_processor.last_specialist_output:
            self.ui.console.print("[yellow]No specialist output to save.[/yellow]")
            self.ui.console.print("[dim]Run a query that uses a specialist tool first (e.g., ask for analysis, plan, or code).[/dim]")
            return

        # Remove <think></think> tags and their content
        import re
        content = self.turn_processor.last_specialist_output
        # Remove thinking tags (including newlines around them)
        content = re.sub(r'<think>.*?</think>\s*', '', content, flags=re.DOTALL)
        content = content.strip()

        # Write to file
        try:
            with open(filename, 'w') as f:
                f.write(content)

            size = len(content)
            self.ui.console.print(f"[green]✓[/green] Saved {size:,} characters to {filename}")
        except Exception as e:
            self.ui.console.print(f"[red]Error saving file: {e}[/red]")

    def _show_history(self):
        """Display list of saved conversation sessions."""
        from rich.table import Table
        from datetime import datetime

        conversations = self.persistence.list_conversations()

        if not conversations:
            self.ui.console.print("[yellow]No saved conversations found.[/yellow]")
            self.ui.console.print(f"[dim]Conversations are auto-saved to .zorora/conversations/[/dim]")
            return

        # Create table
        table = Table(title="Conversation History", show_header=True, header_style="bold magenta")
        table.add_column("Session ID", style="cyan", no_wrap=True)
        table.add_column("Messages", style="dim", width=8)
        table.add_column("Started", style="dim")
        table.add_column("Preview", style="white")

        for conv in conversations:
            # Format start time
            start_time = conv.get("start_time", "")
            if start_time:
                try:
                    dt = datetime.fromisoformat(start_time)
                    start_display = dt.strftime("%Y-%m-%d %H:%M")
                except:
                    start_display = start_time[:16]
            else:
                start_display = "Unknown"

            # Highlight current session
            session_id = conv["session_id"]
            if session_id == self.conversation.session_id:
                session_id = f"[green]{session_id} (current)[/green]"

            table.add_row(
                session_id,
                str(conv.get("user_message_count", 0)),
                start_display,
                conv.get("preview", "")
            )

        self.ui.console.print(table)
        self.ui.console.print(f"\n[dim]Use [cyan]/resume <session_id>[/cyan] to load a conversation[/dim]")

    def _resume_session(self, session_id: str):
        """Resume a previous conversation session."""
        # Check if trying to resume current session
        if session_id == self.conversation.session_id:
            self.ui.console.print("[yellow]Already in this session.[/yellow]")
            return

        # Try to load the session
        if self.conversation.load_from_session(session_id):
            self.ui.console.print(f"[green]✓[/green] Resumed session: {session_id}")
            stats = self.conversation.get_context_stats()
            self.ui.console.print(f"[dim]Loaded {stats['message_count']} messages[/dim]")
        else:
            self.ui.console.print(f"[red]Failed to resume session: {session_id}[/red]")
            self.ui.console.print("[dim]Use /history to see available sessions[/dim]")

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
                except KeyboardInterrupt:
                    self.ui.console.print("\n\n[yellow]⚠ Query interrupted[/yellow]")
                    turn_count -= 1  # Don't count interrupted turns
                    continue
                except Exception as e:
                    self.ui.display_error('error', str(e))

        except KeyboardInterrupt:
            self.ui.console.print("\n\n[dim]Exiting.[/dim]")
        except Exception as e:
            self.ui.display_error('error', f"Fatal error: {e}")
