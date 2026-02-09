"""Command and workflow dispatch for the REPL."""

from __future__ import annotations

import shlex
import config


class REPLCommandProcessor:
    """Handles slash commands and workflow-forcing commands for REPL."""

    def __init__(self, repl, remote_command_cls=None, command_error_cls=None, http_error_cls=None):
        self.repl = repl
        self.remote_command_cls = remote_command_cls
        self.command_error_cls = command_error_cls
        self.http_error_cls = http_error_cls

    def handle_workflow_command(self, command: str):
        """
        Handle workflow-forcing slash commands and remote commands.

        Returns tuple of (response, execution_time) if handled, None otherwise.
        """
        cmd_lower = command.lower().strip()

        # Check for remote commands first (before slash commands)
        # Remote commands use format: ml-<command> <args> (with or without leading /)
        if cmd_lower.startswith('ml-') or cmd_lower.startswith('/ml-'):
            if self.remote_command_cls is None:
                self.repl.ui.console.print("[red]Error: Remote command support not available[/red]")
                return None

            # Strip leading slash if present
            cmd_to_parse = command.lstrip('/')
            try:
                tokens = shlex.split(cmd_to_parse)
            except ValueError as e:
                self.repl.ui.console.print(f"[red]Invalid command syntax: {e}[/red]")
                return None

            cmd_name = tokens[0] if tokens else cmd_to_parse

            if cmd_name in self.repl.remote_commands:
                remote_cmd = self.repl.remote_commands[cmd_name]
                args = tokens[1:] if len(tokens) > 1 else []
                context = self.repl.get_execution_context()

                try:
                    result = remote_cmd.execute(args, context)
                    self.repl.ui.console.print(result)
                    return (result, 0)
                except Exception as e:
                    if self.command_error_cls is not None and isinstance(e, self.command_error_cls):
                        self.repl.ui.console.print(f"[red]Error: {e.message}[/red]")
                        return None
                    if self.http_error_cls is not None and isinstance(e, self.http_error_cls):
                        self.repl.ui.console.print(f"[red]API Error: {e.message}[/red]")
                        return None
                    raise
            else:
                self.repl.ui.console.print(f"[red]Unknown remote command: {cmd_name}[/red]")
                self.repl.ui.console.print(f"[dim]Available remote commands: {', '.join(self.repl.remote_commands.keys())}[/dim]")
                return None

        # /search <query> - Force research workflow
        if cmd_lower.startswith("/search "):
            query = command[8:].strip()
            if not query:
                self.repl.ui.console.print("[red]Usage: /search <query>[/red]")
                self.repl.ui.console.print("[dim]Example: /search gold vs bitcoin prices[/dim]")
                return None
            self.repl.ui.console.print("[cyan]Forcing research workflow...[/cyan]")
            return self.repl.turn_processor.process(query, forced_workflow="research")

        # /ask <query> - Force conversational response (no search)
        elif cmd_lower.startswith("/ask "):
            query = command[5:].strip()
            if not query:
                self.repl.ui.console.print("[red]Usage: /ask <query>[/red]")
                self.repl.ui.console.print("[dim]Example: /ask can you explain that more simply?[/dim]")
                return None
            self.repl.ui.console.print("[cyan]Using conversational mode (no search)...[/cyan]")
            return self.repl.turn_processor.process(query, forced_workflow="qa")

        # /code <prompt> - Force code generation
        elif cmd_lower.startswith("/code "):
            prompt = command[6:].strip()
            if not prompt:
                self.repl.ui.console.print("[red]Usage: /code <prompt>[/red]")
                self.repl.ui.console.print("[dim]Example: /code write a function to parse JSON[/dim]")
                return None
            self.repl.ui.console.print("[cyan]Forcing code generation...[/cyan]")
            return self.repl.turn_processor.process(prompt, forced_workflow="code")

        # /analyst <query> - Force Nehanda RAG query
        elif cmd_lower.startswith("/analyst "):
            query = command[9:].strip()
            if not query:
                self.repl.ui.console.print("[red]Usage: /analyst <query>[/red]")
                self.repl.ui.console.print("[dim]Example: /analyst FERC Order 2222 requirements[/dim]")
                return None
            self.repl.ui.console.print("[cyan]Querying Nehanda RAG...[/cyan]")
            return self.repl.turn_processor.process(query, forced_workflow="energy")

        # /image <prompt> - Force image generation
        elif cmd_lower.startswith("/image "):
            prompt = command[7:].strip()
            if not prompt:
                self.repl.ui.console.print("[red]Usage: /image <prompt>[/red]")
                self.repl.ui.console.print("[dim]Example: /image a futuristic solar panel installation[/dim]")
                return None
            self.repl.ui.console.print("[cyan]Generating image with FLUX...[/cyan]")
            return self.repl.turn_processor.process(prompt, forced_workflow="image")

        # /vision <path> [task] - Force image analysis
        elif cmd_lower.startswith("/vision "):
            args = command[8:].strip()
            if not args:
                self.repl.ui.console.print("[red]Usage: /vision <image_path> [optional task][/red]")
                self.repl.ui.console.print("[dim]Example: /vision screenshot.png[/dim]")
                self.repl.ui.console.print("[dim]Example: /vision chart.png describe this chart[/dim]")
                return None
            self.repl.ui.console.print("[cyan]Analyzing image with vision model...[/cyan]")
            return self.repl.turn_processor.process(args, forced_workflow="vision")

        # /develop <request> - Multi-step code development workflow
        elif cmd_lower.startswith("/develop "):
            request = command[9:].strip()
            if not request:
                self.repl.ui.console.print("[red]Usage: /develop <development request>[/red]")
                self.repl.ui.console.print("[dim]Example: /develop add a REST API endpoint for user authentication[/dim]")
                self.repl.ui.console.print("[dim]Example: /develop refactor the database connection to use connection pooling[/dim]")
                return None

            import os
            from workflows.develop_workflow import DevelopWorkflow

            self.repl.ui.console.print("[cyan]Starting development workflow...[/cyan]")
            workflow = DevelopWorkflow(
                tool_executor=self.repl.turn_processor.tool_executor,
                llm_client=self.repl.turn_processor.llm_client,
                ui=self.repl.ui,
            )

            result = workflow.execute(request, os.getcwd())
            return (result, 0.0)

        # /academic <query>
        elif cmd_lower.startswith("/academic "):
            query = command[10:].strip()
            if not query:
                self.repl.ui.console.print("[red]Usage: /academic <query>[/red]")
                self.repl.ui.console.print("[dim]Example: /academic machine learning interpretability[/dim]")
                self.repl.ui.console.print("[dim]Example: /academic quantum computing 2024[/dim]")
                return None
            self.repl.ui.console.print("[cyan]Searching academic sources (Scholar, PubMed, CORE, arXiv, bioRxiv, medRxiv, PMC) + Sci-Hub...[/cyan]")
            result = self.repl.tool_executor.execute("academic_search", {"query": query})
            if result:
                self.repl.turn_processor.last_specialist_output = result
                self.repl.turn_processor.recent_tool_outputs.append(("academic_search", result))
                if len(self.repl.turn_processor.recent_tool_outputs) > self.repl.turn_processor.max_context_tools:
                    self.repl.turn_processor.recent_tool_outputs.pop(0)
                self.repl.conversation.add_assistant_message(content=result)
            return (result, 0.0) if result else None

        # /deep <query>
        elif cmd_lower.startswith("/deep "):
            query = command[6:].strip()
            if not query:
                self.repl.ui.console.print("[red]Usage: /deep <query>[/red]")
                self.repl.ui.console.print("[dim]Example: /deep impact of AI on renewable energy markets[/dim]")
                self.repl.ui.console.print("[dim]Example: /deep climate change mitigation strategies 2024[/dim]")
                return None

            self.repl.ui.console.print("[cyan]Starting deep research (academic + web + newsroom + credibility scoring)...[/cyan]")

            import time
            start_time = time.time()

            from engine.deep_research_service import run_deep_research
            from engine.research_engine import ResearchEngine

            state = run_deep_research(query=query, depth=1, max_results_per_source=10)

            result = state.synthesis if state.synthesis else "No synthesis generated."

            if state.sources_checked:
                high_cred = sum(1 for s in state.sources_checked if s.credibility_score and s.credibility_score >= 0.7)
                med_cred = sum(1 for s in state.sources_checked if s.credibility_score and 0.4 <= s.credibility_score < 0.7)
                low_cred = sum(1 for s in state.sources_checked if s.credibility_score and s.credibility_score < 0.4)
                result += f"\n\n---\n**Sources**: {len(state.sources_checked)} total ({high_cred} high, {med_cred} medium, {low_cred} low credibility)"

            try:
                research_engine = ResearchEngine()
                research_id = research_engine.save_research(state)
                result += f"\n**Research ID**: {research_id}"
            except Exception as e:
                self.repl.ui.console.print(f"[yellow]Warning: Could not save research: {e}[/yellow]")

            execution_time = time.time() - start_time

            if result:
                self.repl.turn_processor.last_specialist_output = result
                self.repl.conversation.add_assistant_message(content=result)

            return (result, execution_time) if result else None

        # /digest <days> [topic]
        elif cmd_lower.startswith("/digest "):
            import time
            start_time = time.time()

            args = command[8:].strip()
            parts = args.split(None, 1)

            if not parts:
                self.repl.ui.console.print("[red]Usage: /digest <days> [topic][/red]")
                self.repl.ui.console.print("[dim]Example: /digest 14[/dim]")
                self.repl.ui.console.print("[dim]Example: /digest 7 crude oil[/dim]")
                return None

            try:
                days_back = int(parts[0])
                if days_back <= 0:
                    raise ValueError()
                days_back = min(days_back, 90)
            except ValueError:
                self.repl.ui.console.print("[red]Error: First argument must be a positive number of days[/red]")
                return None

            topic = parts[1] if len(parts) > 1 else None

            if topic:
                self.repl.ui.console.print(f"[cyan]Generating {days_back}-day digest focused on '{topic}'...[/cyan]")
            else:
                self.repl.ui.console.print(f"[cyan]Generating {days_back}-day news digest...[/cyan]")

            from workflows.digest_workflow import DigestWorkflow
            workflow = DigestWorkflow(llm_client=self.repl.llm_client)

            topic_slug = topic.replace(" ", "_")[:20] if topic else ""
            output_path = f"newsroom_digest_{days_back}d{'_' + topic_slug if topic_slug else ''}.md"
            result = workflow.execute(days_back, topic=topic, output_path=output_path)

            execution_time = time.time() - start_time

            if result and not result.startswith("Error:"):
                self.repl.ui.console.print(f"[green]✓ Digest saved to {output_path}[/green]")
                self.repl.conversation.add_assistant_message(content=result)

            return (result, execution_time) if result else None

        return None

    def handle_slash_command(self, command: str):
        """Handle slash commands."""
        cmd = command.lower().strip()

        if cmd == "/models":
            self.repl.model_selector.run()
        elif cmd == "/config":
            self.handle_config_command()
        elif cmd == "/help":
            self.show_help()
        elif cmd == "/clear":
            self.clear_context()
        elif cmd == "/visualize":
            self.visualize_context()
        elif cmd == "/history":
            self.show_history()
        elif cmd.startswith("/resume"):
            try:
                parts = shlex.split(command)
            except ValueError as e:
                self.repl.ui.console.print(f"[red]Invalid command syntax: {e}[/red]")
                return

            if len(parts) < 2:
                self.repl.ui.console.print("[red]Usage: /resume <session_id>[/red]")
                self.repl.ui.console.print("[dim]Use /history to see available sessions[/dim]")
            else:
                session_id = parts[1].strip()
                self.resume_session(session_id)
        elif cmd.startswith("/save"):
            try:
                parts = shlex.split(command)
            except ValueError as e:
                self.repl.ui.console.print(f"[red]Invalid command syntax: {e}[/red]")
                return

            if len(parts) < 2:
                self.repl.ui.console.print("[red]Usage: /save <filename>[/red]")
                self.repl.ui.console.print("[dim]Example: /save plan.md[/dim]")
            else:
                filename = " ".join(parts[1:]).strip()
                self.save_output(filename)
        else:
            self.repl.ui.console.print(f"[red]Unknown command: {command}[/red]")
            self.repl.ui.console.print("[dim]Type /help for available commands[/dim]")

    def handle_config_command(self):
        """Display active runtime configuration (read-only)."""
        from rich.table import Table

        self.repl.ui.console.print("\n")
        table = Table(title="Runtime Configuration (Read-only)", show_header=True, header_style="bold magenta")
        table.add_column("Setting", style="cyan", no_wrap=True)
        table.add_column("Value", style="white")
        table.add_column("Description", style="dim")

        orchestrator_endpoint = config.MODEL_ENDPOINTS.get("orchestrator", "local")
        table.add_row("Routing Mode", "Deterministic", "Pattern-based decision tree via simplified_router.py")
        table.add_row("Default Workflow", "Research", "Non-file/non-code queries route to research workflow")
        table.add_row("Orchestrator Endpoint", str(orchestrator_endpoint), "Active endpoint key for the main REPL model")
        table.add_row("Orchestrator Model", str(config.MODEL), "Model label shown in REPL welcome banner")

        self.repl.ui.console.print(table)
        self.repl.ui.console.print("[dim]Use /models or the web settings modal to change model endpoints.[/dim]")

    def show_help(self):
        """Display help information."""
        help_text = """
[bold cyan]Workflow Commands:[/bold cyan]

  [cyan]/search <query>[/cyan]         - Force research workflow (newsroom + web + synthesis)
  [cyan]/ask <query>[/cyan]            - Force conversational mode (no web search)
  [cyan]/code <prompt>[/cyan]          - Force code generation with Codestral
  [cyan]/academic <query>[/cyan]       - Search academic papers (Scholar, PubMed, CORE, arXiv, bioRxiv, medRxiv, PMC + Sci-Hub)
  [cyan]/deep <query>[/cyan]           - Deep research with credibility scoring (academic + web + newsroom)
  [cyan]/analyst <query>[/cyan]        - Query Nehanda RAG (energy policy documents)
  [cyan]/image <prompt>[/cyan]         - Generate image with FLUX (text-to-image)
  [cyan]/vision <path> [task][/cyan]   - Analyze image with vision model
  [cyan]/develop <request>[/cyan]      - Multi-step code development (explore, plan, execute, lint)
  [cyan]/digest <days> [topic][/cyan] - Generate news trend digest by continent

[bold cyan]System Commands:[/bold cyan]

  [cyan]/models[/cyan]                  - Select models for orchestrator and specialist tools
  [cyan]/config[/cyan]                  - Show runtime configuration
  [cyan]/save <filename>[/cyan]        - Save last specialist output to file
  [cyan]/history[/cyan]                 - List all saved conversation sessions
  [cyan]/resume <session_id>[/cyan]    - Resume a previous conversation session
  [cyan]/clear[/cyan]                   - Clear conversation context
  [cyan]/visualize[/cyan]               - Show context usage statistics
  [cyan]/help[/cyan]                    - Show this help message
  [cyan]exit[/cyan]                     - Exit the REPL
"""
        if self.repl.remote_commands:
            help_text += """
[bold cyan]ONA Platform Commands:[/bold cyan] (Optional - requires ONA integration)

  [cyan]/ml-list-challengers <customer_id>[/cyan]    - List challenger models for a customer
  [cyan]/ml-show-metrics <model_id>[/cyan]           - Show evaluation metrics for a model
  [cyan]/ml-diff <challenger_id> <production_id>[/cyan] - Compare challenger vs production model
  [cyan]/ml-promote <customer_id> <model_id> <reason> [--force][/cyan] - Promote challenger to production
  [cyan]/ml-rollback <customer_id> <reason>[/cyan]  - Rollback production model to previous version
  [cyan]/ml-audit-log <customer_id>[/cyan]           - Get audit log for a customer

[dim]Note: ONA commands require ONA_API_BASE_URL and ONA_API_TOKEN environment variables.
      The leading / is optional (both /ml-list-challengers and ml-list-challengers work).[/dim]
"""
        help_text += """
[dim]Note: By default, all queries trigger web search. Use /ask for follow-ups without search.[/dim]
        """
        self.repl.ui.console.print(help_text)

    def clear_context(self):
        """Clear conversation context."""
        self.repl.conversation.clear()
        self.repl.ui.console.print("[green]✓[/green] Conversation context cleared")

    def visualize_context(self):
        """Display context usage visualization."""
        stats = self.repl.conversation.get_context_stats()

        if stats["max_messages"]:
            msg_percent = (stats["message_count"] / stats["max_messages"]) * 100
        else:
            msg_percent = 0

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

        if stats["max_messages"]:
            bar_width = 30
            filled = int((stats["message_count"] / stats["max_messages"]) * bar_width)
            bar = "█" * filled + "░" * (bar_width - filled)
            color = "red" if msg_percent > 90 else "yellow" if msg_percent > 75 else "green"
            viz.append(f"\n{bar}", style=color)

        panel = Panel(viz, title="Context Usage", border_style="cyan")
        self.repl.ui.console.print(panel)

    def save_output(self, filename: str):
        """Save last specialist output to a file."""
        if not self.repl.turn_processor.last_specialist_output:
            self.repl.ui.console.print("[yellow]No specialist output to save.[/yellow]")
            self.repl.ui.console.print("[dim]Run a query that uses a specialist tool first (e.g., ask for analysis, plan, or code).[/dim]")
            return

        import re

        content = self.repl.turn_processor.last_specialist_output
        content = re.sub(r'<think>.*?</think>\s*', '', content, flags=re.DOTALL)
        content = content.strip()

        try:
            with open(filename, 'w') as f:
                f.write(content)

            size = len(content)
            self.repl.ui.console.print(f"[green]✓[/green] Saved {size:,} characters to {filename}")
        except Exception as e:
            self.repl.ui.console.print(f"[red]Error saving file: {e}[/red]")

    def show_history(self):
        """Display list of saved conversation sessions."""
        from rich.table import Table
        from datetime import datetime

        conversations = self.repl.persistence.list_conversations()

        if not conversations:
            self.repl.ui.console.print("[yellow]No saved conversations found.[/yellow]")
            self.repl.ui.console.print("[dim]Conversations are auto-saved to .zorora/conversations/[/dim]")
            return

        table = Table(title="Conversation History", show_header=True, header_style="bold magenta")
        table.add_column("Session ID", style="cyan", no_wrap=True)
        table.add_column("Messages", style="dim", width=8)
        table.add_column("Started", style="dim")
        table.add_column("Preview", style="white")

        for conv in conversations:
            start_time = conv.get("start_time", "")
            if start_time:
                try:
                    dt = datetime.fromisoformat(start_time)
                    start_display = dt.strftime("%Y-%m-%d %H:%M")
                except Exception:
                    start_display = start_time[:16]
            else:
                start_display = "Unknown"

            session_id = conv["session_id"]
            if session_id == self.repl.conversation.session_id:
                session_id = f"[green]{session_id} (current)[/green]"

            table.add_row(
                session_id,
                str(conv.get("user_message_count", 0)),
                start_display,
                conv.get("preview", ""),
            )

        self.repl.ui.console.print(table)
        self.repl.ui.console.print("\n[dim]Use [cyan]/resume <session_id>[/cyan] to load a conversation[/dim]")

    def resume_session(self, session_id: str):
        """Resume a previous conversation session."""
        if session_id == self.repl.conversation.session_id:
            self.repl.ui.console.print("[yellow]Already in this session.[/yellow]")
            return

        if self.repl.conversation.load_from_session(session_id):
            self.repl.ui.console.print(f"[green]✓[/green] Resumed session: {session_id}")
            stats = self.repl.conversation.get_context_stats()
            self.repl.ui.console.print(f"[dim]Loaded {stats['message_count']} messages[/dim]")
        else:
            self.repl.ui.console.print(f"[red]Failed to resume session: {session_id}[/red]")
            self.repl.ui.console.print("[dim]Use /history to see available sessions[/dim]")
