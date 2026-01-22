"""
Nehanda RAG tool for energy policy and regulatory queries.
"""

import logging
import requests
from typing import Optional, List

logger = logging.getLogger(__name__)


def _get_available_municipalities(endpoint: str, timeout: int = 10) -> List[str]:
    """Fetch available municipalities from the Nehanda API."""
    try:
        response = requests.get(f"{endpoint.rstrip('/')}/municipalities", timeout=timeout)
        response.raise_for_status()
        return response.json().get("municipalities", [])
    except Exception as e:
        logger.warning(f"Could not fetch municipalities: {e}")
        return []


def _detect_municipality(query: str, available: List[str]) -> Optional[str]:
    """Detect municipality name from query text."""
    query_lower = query.lower()
    for muni in available:
        if muni.lower() in query_lower:
            return muni
    return None


def use_nehanda(query: str) -> str:
    """
    Analyze energy policy and regulatory compliance using Nehanda RAG.

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

        # Check if Nehanda is enabled
        if not config.NEHANDA.get("enabled", True):
            return "Error: Nehanda RAG is disabled. Enable it with /models command."

        logger.info(f"Delegating to Nehanda RAG: {query[:100]}...")

        # Get endpoint and timeout from config
        endpoint = config.NEHANDA.get("endpoint", "http://localhost:8000")
        timeout = config.NEHANDA.get("timeout", 180)
        api_url = f"{endpoint.rstrip('/')}/chat"

        logger.info(f"Using Nehanda endpoint: {endpoint}")

        # Get available municipalities and detect from query
        available_municipalities = _get_available_municipalities(endpoint)
        municipality = _detect_municipality(query, available_municipalities)

        if not municipality:
            if available_municipalities:
                return f"Please specify a municipality in your question. Available: {', '.join(available_municipalities)}"
            else:
                return "Error: Could not fetch available municipalities from Nehanda API. Is the server running?"

        logger.info(f"Detected municipality: {municipality}")

        # Make API request with municipality
        response = requests.post(
            api_url,
            json={"message": query, "municipality": municipality, "use_rag": True},
            timeout=timeout
        )
        response.raise_for_status()

        data = response.json()

        # Extract response and sources
        answer = data.get("response", "")
        sources = data.get("rag_sources", [])
        rag_used = data.get("rag_context_used", False)

        if not answer or not answer.strip():
            return "Error: Nehanda returned empty response"

        # Format response with sources
        formatted = [answer.strip()]

        if rag_used and sources:
            formatted.append("\n\n📚 Sources:")
            for source in sources:
                formatted.append(f"  - {source}")

        return "\n".join(formatted)

    except requests.ConnectionError:
        import config
        endpoint = config.NEHANDA.get("endpoint", "http://localhost:8000")
        if "localhost" in endpoint:
            return f"Error: Could not connect to Nehanda API at {endpoint}. Is the local API server running? Start it with: cd ~/Workbench/nehanda && python api/server.py"
        else:
            return f"Error: Could not connect to Nehanda API at {endpoint}. Check endpoint configuration with /models command."

    except requests.Timeout:
        return "Error: Nehanda API request timed out after 180 seconds. The model may be generating a very long response or LM Studio may be overloaded."

    except requests.HTTPError as e:
        return f"Error: Nehanda API error (HTTP {e.response.status_code}): {e.response.text}"

    except Exception as e:
        logger.error(f"Nehanda error: {e}")
        return f"Error: Failed to call Nehanda: {str(e)}"


# Backwards compatibility alias
use_energy_analyst = use_nehanda
