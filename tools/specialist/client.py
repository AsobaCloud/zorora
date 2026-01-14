"""
Specialist LLM client factory.

Creates configured LLMClient instances for different specialist roles.
"""

import logging
import os
from typing import Dict, Any

logger = logging.getLogger(__name__)


def create_specialist_client(role: str, model_config: Dict[str, Any]):
    """
    Create an LLMClient for a specialist role, using local, HF, OpenAI, or Anthropic endpoint.

    Args:
        role: Role name (e.g., "codestral", "reasoning", "search", "intent_detector")
        model_config: Model configuration dict from SPECIALIZED_MODELS

    Returns:
        LLMClient instance configured for the role
    """
    from llm_client import LLMClient
    import config

    # Check if we have endpoint mappings
    endpoint_key = "local"
    if hasattr(config, 'MODEL_ENDPOINTS') and role in config.MODEL_ENDPOINTS:
        endpoint_key = config.MODEL_ENDPOINTS[role]

    # If local, use LM Studio
    if endpoint_key == "local":
        return LLMClient(
            api_url=config.API_URL,
            model=model_config["model"],
            max_tokens=model_config["max_tokens"],
            temperature=model_config["temperature"],
            timeout=model_config["timeout"]
        )

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
            timeout=openai_config.get("timeout", model_config["timeout"]),
        )
        # Wrap adapter in LLMClient-compatible interface
        client = LLMClient.__new__(LLMClient)
        client.adapter = adapter
        client.api_url = f"https://api.openai.com/v1/chat/completions"
        client.model = openai_config.get("model", endpoint_key)
        client.max_tokens = model_config["max_tokens"]
        client.temperature = model_config["temperature"]
        client.timeout = openai_config.get("timeout", model_config["timeout"])
        client.tool_choice = "auto"
        client.parallel_tool_calls = True
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
            timeout=anthropic_config.get("timeout", model_config["timeout"]),
        )
        # Wrap adapter in LLMClient-compatible interface
        client = LLMClient.__new__(LLMClient)
        client.adapter = adapter
        client.api_url = f"https://api.anthropic.com/v1/messages"
        client.model = anthropic_config.get("model", endpoint_key)
        client.max_tokens = model_config["max_tokens"]
        client.temperature = model_config["temperature"]
        client.timeout = anthropic_config.get("timeout", model_config["timeout"])
        client.tool_choice = "auto"
        client.parallel_tool_calls = True
        client.auth_token = api_key
        return client

    # Check HF endpoints (existing logic)
    if hasattr(config, 'HF_ENDPOINTS') and endpoint_key in config.HF_ENDPOINTS:
        hf_config = config.HF_ENDPOINTS[endpoint_key]
        return LLMClient(
            api_url=hf_config["url"],
            model=hf_config["model_name"],
            max_tokens=model_config["max_tokens"],
            temperature=model_config["temperature"],
            timeout=hf_config.get("timeout", model_config["timeout"]),
            auth_token=config.HF_TOKEN if hasattr(config, 'HF_TOKEN') else None
        )

    # Fallback to local if endpoint not found
    logger.warning(f"Endpoint '{endpoint_key}' not found for role '{role}', falling back to local")
    return LLMClient(
        api_url=config.API_URL,
        model=model_config["model"],
        max_tokens=model_config["max_tokens"],
        temperature=model_config["temperature"],
        timeout=model_config["timeout"]
    )
