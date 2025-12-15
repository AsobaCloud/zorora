"""Model selector for choosing LLM models for each role."""

from typing import List, Dict, Optional
from pathlib import Path
import re


class ModelSelector:
    """Handle model selection and config file updates."""

    def __init__(self, llm_client, ui, config_path: str = "config.py"):
        self.llm_client = llm_client
        self.ui = ui
        self.config_path = Path(config_path)

    def get_available_models(self) -> List[str]:
        """Fetch available models from LM Studio."""
        try:
            return self.llm_client.list_models()
        except Exception as e:
            self.ui.display_error('error', str(e))
            return []

    def get_current_config(self) -> Dict[str, str]:
        """Read current model configuration from config.py."""
        import config
        return {
            "orchestrator": config.MODEL,
            "codestral": config.SPECIALIZED_MODELS["codestral"]["model"],
            "reasoning": config.SPECIALIZED_MODELS["reasoning"]["model"],
            "search": config.SPECIALIZED_MODELS["search"]["model"],
        }

    def display_models(self, available: List[str], current: Dict[str, str]):
        """Display available models and current selections."""
        from rich.table import Table
        from rich.panel import Panel

        # Current configuration panel
        config_text = "\n".join([
            f"[cyan]Orchestrator:[/cyan] {current['orchestrator']}",
            f"[cyan]Code Generation:[/cyan] {current['codestral']}",
            f"[cyan]Reasoning/Planning:[/cyan] {current['reasoning']}",
            f"[cyan]Search/Research:[/cyan] {current['search']}",
        ])
        self.ui.console.print(Panel(config_text, title="Current Configuration", border_style="blue"))

        # Available models table
        table = Table(title="Available Models in LM Studio", show_header=True, header_style="bold magenta")
        table.add_column("#", style="dim", width=4)
        table.add_column("Model ID", style="cyan")

        for idx, model in enumerate(available, 1):
            table.add_row(str(idx), model)

        self.ui.console.print(table)

    def select_model(self, role: str, available: List[str], current: str) -> Optional[str]:
        """Interactive model selection for a specific role."""
        self.ui.console.print(f"\n[bold]Select model for {role}[/bold]")
        self.ui.console.print(f"[dim]Current: {current}[/dim]")
        self.ui.console.print("[dim]Enter number to select, or press Enter to keep current:[/dim]")

        choice = input(">>> ").strip()

        if not choice:
            return None  # Keep current

        try:
            idx = int(choice) - 1
            if 0 <= idx < len(available):
                return available[idx]
            else:
                self.ui.console.print("[red]Invalid selection. Keeping current.[/red]")
                return None
        except ValueError:
            self.ui.console.print("[red]Invalid input. Keeping current.[/red]")
            return None

    def update_config_file(self, updates: Dict[str, str]) -> bool:
        """Update config.py with new model selections."""
        try:
            content = self.config_path.read_text()

            # Update orchestrator model
            if "orchestrator" in updates:
                content = re.sub(
                    r'MODEL = "[^"]*"',
                    f'MODEL = "{updates["orchestrator"]}"',
                    content
                )

            # Update specialized models
            for role in ["codestral", "reasoning", "search"]:
                if role in updates:
                    # Find the role's config block and update the model line
                    pattern = rf'"{role}":\s*\{{\s*"model":\s*"[^"]*"'
                    replacement = f'"{role}": {{\n        "model": "{updates[role]}"'
                    content = re.sub(pattern, replacement, content)

            self.config_path.write_text(content)
            return True

        except Exception as e:
            self.ui.display_error('error', f"Failed to update config: {e}")
            return False

    def run(self):
        """Run the model selector interface."""
        self.ui.console.print("\n[bold cyan]═══ Model Selector ═══[/bold cyan]\n")

        # Get available models
        available = self.get_available_models()
        if not available:
            self.ui.console.print("[red]No models available from LM Studio.[/red]")
            return

        # Get current configuration
        current = self.get_current_config()

        # Display current state
        self.display_models(available, current)

        # Collect updates
        updates = {}

        roles = [
            ("orchestrator", "Main Orchestrator"),
            ("codestral", "Code Generation"),
            ("reasoning", "Reasoning/Planning"),
            ("search", "Search/Research"),
        ]

        for role_key, role_name in roles:
            new_model = self.select_model(role_name, available, current[role_key])
            if new_model:
                updates[role_key] = new_model

        # Apply updates
        if updates:
            self.ui.console.print("\n[bold]Applying updates...[/bold]")
            if self.update_config_file(updates):
                self.ui.console.print("[green]✓ Configuration updated successfully![/green]")
                self.ui.console.print("[yellow]⚠ Restart required for changes to take effect.[/yellow]")
            else:
                self.ui.console.print("[red]✗ Failed to update configuration.[/red]")
        else:
            self.ui.console.print("\n[dim]No changes made.[/dim]")
