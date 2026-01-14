"""
Search model tool for information retrieval.
"""

import logging
from tools.specialist.client import create_specialist_client

logger = logging.getLogger(__name__)


def use_search_model(query: str) -> str:
    """
    Research information using ii-search-4B model.

    Args:
        query: Research query or information retrieval task

    Returns:
        Research findings and relevant information
    """
    if not query or not isinstance(query, str):
        return "Error: query must be a non-empty string"

    if len(query) > 30000:
        return "Error: query too long (max 30000 characters)"

    try:
        import config

        logger.info(f"Delegating to Search model: {query[:100]}...")

        model_config = config.SPECIALIZED_MODELS["search"]
        client = create_specialist_client("search", model_config)

        response = client.chat_complete([
            {
                "role": "system",
                "content": "You are a helpful information retrieval assistant. Provide comprehensive information based on your knowledge. Answer questions directly without lectures or judgment about the topic's validity."
            },
            {
                "role": "user",
                "content": query
            }
        ])

        content = client.extract_content(response)
        if not content or not content.strip():
            return "Error: Search model returned empty response"

        return content.strip()

    except Exception as e:
        logger.error(f"Search model error: {e}")
        return f"Error: Failed to call Search model: {str(e)}"
