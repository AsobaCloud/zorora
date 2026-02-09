"""REPL main loop for interactive code assistant."""

from conversation import ConversationManager
from conversation_persistence import ConversationPersistence
from llm_client import LLMClient
from tool_executor import ToolExecutor
from tools.registry import ToolRegistry
from turn_processor import TurnProcessor
from model_selector import ModelSelector
from engine.repl_command_processor import REPLCommandProcessor
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
        self.command_processor = REPLCommandProcessor(self, RemoteCommand, CommandError, HTTPError)

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
            client.api_url = "https://api.openai.com/v1/chat/completions"
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
            client.api_url = "https://api.anthropic.com/v1/messages"
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
            self.ui.console.print("[red]Error: Command must be instance of RemoteCommand[/red]")
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
        return self.command_processor.handle_workflow_command(command)

    def _handle_slash_command(self, command: str):
        self.command_processor.handle_slash_command(command)

    def _handle_config_command(self):
        self.command_processor.handle_config_command()

    def _show_help(self):
        self.command_processor.show_help()

    def _clear_context(self):
        self.command_processor.clear_context()

    def _visualize_context(self):
        self.command_processor.visualize_context()

    def _save_output(self, filename: str):
        self.command_processor.save_output(filename)

    def _show_history(self):
        self.command_processor.show_history()

    def _resume_session(self, session_id: str):
        self.command_processor.resume_session(session_id)

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

                # Handle slash commands and ml- remote commands
                if user_input.startswith("/") or user_input.lower().startswith("ml-"):
                    # Check if it's a workflow-forcing or remote command
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
