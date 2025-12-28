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
        Fetch available models from all providers (Local, HF, OpenAI, Anthropic).

        Returns:
            List of dicts with 'name', 'origin', 'provider', and 'cost' keys
        """
        models = []
        import config
        import os

        # Fetch from LM Studio (local)
        try:
            local_models = self.llm_client.list_models()
            for model in local_models:
                models.append({
                    "name": model,
                    "origin": "Local (LM Studio)",
                    "provider": "local",
                    "cost": "Free"
                })
        except Exception as e:
            self.ui.console.print(f"[yellow]Warning: Could not fetch LM Studio models: {e}[/yellow]")

        # Fetch from HF endpoints (existing pattern)
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
                        "origin": f"HF: {endpoint_key}",
                        "provider": endpoint_key,
                        "cost": "Free (HF Inference)"
                    })
                except Exception as e:
                    self.ui.console.print(f"[yellow]Warning: Could not connect to HF endpoint '{endpoint_key}': {e}[/yellow]")

        # Fetch from OpenAI endpoints (matches HF pattern)
        openai_key = None
        if hasattr(config, 'OPENAI_API_KEY') and config.OPENAI_API_KEY:
            openai_key = config.OPENAI_API_KEY
        elif os.getenv("OPENAI_API_KEY"):
            openai_key = os.getenv("OPENAI_API_KEY")
        
        if openai_key and hasattr(config, 'OPENAI_ENDPOINTS'):
            for endpoint_key, endpoint_config in config.OPENAI_ENDPOINTS.items():
                if not endpoint_config.get("enabled", True):
                    continue
                models.append({
                    "name": endpoint_config.get("model", endpoint_key),
                    "origin": f"OpenAI: {endpoint_key}",
                    "provider": endpoint_key,  # Simple key, not prefixed
                    "cost": "Paid"
                })

        # Fetch from Anthropic endpoints (matches HF pattern)
        anthropic_key = None
        if hasattr(config, 'ANTHROPIC_API_KEY') and config.ANTHROPIC_API_KEY:
            anthropic_key = config.ANTHROPIC_API_KEY
        elif os.getenv("ANTHROPIC_API_KEY"):
            anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        
        if anthropic_key and hasattr(config, 'ANTHROPIC_ENDPOINTS'):
            for endpoint_key, endpoint_config in config.ANTHROPIC_ENDPOINTS.items():
                if not endpoint_config.get("enabled", True):
                    continue
                models.append({
                    "name": endpoint_config.get("model", endpoint_key),
                    "origin": f"Anthropic: {endpoint_key}",
                    "provider": endpoint_key,  # Simple key, not prefixed
                    "cost": "Paid"
                })

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
            "vision": config.SPECIALIZED_MODELS.get("vision", {}).get("model", "Not configured"),
            "image_generation": config.SPECIALIZED_MODELS.get("image_generation", {}).get("model", "Not configured"),
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
                "vision_endpoint": config.MODEL_ENDPOINTS.get("vision", "local"),
                "image_generation_endpoint": config.MODEL_ENDPOINTS.get("image_generation", "local"),
            })

        # Add API key information if available
        if hasattr(config, 'HF_TOKEN'):
            result["hf_token"] = config.HF_TOKEN
        if hasattr(config, 'OPENAI_API_KEY'):
            result["openai_api_key"] = config.OPENAI_API_KEY
        if hasattr(config, 'ANTHROPIC_API_KEY'):
            result["anthropic_api_key"] = config.ANTHROPIC_API_KEY

        return result

    def display_models(self, available: List[Dict[str, str]], current: Dict[str, str]):
        """Display available models and current selections."""
        from rich.table import Table
        from rich.panel import Panel

        # Helper to format endpoint origin
        def format_origin(endpoint_key):
            if endpoint_key == "local":
                return "Local (LM Studio)"
            # Check which provider dict contains this key
            import config
            if hasattr(config, 'OPENAI_ENDPOINTS') and endpoint_key in config.OPENAI_ENDPOINTS:
                return f"OpenAI: {endpoint_key}"
            if hasattr(config, 'ANTHROPIC_ENDPOINTS') and endpoint_key in config.ANTHROPIC_ENDPOINTS:
                return f"Anthropic: {endpoint_key}"
            if hasattr(config, 'HF_ENDPOINTS') and endpoint_key in config.HF_ENDPOINTS:
                return f"HF: {endpoint_key}"
            return f"Unknown: {endpoint_key}"

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
            f"[cyan]Vision/Image Analysis:[/cyan] {current.get('vision', 'Not configured')}" + (f" [dim]({format_origin(current.get('vision_endpoint', 'local'))})[/dim]" if current.get('vision_endpoint') else ""),
            f"[cyan]Image Generation:[/cyan] {current.get('image_generation', 'Not configured')}" + (f" [dim]({format_origin(current.get('image_generation_endpoint', 'local'))})[/dim]" if current.get('image_generation_endpoint') else ""),
            f"[cyan]EnergyAnalyst:[/cyan] {current.get('energy_analyst_endpoint', 'http://localhost:8000')} ({energy_status})",
            f"[cyan]HuggingFace Token:[/cyan] {mask_token(current.get('hf_token'))}",
            f"[cyan]OpenAI API Key:[/cyan] {mask_token(current.get('openai_api_key', ''))}",
            f"[cyan]Anthropic API Key:[/cyan] {mask_token(current.get('anthropic_api_key', ''))}",
        ])

        config_text = "\n".join(config_lines)
        self.ui.console.print(Panel(config_text, title="Current Configuration", border_style="blue"))

        # Available models table
        table = Table(title="Available Models (Local & Remote)", show_header=True, header_style="bold magenta")
        table.add_column("#", style="dim", width=4)
        table.add_column("Model ID", style="cyan")
        table.add_column("Origin", style="dim")
        table.add_column("Cost", style="yellow", width=12)

        for idx, model_info in enumerate(available, 1):
            cost = model_info.get("cost", "Unknown")
            cost_style = "green" if cost == "Free" or "Free" in cost else "yellow"
            table.add_row(
                str(idx),
                model_info["name"],
                model_info["origin"],
                f"[{cost_style}]{cost}[/{cost_style}]"
            )

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
                # Extract endpoint key from provider field (simple key, not prefixed)
                provider = model_info.get("provider", "local")
                if provider == "local":
                    endpoint = "local"
                else:
                    # Use provider as endpoint key (works for HF, OpenAI, Anthropic)
                    endpoint = provider

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

    def configure_openai_key(self, current_key: str) -> Optional[str]:
        """Interactive OpenAI API key configuration."""
        import os
        # Check environment variable if config is empty
        if not current_key:
            current_key = os.getenv("OPENAI_API_KEY", "")
        
        # Mask current key for display
        masked = f"{current_key[:4]}...{current_key[-4:]}" if current_key and len(current_key) >= 8 else "Not set"

        self.ui.console.print(f"\n[bold]Configure OpenAI API Key[/bold]")
        self.ui.console.print(f"[dim]Current: {masked}[/dim]")
        self.ui.console.print("[dim]Enter new API key, or press Enter to keep current:[/dim]")
        self.ui.console.print("[yellow]Note: Key will be stored in config.py[/yellow]")
        self.ui.console.print("[dim]You can also set OPENAI_API_KEY environment variable[/dim]\n")

        new_key = input(">>> ").strip()

        if not new_key:
            return None  # Keep current

        # Basic validation - OpenAI keys typically start with "sk-"
        if not new_key.startswith("sk-"):
            self.ui.console.print("[yellow]Warning: OpenAI API keys usually start with 'sk-'[/yellow]")
            self.ui.console.print("[dim]Continue anyway? (y/n):[/dim]")
            confirm = input(">>> ").strip().lower()
            if confirm != 'y':
                self.ui.console.print("[dim]Key update cancelled.[/dim]")
                return None

        return new_key

    def configure_anthropic_key(self, current_key: str) -> Optional[str]:
        """Interactive Anthropic API key configuration."""
        import os
        # Check environment variable if config is empty
        if not current_key:
            current_key = os.getenv("ANTHROPIC_API_KEY", "")
        
        # Mask current key for display
        masked = f"{current_key[:4]}...{current_key[-4:]}" if current_key and len(current_key) >= 8 else "Not set"

        self.ui.console.print(f"\n[bold]Configure Anthropic API Key[/bold]")
        self.ui.console.print(f"[dim]Current: {masked}[/dim]")
        self.ui.console.print("[dim]Enter new API key, or press Enter to keep current:[/dim]")
        self.ui.console.print("[yellow]Note: Key will be stored in config.py[/yellow]")
        self.ui.console.print("[dim]You can also set ANTHROPIC_API_KEY environment variable[/dim]\n")

        new_key = input(">>> ").strip()

        if not new_key:
            return None  # Keep current

        # Basic validation - Anthropic keys typically start with "sk-ant-"
        if not new_key.startswith("sk-ant-"):
            self.ui.console.print("[yellow]Warning: Anthropic API keys usually start with 'sk-ant-'[/yellow]")
            self.ui.console.print("[dim]Continue anyway? (y/n):[/dim]")
            confirm = input(">>> ").strip().lower()
            if confirm != 'y':
                self.ui.console.print("[dim]Key update cancelled.[/dim]")
                return None

        return new_key

    def add_hf_endpoint(self) -> Optional[Dict[str, any]]:
        """Interactive HuggingFace endpoint addition."""
        self.ui.console.print(f"\n[bold cyan]Add New HuggingFace Inference Endpoint[/bold cyan]\n")

        # Endpoint key (identifier)
        self.ui.console.print("[bold]1. Endpoint Key (identifier)[/bold]")
        self.ui.console.print("[dim]This is a short name to identify this endpoint (e.g., 'llama-70b', 'mistral-large')[/dim]")
        endpoint_key = input(">>> ").strip()

        if not endpoint_key:
            self.ui.console.print("[red]Endpoint key is required.[/red]")
            return None

        # Check if endpoint already exists
        import config
        if hasattr(config, 'HF_ENDPOINTS') and endpoint_key in config.HF_ENDPOINTS:
            self.ui.console.print(f"[yellow]Warning: Endpoint '{endpoint_key}' already exists.[/yellow]")
            self.ui.console.print("[dim]Overwrite? (y/n):[/dim]")
            confirm = input(">>> ").strip().lower()
            if confirm != 'y':
                self.ui.console.print("[dim]Cancelled.[/dim]")
                return None

        # Endpoint URL
        self.ui.console.print("\n[bold]2. Endpoint URL[/bold]")
        self.ui.console.print("[dim]Full URL to the inference endpoint (must end with /v1/chat/completions)[/dim]")
        self.ui.console.print("[dim]Example: https://xyz.endpoints.huggingface.cloud/v1/chat/completions[/dim]")
        url = input(">>> ").strip()

        if not url:
            self.ui.console.print("[red]URL is required.[/red]")
            return None

        # Ensure URL is valid
        if not url.startswith(("http://", "https://")):
            self.ui.console.print("[yellow]Warning: URL should start with http:// or https://[/yellow]")
            url = "https://" + url

        # Model name
        self.ui.console.print("\n[bold]3. Model Name[/bold]")
        self.ui.console.print("[dim]The model identifier (e.g., 'meta-llama/Llama-3.1-70B-Instruct')[/dim]")
        model_name = input(">>> ").strip()

        if not model_name:
            self.ui.console.print("[red]Model name is required.[/red]")
            return None

        # Timeout (optional)
        self.ui.console.print("\n[bold]4. Timeout (seconds)[/bold]")
        self.ui.console.print("[dim]Request timeout in seconds (default: 120, press Enter to use default)[/dim]")
        timeout_input = input(">>> ").strip()

        timeout = 120  # Default
        if timeout_input:
            try:
                timeout = int(timeout_input)
                if timeout <= 0:
                    self.ui.console.print("[yellow]Invalid timeout, using default (120s)[/yellow]")
                    timeout = 120
            except ValueError:
                self.ui.console.print("[yellow]Invalid timeout, using default (120s)[/yellow]")
                timeout = 120

        # Summary and confirmation
        self.ui.console.print("\n[bold]Summary:[/bold]")
        self.ui.console.print(f"  [cyan]Key:[/cyan] {endpoint_key}")
        self.ui.console.print(f"  [cyan]URL:[/cyan] {url}")
        self.ui.console.print(f"  [cyan]Model:[/cyan] {model_name}")
        self.ui.console.print(f"  [cyan]Timeout:[/cyan] {timeout}s")
        self.ui.console.print("\n[dim]Add this endpoint? (y/n):[/dim]")

        confirm = input(">>> ").strip().lower()
        if confirm != 'y':
            self.ui.console.print("[dim]Cancelled.[/dim]")
            return None

        return {
            "key": endpoint_key,
            "url": url,
            "model_name": model_name,
            "timeout": timeout,
            "enabled": True
        }

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
            for role in ["codestral", "reasoning", "search", "intent_detector", "vision", "image_generation"]:
                if role in updates:
                    # Find the role's config block and update the model line
                    pattern = rf'"{role}":\s*\{{\s*"model":\s*"[^"]*"'
                    replacement = f'"{role}": {{\n        "model": "{updates[role]}"'
                    content = re.sub(pattern, replacement, content)

            # Update MODEL_ENDPOINTS mapping
            for role in ["orchestrator", "codestral", "reasoning", "search", "intent_detector", "vision", "image_generation"]:
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

            # Update API keys
            if "hf_token" in updates:
                pattern = r'HF_TOKEN = "[^"]*"'
                replacement = f'HF_TOKEN = "{updates["hf_token"]}"'
                content = re.sub(pattern, replacement, content)
            
            if "openai_api_key" in updates:
                pattern = r'OPENAI_API_KEY = "[^"]*"'
                replacement = f'OPENAI_API_KEY = "{updates["openai_api_key"]}"'
                content = re.sub(pattern, replacement, content)
            
            if "anthropic_api_key" in updates:
                pattern = r'ANTHROPIC_API_KEY = "[^"]*"'
                replacement = f'ANTHROPIC_API_KEY = "{updates["anthropic_api_key"]}"'
                content = re.sub(pattern, replacement, content)

            self.config_path.write_text(content)
            return True

        except Exception as e:
            self.ui.display_error('error', f"Failed to update config: {e}")
            return False

    def add_hf_endpoint_to_config(self, endpoint_data: Dict[str, any]) -> bool:
        """Add a new HuggingFace endpoint to config.py HF_ENDPOINTS dictionary."""
        try:
            lines = self.config_path.read_text().splitlines(keepends=True)

            # Build the new endpoint entry
            new_endpoint_lines = [
                f'    "{endpoint_data["key"]}": {{\n',
                f'        "url": "{endpoint_data["url"]}",\n',
                f'        "model_name": "{endpoint_data["model_name"]}",\n',
                f'        "timeout": {endpoint_data["timeout"]},\n',
                f'        "enabled": {str(endpoint_data["enabled"])},\n',
                f'    }},\n',
            ]

            # Find the insertion point (before closing brace of HF_ENDPOINTS or before comment)
            insert_idx = None
            endpoint_key = endpoint_data['key']
            endpoint_start_idx = None
            endpoint_end_idx = None
            in_hf_endpoints = False

            for i, line in enumerate(lines):
                # Check if we're entering HF_ENDPOINTS
                if 'HF_ENDPOINTS = {' in line:
                    in_hf_endpoints = True
                    continue

                if in_hf_endpoints:
                    # Check if this endpoint already exists
                    if f'"{endpoint_key}"' in line and endpoint_start_idx is None:
                        endpoint_start_idx = i

                    # Find the end of existing endpoint entry (if replacing)
                    if endpoint_start_idx is not None and endpoint_end_idx is None:
                        if '},' in line:
                            endpoint_end_idx = i + 1
                            break

                    # Find insertion point (before comment or closing brace)
                    if '# Add more HF endpoints here as needed' in line:
                        insert_idx = i
                        break
                    elif line.strip() == '}':
                        insert_idx = i
                        break

            if not in_hf_endpoints:
                self.ui.console.print("[red]Could not find HF_ENDPOINTS in config.py[/red]")
                return False

            # Replace existing or insert new
            if endpoint_start_idx is not None and endpoint_end_idx is not None:
                # Replace existing endpoint
                lines[endpoint_start_idx:endpoint_end_idx] = new_endpoint_lines
            elif insert_idx is not None:
                # Insert new endpoint
                lines[insert_idx:insert_idx] = new_endpoint_lines
            else:
                self.ui.console.print("[red]Could not find insertion point in HF_ENDPOINTS[/red]")
                return False

            # Write back
            self.config_path.write_text(''.join(lines))
            return True

        except Exception as e:
            self.ui.console.print(f"[red]Failed to add HF endpoint: {e}[/red]")
            import traceback
            traceback.print_exc()
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

        # Ask if user wants to add a new HF endpoint first
        self.ui.console.print("\n[bold]Would you like to add a new HuggingFace inference endpoint?[/bold]")
        self.ui.console.print("[dim]Enter 'y' to add endpoint, or press Enter to skip:[/dim]")
        add_endpoint_choice = input(">>> ").strip().lower()

        if add_endpoint_choice == 'y':
            endpoint_data = self.add_hf_endpoint()
            if endpoint_data:
                if self.add_hf_endpoint_to_config(endpoint_data):
                    self.ui.console.print(f"[green]✓ Added HF endpoint '{endpoint_data['key']}' successfully![/green]")
                    self.ui.console.print("[yellow]⚠ Restart or run /models again to see it in the list.[/yellow]")
                    # Refresh available models to include the new endpoint
                    available = self.get_available_models()
                else:
                    self.ui.console.print("[red]✗ Failed to add HF endpoint.[/red]")

        # Collect updates
        updates = {}

        roles = [
            ("orchestrator", "Main Orchestrator"),
            ("codestral", "Code Generation"),
            ("reasoning", "Reasoning/Planning"),
            ("search", "Search/Research"),
            ("intent_detector", "Intent Detection (fast routing)"),
            ("vision", "Vision/Image Analysis"),
            ("image_generation", "Image Generation (text-to-image)"),
        ]

        for role_key, role_name in roles:
            selection = self.select_model(role_name, available, current.get(role_key, "Not configured"))
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

        # Configure API keys
        new_hf_token = self.configure_hf_token(current.get('hf_token', ''))
        if new_hf_token:
            updates["hf_token"] = new_hf_token
        
        import os
        current_openai_key = current.get('openai_api_key', '') or os.getenv("OPENAI_API_KEY", "")
        new_openai_key = self.configure_openai_key(current_openai_key)
        if new_openai_key:
            updates["openai_api_key"] = new_openai_key
        
        current_anthropic_key = current.get('anthropic_api_key', '') or os.getenv("ANTHROPIC_API_KEY", "")
        new_anthropic_key = self.configure_anthropic_key(current_anthropic_key)
        if new_anthropic_key:
            updates["anthropic_api_key"] = new_anthropic_key

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
