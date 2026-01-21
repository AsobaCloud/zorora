"""Config management utilities for Web UI settings."""

import ast
import re
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
import shutil
from datetime import datetime

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages reading and writing config.py safely."""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize config manager.
        
        Args:
            config_path: Path to config.py (default: ./config.py)
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config.py"
        self.config_path = Path(config_path)
        self.backup_dir = self.config_path.parent / ".config_backups"
        self.backup_dir.mkdir(exist_ok=True)
    
    def read_config(self) -> Dict[str, Any]:
        """
        Read current config.py safely.
        
        Returns:
            Dict with config values
        """
        if not self.config_path.exists():
            logger.warning(f"Config file not found: {self.config_path}")
            return self._get_default_config()
        
        try:
            # Use importlib to safely load config module
            import importlib.util
            spec = importlib.util.spec_from_file_location("config", self.config_path)
            config_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(config_module)
            
            return {
                "api_url": getattr(config_module, "API_URL", "http://localhost:1234/v1/chat/completions"),
                "model": getattr(config_module, "MODEL", "your-model-name"),
                "specialized_models": getattr(config_module, "SPECIALIZED_MODELS", {}),
                "model_endpoints": getattr(config_module, "MODEL_ENDPOINTS", {}),
                "hf_endpoints": getattr(config_module, "HF_ENDPOINTS", {}),
                "hf_token": getattr(config_module, "HF_TOKEN", None),
                "openai_api_key": getattr(config_module, "OPENAI_API_KEY", None),
                "openai_endpoints": getattr(config_module, "OPENAI_ENDPOINTS", {}),
                "anthropic_api_key": getattr(config_module, "ANTHROPIC_API_KEY", None),
                "anthropic_endpoints": getattr(config_module, "ANTHROPIC_ENDPOINTS", {}),
                "nehanda": getattr(config_module, "NEHANDA", {}),
            }
        except Exception as e:
            logger.error(f"Error reading config: {e}")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default config structure."""
        return {
            "api_url": "http://localhost:1234/v1/chat/completions",
            "model": "your-model-name",
            "specialized_models": {
                "codestral": {"model": "your-model-name"},
                "reasoning": {"model": "your-model-name"},
                "search": {"model": "your-model-name"},
                "intent_detector": {"model": "your-model-name"},
            },
            "model_endpoints": {
                "orchestrator": "local",
                "codestral": "local",
                "reasoning": "local",
                "search": "local",
                "intent_detector": "local",
            },
            "hf_endpoints": {},
            "hf_token": None,
            "openai_api_key": None,
            "openai_endpoints": {},
            "anthropic_api_key": None,
            "anthropic_endpoints": {},
            "nehanda": {
                "endpoint": "http://localhost:8000",
                "enabled": True,
            },
        }
    
    def write_config(self, updates: Dict[str, Any]) -> Dict[str, bool]:
        """
        Write config updates to config.py.
        
        Args:
            updates: Dict with config updates
                {
                    "model_endpoints": {"orchestrator": "local", ...},
                    "specialized_models": {"codestral": {"model": "..."}, ...},
                    "hf_endpoints": {"key": {...}, ...},
                    "hf_token": "...",
                }
        
        Returns:
            {"success": bool, "error": str}
        """
        try:
            # Backup existing config
            self._backup_config()
            
            # Read current config
            current = self.read_config()
            
            # Merge updates
            merged = self._merge_config(current, updates)
            
            # Validate merged config
            validation_error = self._validate_config(merged)
            if validation_error:
                return {"success": False, "error": validation_error}
            
            # Write config file
            self._write_config_file(merged)
            
            return {"success": True, "error": None}
            
        except Exception as e:
            logger.error(f"Error writing config: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    def _backup_config(self):
        """Create backup of config.py before writing."""
        if not self.config_path.exists():
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir / f"config_{timestamp}.py"
        shutil.copy2(self.config_path, backup_path)
        logger.info(f"Backed up config to: {backup_path}")
    
    def _merge_config(self, current: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
        """Merge updates into current config."""
        merged = current.copy()
        
        # Deep merge nested dicts
        if "model_endpoints" in updates:
            merged["model_endpoints"] = {**current.get("model_endpoints", {}), **updates["model_endpoints"]}
        
        if "specialized_models" in updates:
            merged["specialized_models"] = current.get("specialized_models", {}).copy()
            for role, model_config in updates["specialized_models"].items():
                if role in merged["specialized_models"]:
                    merged["specialized_models"][role] = {
                        **merged["specialized_models"][role],
                        **model_config
                    }
                else:
                    merged["specialized_models"][role] = model_config
        
        if "hf_endpoints" in updates:
            merged["hf_endpoints"] = {**current.get("hf_endpoints", {}), **updates["hf_endpoints"]}
        
        if "openai_endpoints" in updates:
            merged["openai_endpoints"] = {**current.get("openai_endpoints", {}), **updates["openai_endpoints"]}
        
        if "anthropic_endpoints" in updates:
            merged["anthropic_endpoints"] = {**current.get("anthropic_endpoints", {}), **updates["anthropic_endpoints"]}
        
        # Only update API tokens if provided and not masked
        for token_key in ["hf_token", "openai_api_key", "anthropic_api_key"]:
            if token_key in updates:
                token_value = updates[token_key]
                # Reject masked tokens (contain "...")
                if isinstance(token_value, str) and "..." in token_value:
                    logger.warning(f"Rejected masked {token_key} update")
                else:
                    merged[token_key] = token_value
        
        if "nehanda" in updates:
            merged["nehanda"] = {**current.get("nehanda", {}), **updates["nehanda"]}
        
        return merged
    
    def _validate_config(self, config: Dict[str, Any]) -> Optional[str]:
        """Validate config structure and values."""
        # Validate model_endpoints
        if "model_endpoints" in config:
            valid_roles = ["orchestrator", "codestral", "reasoning", "search", "intent_detector", "vision", "image_generation"]
            for role, endpoint in config["model_endpoints"].items():
                if role not in valid_roles:
                    return f"Invalid role in model_endpoints: {role}"
                # "local" is always valid (special value)
                if endpoint == "local":
                    continue
                # Check if endpoint exists in any provider dict
                hf_endpoints = config.get("hf_endpoints", {})
                openai_endpoints = config.get("openai_endpoints", {})
                anthropic_endpoints = config.get("anthropic_endpoints", {})
                if endpoint not in hf_endpoints and endpoint not in openai_endpoints and endpoint not in anthropic_endpoints:
                    return f"Endpoint '{endpoint}' not found in HF_ENDPOINTS, OPENAI_ENDPOINTS, or ANTHROPIC_ENDPOINTS"
        
        # Validate HF endpoints
        if "hf_endpoints" in config:
            for key, endpoint_config in config["hf_endpoints"].items():
                if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_-]*$', key):
                    return f"Invalid endpoint key: {key} (must be valid Python identifier)"
                if "url" not in endpoint_config:
                    return f"HF endpoint '{key}' missing 'url'"
                if not endpoint_config["url"].startswith(("http://", "https://")):
                    return f"HF endpoint '{key}' URL must start with http:// or https://"
                if "model_name" not in endpoint_config:
                    return f"HF endpoint '{key}' missing 'model_name'"
        
        # Validate OpenAI endpoints
        if "openai_endpoints" in config:
            for key, endpoint_config in config["openai_endpoints"].items():
                if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_-]*$', key):
                    return f"Invalid endpoint key: {key} (must be valid Python identifier)"
                if "model" not in endpoint_config:
                    return f"OpenAI endpoint '{key}' missing 'model'"
        
        # Validate Anthropic endpoints
        if "anthropic_endpoints" in config:
            for key, endpoint_config in config["anthropic_endpoints"].items():
                if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_-]*$', key):
                    return f"Invalid endpoint key: {key} (must be valid Python identifier)"
                if "model" not in endpoint_config:
                    return f"Anthropic endpoint '{key}' missing 'model'"
        
        # Validate API URL
        if "api_url" in config:
            if not config["api_url"].startswith(("http://", "https://")):
                return "API_URL must start with http:// or https://"
        
        return None
    
    def _write_config_file(self, config: Dict[str, Any]):
        """
        Write config dict to config.py file.
        
        NOTE: This ALWAYS regenerates the entire file. Comments and formatting
        from the original config.py are NOT preserved. This is intentional.
        """
        lines = [
            '"""Configuration constants and settings.',
            '',
            'IMPORTANT: This file is auto-generated by Web UI settings.',
            'Manual edits may be overwritten.',
            '"""',
            '',
            'from pathlib import Path',
            '',
            '# LM Studio API Configuration (OpenAI-compatible)',
            f'API_URL = "{config["api_url"]}"',
            f'MODEL = "{config["model"]}"',
            'MAX_TOKENS = 2048',
            'TIMEOUT = 60',
            'TEMPERATURE = 0.2',
            '',
            '# Specialized Model Configuration',
            'SPECIALIZED_MODELS = {',
        ]
        
        # Write SPECIALIZED_MODELS
        for role, model_config in config.get("specialized_models", {}).items():
            model_name = model_config.get("model", "your-model-name")
            max_tokens = model_config.get("max_tokens", 2048)
            temperature = model_config.get("temperature", 0.3)
            timeout = model_config.get("timeout", 60)
            lines.append(f'    "{role}": {{')
            lines.append(f'        "model": "{model_name}",')
            lines.append(f'        "max_tokens": {max_tokens},')
            lines.append(f'        "temperature": {temperature},')
            lines.append(f'        "timeout": {timeout},')
            lines.append('    },')
        
        lines.append('}')
        lines.append('')
        lines.append('# Hugging Face Inference Endpoints')
        if config.get("hf_token"):
            lines.append(f'HF_TOKEN = "{config["hf_token"]}"')
        else:
            lines.append('# HF_TOKEN = "hf_YOUR_TOKEN_HERE"')
        lines.append('')
        lines.append('HF_ENDPOINTS = {')
        
        # Write HF_ENDPOINTS
        for key, endpoint_config in config.get("hf_endpoints", {}).items():
            lines.append(f'    "{key}": {{')
            lines.append(f'        "url": "{endpoint_config["url"]}",')
            lines.append(f'        "model_name": "{endpoint_config["model_name"]}",')
            if "api_key" in endpoint_config:
                lines.append(f'        "api_key": "{endpoint_config["api_key"]}",')
            lines.append(f'        "timeout": {endpoint_config.get("timeout", 120)},')
            lines.append(f'        "enabled": {endpoint_config.get("enabled", True)},')
            lines.append('    },')
        
        lines.append('}')
        lines.append('')
        lines.append('# OpenAI API Configuration')
        if config.get("openai_api_key"):
            lines.append(f'OPENAI_API_KEY = "{config["openai_api_key"]}"')
        else:
            lines.append('# OPENAI_API_KEY = "sk-YOUR_KEY_HERE"')
        lines.append('')
        lines.append('OPENAI_ENDPOINTS = {')
        
        # Write OPENAI_ENDPOINTS
        for key, endpoint_config in config.get("openai_endpoints", {}).items():
            lines.append(f'    "{key}": {{')
            lines.append(f'        "model": "{endpoint_config["model"]}",')
            if "api_key" in endpoint_config:
                lines.append(f'        "api_key": "{endpoint_config["api_key"]}",')
            lines.append(f'        "timeout": {endpoint_config.get("timeout", 60)},')
            lines.append(f'        "enabled": {endpoint_config.get("enabled", True)},')
            if "max_tokens" in endpoint_config:
                lines.append(f'        "max_tokens": {endpoint_config["max_tokens"]},')
            lines.append('    },')
        
        lines.append('}')
        lines.append('')
        lines.append('# Anthropic API Configuration')
        if config.get("anthropic_api_key"):
            lines.append(f'ANTHROPIC_API_KEY = "{config["anthropic_api_key"]}"')
        else:
            lines.append('# ANTHROPIC_API_KEY = "sk-ant-YOUR_KEY_HERE"')
        lines.append('')
        lines.append('ANTHROPIC_ENDPOINTS = {')
        
        # Write ANTHROPIC_ENDPOINTS
        for key, endpoint_config in config.get("anthropic_endpoints", {}).items():
            lines.append(f'    "{key}": {{')
            lines.append(f'        "model": "{endpoint_config["model"]}",')
            if "api_key" in endpoint_config:
                lines.append(f'        "api_key": "{endpoint_config["api_key"]}",')
            lines.append(f'        "timeout": {endpoint_config.get("timeout", 60)},')
            lines.append(f'        "enabled": {endpoint_config.get("enabled", True)},')
            if "max_tokens" in endpoint_config:
                lines.append(f'        "max_tokens": {endpoint_config["max_tokens"]},')
            lines.append('    },')
        
        lines.append('}')
        lines.append('')
        lines.append('# Model Endpoint Mapping')
        lines.append('MODEL_ENDPOINTS = {')
        
        # Write MODEL_ENDPOINTS
        for role, endpoint in config.get("model_endpoints", {}).items():
            lines.append(f'    "{role}": "{endpoint}",')
        
        lines.append('}')
        lines.append('')
        lines.append('# Nehanda RAG Configuration (Energy Policy Analysis)')
        lines.append('NEHANDA = {')
        energy_config = config.get("nehanda", {})
        lines.append(f'    "endpoint": "{energy_config.get("endpoint", "http://localhost:8000")}",')
        lines.append(f'    "timeout": {energy_config.get("timeout", 180)},')
        lines.append(f'    "enabled": {energy_config.get("enabled", True)},')
        lines.append('}')
        
        # Write to file atomically
        temp_path = self.config_path.with_suffix('.py.tmp')
        temp_path.write_text('\n'.join(lines))
        temp_path.replace(self.config_path)
        logger.info(f"Wrote config to: {self.config_path}")


