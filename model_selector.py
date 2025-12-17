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

    def get_available_models(self) -> List[Dict[str, str]]:
        """
        Fetch available models from LM Studio and HF endpoints.

        Returns:
            List of dicts with 'name' and 'origin' keys
        """
        models = []

        # Fetch from LM Studio (local)
        try:
            local_models = self.llm_client.list_models()
            for model in local_models:
                models.append({"name": model, "origin": "Local (LM Studio)"})
        except Exception as e:
            self.ui.console.print(f"[yellow]Warning: Could not fetch LM Studio models: {e}[/yellow]")

        # Fetch from HF endpoints
        import config
        if hasattr(config, 'HF_ENDPOINTS') and hasattr(config, 'HF_TOKEN'):
            for endpoint_key, endpoint_config in config.HF_ENDPOINTS.items():
                if not endpoint_config.get("enabled", True):
                    continue

                try:
                    from llm_client import LLMClient
                    hf_client = LLMClient(
                        api_url=endpoint_config["url"],
                        model=endpoint_config["model_name"],
                        auth_token=config.HF_TOKEN
                    )
                    # For HF endpoints, just add the configured model
                    # (HF endpoints typically serve a single model, not a list)
                    models.append({
                        "name": endpoint_config["model_name"],
                        "origin": f"HF: {endpoint_key}"
                    })
                except Exception as e:
                    self.ui.console.print(f"[yellow]Warning: Could not connect to HF endpoint '{endpoint_key}': {e}[/yellow]")

        return models

    def get_current_config(self) -> Dict[str, str]:
        """Read current model configuration from config.py."""
        import config
        result = {
            "orchestrator": config.MODEL,
            "codestral": config.SPECIALIZED_MODELS["codestral"]["model"],
            "reasoning": config.SPECIALIZED_MODELS["reasoning"]["model"],
            "search": config.SPECIALIZED_MODELS["search"]["model"],
            "intent_detector": config.SPECIALIZED_MODELS["intent_detector"]["model"],
            "energy_analyst_endpoint": config.ENERGY_ANALYST["endpoint"],
            "energy_analyst_enabled": config.ENERGY_ANALYST["enabled"],
        }

        # Add endpoint information if available
        if hasattr(config, 'MODEL_ENDPOINTS'):
            result.update({
                "orchestrator_endpoint": config.MODEL_ENDPOINTS.get("orchestrator", "local"),
                "codestral_endpoint": config.MODEL_ENDPOINTS.get("codestral", "local"),
                "reasoning_endpoint": config.MODEL_ENDPOINTS.get("reasoning", "local"),
                "search_endpoint": config.MODEL_ENDPOINTS.get("search", "local"),
                "intent_detector_endpoint": config.MODEL_ENDPOINTS.get("intent_detector", "local"),
            })

        # Add HF token information if available
        if hasattr(config, 'HF_TOKEN'):
            result["hf_token"] = config.HF_TOKEN

        return result

    def display_models(self, available: List[Dict[str, str]], current: Dict[str, str]):
        """Display available models and current selections."""
        from rich.table import Table
        from rich.panel import Panel

        # Helper to format endpoint origin
        def format_origin(endpoint_key):
            if endpoint_key == "local":
                return "Local (LM Studio)"
            return f"HF: {endpoint_key}"

        # Helper to mask token
        def mask_token(token):
            if not token or len(token) < 8:
                return "Not set"
            return f"{token[:4]}...{token[-4:]}"

        # Current configuration panel
        energy_status = "Enabled" if current.get('energy_analyst_enabled', True) else "Disabled"
        config_lines = [
            f"[cyan]Orchestrator:[/cyan] {current['orchestrator']}",
        ]
        if current.get('orchestrator_endpoint'):
            config_lines[0] += f" [dim]({format_origin(current['orchestrator_endpoint'])})[/dim]"

        config_lines.extend([
            f"[cyan]Code Generation:[/cyan] {current['codestral']}" + (f" [dim]({format_origin(current.get('codestral_endpoint', 'local'))})[/dim]" if current.get('codestral_endpoint') else ""),
            f"[cyan]Reasoning/Planning:[/cyan] {current['reasoning']}" + (f" [dim]({format_origin(current.get('reasoning_endpoint', 'local'))})[/dim]" if current.get('reasoning_endpoint') else ""),
            f"[cyan]Search/Research:[/cyan] {current['search']}" + (f" [dim]({format_origin(current.get('search_endpoint', 'local'))})[/dim]" if current.get('search_endpoint') else ""),
            f"[cyan]Intent Detection:[/cyan] {current['intent_detector']}" + (f" [dim]({format_origin(current.get('intent_detector_endpoint', 'local'))})[/dim]" if current.get('intent_detector_endpoint') else ""),
            f"[cyan]EnergyAnalyst:[/cyan] {current.get('energy_analyst_endpoint', 'http://localhost:8000')} ({energy_status})",
            f"[cyan]HuggingFace Token:[/cyan] {mask_token(current.get('hf_token'))}",
        ])

        config_text = "\n".join(config_lines)
        self.ui.console.print(Panel(config_text, title="Current Configuration", border_style="blue"))

        # Available models table
        table = Table(title="Available Models (Local & Remote)", show_header=True, header_style="bold magenta")
        table.add_column("#", style="dim", width=4)
        table.add_column("Model ID", style="cyan")
        table.add_column("Origin", style="dim")

        for idx, model_info in enumerate(available, 1):
            table.add_row(str(idx), model_info["name"], model_info["origin"])

        self.ui.console.print(table)

    def select_model(self, role: str, available: List[Dict[str, str]], current: str) -> Optional[Dict[str, str]]:
        """
        Interactive model selection for a specific role.

        Returns:
            Dict with 'model' and 'endpoint' keys, or None if keeping current
        """
        self.ui.console.print(f"\n[bold]Select model for {role}[/bold]")
        self.ui.console.print(f"[dim]Current: {current}[/dim]")
        self.ui.console.print("[dim]Enter number to select, or press Enter to keep current:[/dim]")

        choice = input(">>> ").strip()

        if not choice:
            return None  # Keep current

        try:
            idx = int(choice) - 1
            if 0 <= idx < len(available):
                model_info = available[idx]
                # Extract endpoint key from origin
                origin = model_info["origin"]
                if origin.startswith("HF: "):
                    endpoint = origin[4:]  # Remove "HF: " prefix
                else:
                    endpoint = "local"

                return {
                    "model": model_info["name"],
                    "endpoint": endpoint
                }
            else:
                self.ui.console.print("[red]Invalid selection. Keeping current.[/red]")
                return None
        except ValueError:
            self.ui.console.print("[red]Invalid input. Keeping current.[/red]")
            return None

    def configure_hf_token(self, current_token: str) -> Optional[str]:
        """Interactive HuggingFace token configuration."""
        # Mask current token for display
        masked = f"{current_token[:4]}...{current_token[-4:]}" if current_token and len(current_token) >= 8 else "Not set"

        self.ui.console.print(f"\n[bold]Configure HuggingFace API Token[/bold]")
        self.ui.console.print(f"[dim]Current: {masked}[/dim]")
        self.ui.console.print("[dim]Enter new token, or press Enter to keep current:[/dim]")
        self.ui.console.print("[yellow]Note: Token will be stored in config.py[/yellow]\n")

        new_token = input(">>> ").strip()

        if not new_token:
            return None  # Keep current

        # Basic validation - HF tokens typically start with "hf_"
        if not new_token.startswith("hf_"):
            self.ui.console.print("[yellow]Warning: HuggingFace tokens usually start with 'hf_'[/yellow]")
            self.ui.console.print("[dim]Continue anyway? (y/n):[/dim]")
            confirm = input(">>> ").strip().lower()
            if confirm != 'y':
                self.ui.console.print("[dim]Token update cancelled.[/dim]")
                return None

        return new_token

    def select_energy_analyst_endpoint(self, current_endpoint: str, current_enabled: bool) -> Optional[Dict[str, any]]:
        """Interactive EnergyAnalyst endpoint selection."""
        from rich.table import Table

        self.ui.console.print(f"\n[bold]Configure EnergyAnalyst Endpoint[/bold]")
        self.ui.console.print(f"[dim]Current: {current_endpoint} ({'Enabled' if current_enabled else 'Disabled'})[/dim]\n")

        # Options table
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("#", style="dim", width=4)
        table.add_column("Option", style="cyan")
        table.add_column("Endpoint", style="dim")

        options = [
            ("Local (Development)", "http://localhost:8000"),
            ("Production (Railway)", "https://energyanalystragservice-production.up.railway.app"),
            ("Custom URL", "Enter custom endpoint"),
            ("Disable", "Tool will not be called"),
        ]

        for idx, (name, desc) in enumerate(options, 1):
            table.add_row(str(idx), name, desc)

        self.ui.console.print(table)
        self.ui.console.print("\n[dim]Enter number to select, or press Enter to keep current:[/dim]")

        choice = input(">>> ").strip()

        if not choice:
            return None  # Keep current

        try:
            idx = int(choice)
            if idx == 1:  # Local
                return {"endpoint": "http://localhost:8000", "enabled": True}
            elif idx == 2:  # Production
                return {"endpoint": "https://energyanalystragservice-production.up.railway.app", "enabled": True}
            elif idx == 3:  # Custom
                self.ui.console.print("\n[bold]Enter custom endpoint URL:[/bold]")
                self.ui.console.print("[dim]Example: https://your-api.com[/dim]")
                custom_url = input(">>> ").strip()
                if custom_url:
                    # Ensure URL starts with http:// or https://
                    if not custom_url.startswith(("http://", "https://")):
                        custom_url = "https://" + custom_url
                    return {"endpoint": custom_url, "enabled": True}
                else:
                    self.ui.console.print("[red]No URL entered. Keeping current.[/red]")
                    return None
            elif idx == 4:  # Disable
                return {"endpoint": current_endpoint, "enabled": False}
            else:
                self.ui.console.print("[red]Invalid selection. Keeping current.[/red]")
                return None
        except ValueError:
            self.ui.console.print("[red]Invalid input. Keeping current.[/red]")
            return None

    def update_config_file(self, updates: Dict[str, str]) -> bool:
        """Update config.py with new model selections and endpoint mappings."""
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
            for role in ["codestral", "reasoning", "search", "intent_detector"]:
                if role in updates:
                    # Find the role's config block and update the model line
                    pattern = rf'"{role}":\s*\{{\s*"model":\s*"[^"]*"'
                    replacement = f'"{role}": {{\n        "model": "{updates[role]}"'
                    content = re.sub(pattern, replacement, content)

            # Update MODEL_ENDPOINTS mapping
            for role in ["orchestrator", "codestral", "reasoning", "search", "intent_detector"]:
                endpoint_key = f"{role}_endpoint"
                if endpoint_key in updates:
                    # Update the specific role's endpoint in MODEL_ENDPOINTS dict
                    pattern = rf'"{role}":\s*"[^"]*"'
                    replacement = f'"{role}": "{updates[endpoint_key]}"'
                    content = re.sub(pattern, replacement, content)

            # Update EnergyAnalyst endpoint
            if "energy_analyst_endpoint" in updates:
                pattern = r'"endpoint":\s*"[^"]*"'
                replacement = f'"endpoint": "{updates["energy_analyst_endpoint"]}"'
                content = re.sub(pattern, replacement, content)

            # Update EnergyAnalyst enabled status
            if "energy_analyst_enabled" in updates:
                pattern = r'"enabled":\s*(True|False)'
                replacement = f'"enabled": {updates["energy_analyst_enabled"]}'
                content = re.sub(pattern, replacement, content)

            # Update HF token
            if "hf_token" in updates:
                pattern = r'HF_TOKEN = "[^"]*"'
                replacement = f'HF_TOKEN = "{updates["hf_token"]}"'
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
            ("intent_detector", "Intent Detection (fast routing)"),
        ]

        for role_key, role_name in roles:
            selection = self.select_model(role_name, available, current[role_key])
            if selection:
                updates[role_key] = selection["model"]
                updates[f"{role_key}_endpoint"] = selection["endpoint"]

        # Configure EnergyAnalyst endpoint
        energy_config = self.select_energy_analyst_endpoint(
            current.get('energy_analyst_endpoint', 'http://localhost:8000'),
            current.get('energy_analyst_enabled', True)
        )
        if energy_config:
            updates["energy_analyst_endpoint"] = energy_config["endpoint"]
            updates["energy_analyst_enabled"] = energy_config["enabled"]

        # Configure HuggingFace token
        new_token = self.configure_hf_token(current.get('hf_token', ''))
        if new_token:
            updates["hf_token"] = new_token

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
