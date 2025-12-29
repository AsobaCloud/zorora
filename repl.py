"""REPL main loop for interactive code assistant."""

from conversation import ConversationManager
from conversation_persistence import ConversationPersistence
from llm_client import LLMClient
from tool_executor import ToolExecutor
from tools.registry import ToolRegistry
from turn_processor import TurnProcessor
from model_selector import ModelSelector
from config import load_system_prompt
import config
from ui import ZororaUI

# Import remote command support (optional - may not exist if ONA commands not installed)
try:
    from zorora.remote_command import RemoteCommand, CommandError
    from zorora.http_client import HTTPError
except ImportError:
    # Remote command support not available
    RemoteCommand = None
    CommandError = None
    HTTPError = None


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
        self.tool_executor = ToolExecutor(self.tool_registry, ui=self.ui)
        self.llm_client = self._create_orchestrator_client()
        self.conversation = ConversationManager(
            system_prompt=load_system_prompt(),
            persistence=self.persistence,
            auto_save=True,
            tool_executor=self.tool_executor  # For context summarization
        )
        self.turn_processor = TurnProcessor(
            self.conversation,
            self.llm_client,
            self.tool_executor,
            self.tool_registry,
            ui=self.ui
        )
        self.model_selector = ModelSelector(self.llm_client, self.ui)
        
        # Initialize remote command registry
        self.remote_commands: dict = {}

    def _create_orchestrator_client(self):
        """Create LLMClient for orchestrator, using local, HF, OpenAI, or Anthropic endpoint."""
        import os
        # Check if we have endpoint mappings
        endpoint_key = "local"
        if hasattr(config, 'MODEL_ENDPOINTS') and "orchestrator" in config.MODEL_ENDPOINTS:
            endpoint_key = config.MODEL_ENDPOINTS["orchestrator"]

        # If local, use LM Studio
        if endpoint_key == "local":
            return LLMClient()

        # Check OpenAI endpoints (matches HF pattern)
        if hasattr(config, 'OPENAI_ENDPOINTS') and endpoint_key in config.OPENAI_ENDPOINTS:
            openai_config = config.OPENAI_ENDPOINTS[endpoint_key]
            # Get API key from config or environment variable
            api_key = config.OPENAI_API_KEY if hasattr(config, 'OPENAI_API_KEY') and config.OPENAI_API_KEY else os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError(f"OPENAI_API_KEY not configured for endpoint '{endpoint_key}'. Set it in config.py or OPENAI_API_KEY environment variable.")
            
            # Create LLMClient wrapper for OpenAI (uses OpenAIAdapter internally)
            from providers.openai_adapter import OpenAIAdapter
            adapter = OpenAIAdapter(
                api_key=api_key,
                model=openai_config.get("model", endpoint_key),
                timeout=openai_config.get("timeout", config.TIMEOUT),
            )
            # Wrap adapter in LLMClient-compatible interface
            client = LLMClient.__new__(LLMClient)
            client.adapter = adapter
            client.api_url = f"https://api.openai.com/v1/chat/completions"
            client.model = openai_config.get("model", endpoint_key)
            client.max_tokens = config.MAX_TOKENS
            client.temperature = config.TEMPERATURE
            client.timeout = openai_config.get("timeout", config.TIMEOUT)
            client.tool_choice = config.TOOL_CHOICE
            client.parallel_tool_calls = config.PARALLEL_TOOL_CALLS
            client.auth_token = api_key
            return client

        # Check Anthropic endpoints (matches HF pattern)
        if hasattr(config, 'ANTHROPIC_ENDPOINTS') and endpoint_key in config.ANTHROPIC_ENDPOINTS:
            anthropic_config = config.ANTHROPIC_ENDPOINTS[endpoint_key]
            # Get API key from config or environment variable
            api_key = config.ANTHROPIC_API_KEY if hasattr(config, 'ANTHROPIC_API_KEY') and config.ANTHROPIC_API_KEY else os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError(f"ANTHROPIC_API_KEY not configured for endpoint '{endpoint_key}'. Set it in config.py or ANTHROPIC_API_KEY environment variable.")
            
            # Create LLMClient wrapper for Anthropic (uses AnthropicAdapter internally)
            from providers.anthropic_adapter import AnthropicAdapter
            adapter = AnthropicAdapter(
                api_key=api_key,
                model=anthropic_config.get("model", endpoint_key),
                timeout=anthropic_config.get("timeout", config.TIMEOUT),
            )
            # Wrap adapter in LLMClient-compatible interface
            client = LLMClient.__new__(LLMClient)
            client.adapter = adapter
            client.api_url = f"https://api.anthropic.com/v1/messages"
            client.model = anthropic_config.get("model", endpoint_key)
            client.max_tokens = config.MAX_TOKENS
            client.temperature = config.TEMPERATURE
            client.timeout = anthropic_config.get("timeout", config.TIMEOUT)
            client.tool_choice = config.TOOL_CHOICE
            client.parallel_tool_calls = config.PARALLEL_TOOL_CALLS
            client.auth_token = api_key
            return client

        # Check HF endpoints (existing logic)
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
    
    def register_remote_command(self, command):
        """
        Register a remote command with the REPL.
        
        Args:
            command: RemoteCommand instance to register
        """
        if RemoteCommand is None:
            self.ui.console.print("[yellow]Warning: Remote command support not available[/yellow]")
            return
        
        if not isinstance(command, RemoteCommand):
            self.ui.console.print(f"[red]Error: Command must be instance of RemoteCommand[/red]")
            return
        
        self.remote_commands[command.name] = command
        self.ui.console.print(f"[dim]Registered remote command: {command.name}[/dim]")
    
    def get_execution_context(self):
        """
        Get execution context for remote commands.
        
        Returns:
            Context dict with actor, environment, etc.
        """
        import os
        return {
            'actor': os.getenv('ZORORA_ACTOR', os.getenv('USER', 'zorora-user')),
            'environment': os.getenv('ZORORA_ENV', 'prod'),
            'request_id': f"zorora-{os.getpid()}-{id(self)}"
        }

    def _handle_workflow_command(self, command: str):
        """
        Handle workflow-forcing slash commands and remote commands.

        Returns tuple of (response, execution_time) if handled, None otherwise.
        """
        cmd_lower = command.lower().strip()
        
        # Check for remote commands first (before slash commands)
        # Remote commands use format: ml-<command> <args>
        if cmd_lower.startswith('ml-'):
            if RemoteCommand is None:
                self.ui.console.print("[red]Error: Remote command support not available[/red]")
                return None
            
            parts = command.split(None, 1)
            cmd_name = parts[0] if parts else command
            
            if cmd_name in self.remote_commands:
                remote_cmd = self.remote_commands[cmd_name]
                args = parts[1].split() if len(parts) > 1 else []
                context = self.get_execution_context()
                
                try:
                    result = remote_cmd.execute(args, context)
                    self.ui.console.print(result)
                    return (result, 0)  # No execution time tracking for remote commands
                except CommandError as e:
                    self.ui.console.print(f"[red]Error: {e.message}[/red]")
                    return None
                except HTTPError as e:
                    self.ui.console.print(f"[red]API Error: {e.message}[/red]")
                    return None
            else:
                self.ui.console.print(f"[red]Unknown remote command: {cmd_name}[/red]")
                self.ui.console.print(f"[dim]Available remote commands: {', '.join(self.remote_commands.keys())}[/dim]")
                return None

        # /search <query> - Force research workflow
        if cmd_lower.startswith("/search "):
            query = command[8:].strip()  # Remove "/search "
            if not query:
                self.ui.console.print("[red]Usage: /search <query>[/red]")
                self.ui.console.print("[dim]Example: /search gold vs bitcoin prices[/dim]")
                return None
            self.ui.console.print(f"[cyan]Forcing research workflow...[/cyan]")
            return self.turn_processor.process(query, forced_workflow="research")

        # /ask <query> - Force conversational response (no search)
        elif cmd_lower.startswith("/ask "):
            query = command[5:].strip()  # Remove "/ask "
            if not query:
                self.ui.console.print("[red]Usage: /ask <query>[/red]")
                self.ui.console.print("[dim]Example: /ask can you explain that more simply?[/dim]")
                return None
            self.ui.console.print(f"[cyan]Using conversational mode (no search)...[/cyan]")
            return self.turn_processor.process(query, forced_workflow="qa")

        # /code <prompt> - Force code generation
        elif cmd_lower.startswith("/code "):
            prompt = command[6:].strip()  # Remove "/code "
            if not prompt:
                self.ui.console.print("[red]Usage: /code <prompt>[/red]")
                self.ui.console.print("[dim]Example: /code write a function to parse JSON[/dim]")
                return None
            self.ui.console.print(f"[cyan]Forcing code generation...[/cyan]")
            return self.turn_processor.process(prompt, forced_workflow="code")

        # /analyst <query> - Force EnergyAnalyst RAG query
        elif cmd_lower.startswith("/analyst "):
            query = command[9:].strip()  # Remove "/analyst "
            if not query:
                self.ui.console.print("[red]Usage: /analyst <query>[/red]")
                self.ui.console.print("[dim]Example: /analyst FERC Order 2222 requirements[/dim]")
                return None
            self.ui.console.print(f"[cyan]Querying EnergyAnalyst RAG...[/cyan]")
            return self.turn_processor.process(query, forced_workflow="energy")

        # /image <prompt> - Force image generation
        elif cmd_lower.startswith("/image "):
            prompt = command[7:].strip()  # Remove "/image "
            if not prompt:
                self.ui.console.print("[red]Usage: /image <prompt>[/red]")
                self.ui.console.print("[dim]Example: /image a futuristic solar panel installation[/dim]")
                return None
            self.ui.console.print(f"[cyan]Generating image with FLUX...[/cyan]")
            return self.turn_processor.process(prompt, forced_workflow="image")

        # /vision <path> [task] - Force image analysis
        elif cmd_lower.startswith("/vision "):
            args = command[8:].strip()  # Remove "/vision "
            if not args:
                self.ui.console.print("[red]Usage: /vision <image_path> [optional task][/red]")
                self.ui.console.print("[dim]Example: /vision screenshot.png[/dim]")
                self.ui.console.print("[dim]Example: /vision chart.png describe this chart[/dim]")
                return None
            self.ui.console.print(f"[cyan]Analyzing image with vision model...[/cyan]")
            return self.turn_processor.process(args, forced_workflow="vision")

        # /develop <request> - Multi-step code development workflow
        elif cmd_lower.startswith("/develop "):
            request = command[9:].strip()  # Remove "/develop "
            if not request:
                self.ui.console.print("[red]Usage: /develop <development request>[/red]")
                self.ui.console.print("[dim]Example: /develop add a REST API endpoint for user authentication[/dim]")
                self.ui.console.print("[dim]Example: /develop refactor the database connection to use connection pooling[/dim]")
                return None

            # Import and run develop workflow
            import os
            from workflows.develop_workflow import DevelopWorkflow

            self.ui.console.print(f"[cyan]Starting development workflow...[/cyan]")
            workflow = DevelopWorkflow(
                tool_executor=self.turn_processor.tool_executor,
                llm_client=self.turn_processor.llm_client,
                ui=self.ui
            )

            # Execute workflow (this handles all phases internally)
            result = workflow.execute(request, os.getcwd())

            # Return as tuple for consistency with other commands
            return (result, 0.0)  # Time not tracked separately for multi-phase workflow

        # /academic <query> - Academic paper search with multiple sources + Sci-Hub
        elif cmd_lower.startswith("/academic "):
            query = command[10:].strip()  # Remove "/academic "
            if not query:
                self.ui.console.print("[red]Usage: /academic <query>[/red]")
                self.ui.console.print("[dim]Example: /academic machine learning interpretability[/dim]")
                self.ui.console.print("[dim]Example: /academic quantum computing 2024[/dim]")
                return None
            self.ui.console.print(f"[cyan]Searching academic sources (Scholar, PubMed, CORE, arXiv, bioRxiv, medRxiv, PMC) + Sci-Hub...[/cyan]")
            result = self.tool_executor.execute("academic_search", {"query": query})
            if result:
                # Store result for other tools to access
                self.turn_processor.last_specialist_output = result
                # Add to recent tool outputs for context injection
                self.turn_processor.recent_tool_outputs.append(("academic_search", result))
                # Keep only last N tool outputs
                if len(self.turn_processor.recent_tool_outputs) > self.turn_processor.max_context_tools:
                    self.turn_processor.recent_tool_outputs.pop(0)
                # Add to conversation history
                self.conversation.add_assistant_message(content=result)
            return (result, 0.0) if result else None

        # Not a workflow command
        return None

    def _handle_slash_command(self, command: str):
        """Handle slash commands."""
        cmd = command.lower().strip()

        if cmd == "/models":
            self.model_selector.run()
        elif cmd == "/config":
            self._handle_config_command()
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

    def _handle_config_command(self):
        """Interactive configuration editor for routing settings."""
        from rich.panel import Panel
        from rich.table import Table
        from rich.prompt import Confirm, FloatPrompt

        while True:
            # Display current configuration
            self.ui.console.print("\n")
            table = Table(title="Routing Configuration", show_header=True, header_style="bold magenta")
            table.add_column("Setting", style="cyan", no_wrap=True)
            table.add_column("Value", style="white")
            table.add_column("Description", style="dim")

            # Add rows with current values
            table.add_row(
                "1. USE_JSON_ROUTING",
                f"[green]{config.USE_JSON_ROUTING}[/green]" if config.USE_JSON_ROUTING else f"[red]{config.USE_JSON_ROUTING}[/red]",
                "Use JSON-based routing system"
            )
            table.add_row(
                "2. USE_HEURISTIC_ROUTER",
                f"[green]{config.USE_HEURISTIC_ROUTER}[/green]" if config.USE_HEURISTIC_ROUTER else f"[red]{config.USE_HEURISTIC_ROUTER}[/red]",
                "Enable fast keyword-based routing"
            )
            table.add_row(
                "3. ENABLE_CONFIDENCE_FALLBACK",
                f"[green]{config.ENABLE_CONFIDENCE_FALLBACK}[/green]" if config.ENABLE_CONFIDENCE_FALLBACK else f"[red]{config.ENABLE_CONFIDENCE_FALLBACK}[/red]",
                "Fallback to 8B model for low confidence"
            )
            table.add_row(
                "4. CONFIDENCE_THRESHOLD_HIGH",
                f"[yellow]{config.CONFIDENCE_THRESHOLD_HIGH}[/yellow]",
                "Execute immediately if >= this (0.0-1.0)"
            )
            table.add_row(
                "5. CONFIDENCE_THRESHOLD_LOW",
                f"[yellow]{config.CONFIDENCE_THRESHOLD_LOW}[/yellow]",
                "Fallback to 8B if < this (0.0-1.0)"
            )

            self.ui.console.print(table)
            self.ui.console.print("\n[dim]Enter option number to toggle/edit, 's' to save, or 'q' to quit without saving[/dim]")

            # Get user choice
            choice = input("Choice: ").strip().lower()

            if choice == 'q':
                self.ui.console.print("[yellow]Configuration unchanged[/yellow]")
                break
            elif choice == 's':
                self._save_config_changes()
                self.ui.console.print("[green]✓[/green] Configuration saved!")
                break
            elif choice == '1':
                config.USE_JSON_ROUTING = not config.USE_JSON_ROUTING
                self.ui.console.print(f"[green]✓[/green] USE_JSON_ROUTING set to {config.USE_JSON_ROUTING}")
            elif choice == '2':
                config.USE_HEURISTIC_ROUTER = not config.USE_HEURISTIC_ROUTER
                self.ui.console.print(f"[green]✓[/green] USE_HEURISTIC_ROUTER set to {config.USE_HEURISTIC_ROUTER}")
            elif choice == '3':
                config.ENABLE_CONFIDENCE_FALLBACK = not config.ENABLE_CONFIDENCE_FALLBACK
                self.ui.console.print(f"[green]✓[/green] ENABLE_CONFIDENCE_FALLBACK set to {config.ENABLE_CONFIDENCE_FALLBACK}")
            elif choice == '4':
                try:
                    new_value = FloatPrompt.ask(
                        "Enter new CONFIDENCE_THRESHOLD_HIGH (0.0-1.0)",
                        default=config.CONFIDENCE_THRESHOLD_HIGH,
                        console=self.ui.console
                    )
                    if 0.0 <= new_value <= 1.0:
                        config.CONFIDENCE_THRESHOLD_HIGH = new_value
                        self.ui.console.print(f"[green]✓[/green] CONFIDENCE_THRESHOLD_HIGH set to {new_value}")
                    else:
                        self.ui.console.print("[red]Value must be between 0.0 and 1.0[/red]")
                except Exception as e:
                    self.ui.console.print(f"[red]Invalid input: {e}[/red]")
            elif choice == '5':
                try:
                    new_value = FloatPrompt.ask(
                        "Enter new CONFIDENCE_THRESHOLD_LOW (0.0-1.0)",
                        default=config.CONFIDENCE_THRESHOLD_LOW,
                        console=self.ui.console
                    )
                    if 0.0 <= new_value <= 1.0:
                        config.CONFIDENCE_THRESHOLD_LOW = new_value
                        self.ui.console.print(f"[green]✓[/green] CONFIDENCE_THRESHOLD_LOW set to {new_value}")
                    else:
                        self.ui.console.print("[red]Value must be between 0.0 and 1.0[/red]")
                except Exception as e:
                    self.ui.console.print(f"[red]Invalid input: {e}[/red]")
            else:
                self.ui.console.print("[red]Invalid choice[/red]")

    def _save_config_changes(self):
        """Save configuration changes to config.py."""
        import re
        from pathlib import Path

        config_file = Path(__file__).parent / "config.py"

        try:
            # Read current config file
            with open(config_file, 'r') as f:
                content = f.read()

            # Update routing configuration section
            replacements = {
                r'USE_JSON_ROUTING = \w+': f'USE_JSON_ROUTING = {config.USE_JSON_ROUTING}',
                r'USE_HEURISTIC_ROUTER = \w+': f'USE_HEURISTIC_ROUTER = {config.USE_HEURISTIC_ROUTER}',
                r'ENABLE_CONFIDENCE_FALLBACK = \w+': f'ENABLE_CONFIDENCE_FALLBACK = {config.ENABLE_CONFIDENCE_FALLBACK}',
                r'CONFIDENCE_THRESHOLD_HIGH = [\d.]+': f'CONFIDENCE_THRESHOLD_HIGH = {config.CONFIDENCE_THRESHOLD_HIGH}',
                r'CONFIDENCE_THRESHOLD_LOW = [\d.]+': f'CONFIDENCE_THRESHOLD_LOW = {config.CONFIDENCE_THRESHOLD_LOW}',
            }

            for pattern, replacement in replacements.items():
                content = re.sub(pattern, replacement, content)

            # Write back to file
            with open(config_file, 'w') as f:
                f.write(content)

            return True

        except Exception as e:
            self.ui.console.print(f"[red]Error saving config: {e}[/red]")
            return False

    def _show_help(self):
        """Display help information."""
        help_text = """
[bold cyan]Workflow Commands:[/bold cyan]

  [cyan]/search <query>[/cyan]         - Force research workflow (newsroom + web + synthesis)
  [cyan]/ask <query>[/cyan]            - Force conversational mode (no web search)
  [cyan]/code <prompt>[/cyan]          - Force code generation with Codestral
  [cyan]/academic <query>[/cyan]       - Search academic papers (Scholar, PubMed, CORE, arXiv, bioRxiv, medRxiv, PMC + Sci-Hub)
  [cyan]/analyst <query>[/cyan]        - Query EnergyAnalyst RAG (energy policy documents)
  [cyan]/image <prompt>[/cyan]         - Generate image with FLUX (text-to-image)
  [cyan]/vision <path> [task][/cyan]   - Analyze image with vision model
  [cyan]/develop <request>[/cyan]      - Multi-step code development (explore, plan, execute, lint)

[bold cyan]System Commands:[/bold cyan]

  [cyan]/models[/cyan]                  - Select models for orchestrator and specialist tools
  [cyan]/config[/cyan]                  - Configure routing settings
  [cyan]/save <filename>[/cyan]        - Save last specialist output to file
  [cyan]/history[/cyan]                 - List all saved conversation sessions
  [cyan]/resume <session_id>[/cyan]    - Resume a previous conversation session
  [cyan]/clear[/cyan]                   - Clear conversation context
  [cyan]/visualize[/cyan]               - Show context usage statistics
  [cyan]/help[/cyan]                    - Show this help message
  [cyan]exit[/cyan]                     - Exit the REPL
"""
        # Add ONA Platform Commands section if available
        if self.remote_commands:
            help_text += """
[bold cyan]ONA Platform Commands:[/bold cyan] (Optional - requires ONA integration)

  [cyan]ml-list-challengers <customer_id>[/cyan]     - List challenger models for a customer
  [cyan]ml-show-metrics <model_id>[/cyan]            - Show evaluation metrics for a model
  [cyan]ml-diff <challenger_id> <production_id>[/cyan] - Compare challenger vs production model
  [cyan]ml-promote <customer_id> <model_id> <reason> [--force][/cyan] - Promote challenger to production
  [cyan]ml-rollback <customer_id> <reason>[/cyan]   - Rollback production model to previous version
  [cyan]ml-audit-log <customer_id>[/cyan]            - Get audit log for a customer

[dim]Note: ONA platform commands require ONA_API_BASE_URL and ONA_API_TOKEN environment variables.[/dim]
"""
        help_text += """
[dim]Note: By default, all queries trigger web search. Use /ask for follow-ups without search.[/dim]
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

                # Get user input (with boxed prompt)
                tools_available = True  # Can be dynamically determined
                user_input = self.ui.get_input(turn_count, tools_available)

                if not user_input:
                    turn_count -= 1  # Don't count empty inputs
                    continue
                if user_input.lower() in ("exit", "quit", "q"):
                    self.ui.console.print("\n[dim]Exiting.[/dim]")
                    # Restore terminal state before exit
                    self.ui.cleanup()
                    break

                # Handle slash commands
                if user_input.startswith("/"):
                    # Check if it's a workflow-forcing command
                    workflow_result = self._handle_workflow_command(user_input)
                    if workflow_result is not None:
                        # Workflow command processed - display result
                        response, execution_time = workflow_result
                        self.ui.display_response(response, execution_time)
                    else:
                        # System command (help, models, etc.) - handled internally
                        self._handle_slash_command(user_input)
                        turn_count -= 1  # Don't count system commands
                    continue

                # Process turn
                try:
                    response, execution_time = self.turn_processor.process(user_input)
                    self.ui.display_response(response, execution_time)
                except KeyboardInterrupt:
                    self.ui.console.print("\n\n[yellow]⚠ Query interrupted[/yellow]")
                    turn_count -= 1  # Don't count interrupted turns
                    continue
                except Exception as e:
                    self.ui.display_error('error', str(e))

        except KeyboardInterrupt:
            self.ui.console.print("\n\n[dim]Exiting.[/dim]")
            # Restore terminal state before exit
            self.ui.cleanup()
        except Exception as e:
            self.ui.display_error('error', f"Fatal error: {e}")