class ModelFetcher:
    """Fetches available models from LM Studio and HF endpoints."""
    
    def __init__(self):
        """Initialize model fetcher."""
        pass
    
    def fetch_lm_studio_models(self) -> List[Dict[str, str]]:
        """
        Fetch available models from LM Studio.
        
        Returns:
            List of dicts with 'name' and 'origin' keys
        """
        try:
            import requests
            response = requests.get("http://localhost:1234/v1/models", timeout=5)
            response.raise_for_status()
            data = response.json()
            
            models = []
            for model in data.get("data", []):
                model_id = model.get("id", "")
                if model_id:
                    models.append({
                        "name": model_id,
                        "origin": "Local (LM Studio)",
                        "type": "local"
                    })
            return models
        except Exception as e:
            logger.warning(f"Could not fetch LM Studio models: {e}")
            return []
    
    def fetch_hf_endpoints(self) -> List[Dict[str, str]]:
        """
        Fetch configured HF endpoints.
        
        Returns:
            List of dicts with endpoint info
        """
        try:
            import config
            endpoints = []
            
            if hasattr(config, 'HF_ENDPOINTS'):
                for key, endpoint_config in config.HF_ENDPOINTS.items():
                    if endpoint_config.get("enabled", True):
                        endpoints.append({
                            "key": key,
                            "name": endpoint_config.get("model_name", key),
                            "origin": f"HF: {key}",
                            "type": "hf",
                            "url": endpoint_config.get("url", ""),
                        })
            
            return endpoints
        except Exception as e:
            logger.warning(f"Could not fetch HF endpoints: {e}")
            return []
    
    def fetch_openai_endpoints(self) -> List[Dict[str, str]]:
        """
        Fetch configured OpenAI endpoints.
        
        Returns:
            List of dicts with endpoint info
        """
        try:
            import config
            endpoints = []
            
            if hasattr(config, 'OPENAI_ENDPOINTS'):
                for key, endpoint_config in config.OPENAI_ENDPOINTS.items():
                    if endpoint_config.get("enabled", True):
                        endpoints.append({
                            "key": key,
                            "name": endpoint_config.get("model", key),
                            "origin": f"OpenAI: {key}",
                            "type": "openai",
                            "url": "https://api.openai.com/v1/chat/completions",
                        })
            
            return endpoints
        except Exception as e:
            logger.warning(f"Could not fetch OpenAI endpoints: {e}")
            return []
    
    def fetch_anthropic_endpoints(self) -> List[Dict[str, str]]:
        """
        Fetch configured Anthropic endpoints.
        
        Returns:
            List of dicts with endpoint info
        """
        try:
            import config
            endpoints = []
            
            if hasattr(config, 'ANTHROPIC_ENDPOINTS'):
                for key, endpoint_config in config.ANTHROPIC_ENDPOINTS.items():
                    if endpoint_config.get("enabled", True):
                        endpoints.append({
                            "key": key,
                            "name": endpoint_config.get("model", key),
                            "origin": f"Anthropic: {key}",
                            "type": "anthropic",
                            "url": "https://api.anthropic.com/v1/messages",
                        })
            
            return endpoints
        except Exception as e:
            logger.warning(f"Could not fetch Anthropic endpoints: {e}")
            return []
    
    def fetch_all_models(self) -> List[Dict[str, str]]:
        """
        Fetch all available models (LM Studio + HF + OpenAI + Anthropic).
        
        NOTE: This is called on EVERY modal open - no caching is performed.
        Performance target is <500ms total for settings load.
        
        Returns:
            Combined list of models
        """
        models = self.fetch_lm_studio_models()
        hf_endpoints = self.fetch_hf_endpoints()
        openai_endpoints = self.fetch_openai_endpoints()
        anthropic_endpoints = self.fetch_anthropic_endpoints()
        
        # Convert endpoints to model format
        for endpoint in hf_endpoints + openai_endpoints + anthropic_endpoints:
            models.append({
                "name": endpoint["name"],
                "origin": endpoint["origin"],
                "type": endpoint["type"],
                "endpoint_key": endpoint["key"],
            })
        
        return models
