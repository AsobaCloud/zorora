"""
Energy analyst tool for energy policy and regulatory queries.
"""

import logging
import requests

logger = logging.getLogger(__name__)


def use_energy_analyst(query: str) -> str:
    """
    Analyze energy policy and regulatory compliance using EnergyAnalyst RAG.

    Args:
        query: Energy policy or regulatory compliance question

    Returns:
        Detailed analysis with RAG-sourced context from energy policy documents
    """
    if not query or not isinstance(query, str):
        return "Error: query must be a non-empty string"

    if len(query) > 2000:
        return "Error: query too long (max 2000 characters)"

    try:
        import config

        # Check if EnergyAnalyst is enabled
        if not config.ENERGY_ANALYST.get("enabled", True):
            return "Error: EnergyAnalyst is disabled. Enable it with /models command."

        logger.info(f"Delegating to EnergyAnalyst: {query[:100]}...")

        # Get endpoint and timeout from config
        endpoint = config.ENERGY_ANALYST.get("endpoint", "http://localhost:8000")
        timeout = config.ENERGY_ANALYST.get("timeout", 180)
        api_url = f"{endpoint.rstrip('/')}/chat"

        logger.info(f"Using EnergyAnalyst endpoint: {endpoint}")

        # Make API request
        response = requests.post(
            api_url,
            json={"message": query, "use_rag": True},
            timeout=timeout
        )
        response.raise_for_status()

        data = response.json()

        # Extract response and sources
        answer = data.get("response", "")
        sources = data.get("rag_sources", [])
        rag_used = data.get("rag_context_used", False)

        if not answer or not answer.strip():
            return "Error: EnergyAnalyst returned empty response"

        # Format response with sources
        formatted = [answer.strip()]

        if rag_used and sources:
            formatted.append("\n\n📚 Sources:")
            for source in sources:
                formatted.append(f"  - {source}")

        return "\n".join(formatted)

    except requests.ConnectionError:
        import config
        endpoint = config.ENERGY_ANALYST.get("endpoint", "http://localhost:8000")
        if "localhost" in endpoint:
            return f"Error: Could not connect to EnergyAnalyst API at {endpoint}. Is the local API server running? Start it with: cd ~/Workbench/energyanalyst-v0.1 && python api/server.py"
        else:
            return f"Error: Could not connect to EnergyAnalyst API at {endpoint}. Check endpoint configuration with /models command."

    except requests.Timeout:
        return "Error: EnergyAnalyst API request timed out after 180 seconds. The model may be generating a very long response or LM Studio may be overloaded."

    except requests.HTTPError as e:
        return f"Error: EnergyAnalyst API error (HTTP {e.response.status_code}): {e.response.text}"

    except Exception as e:
        logger.error(f"EnergyAnalyst error: {e}")
        return f"Error: Failed to call EnergyAnalyst: {str(e)}"
