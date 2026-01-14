"""
Reasoning model tool for complex analysis and planning.
"""

import logging
from tools.specialist.client import create_specialist_client

logger = logging.getLogger(__name__)


def use_reasoning_model(task: str) -> str:
    """
    Plan or reason about complex tasks using Ministral-3-14B-Reasoning model.

    Args:
        task: Planning task, architectural decision, or complex reasoning problem

    Returns:
        Detailed plan or reasoning steps
    """
    if not task or not isinstance(task, str):
        return "Error: task must be a non-empty string"

    if len(task) > 30000:
        return "Error: task too long (max 30000 characters)"

    try:
        import config

        logger.info(f"Delegating to Reasoning model: {task[:100]}...")

        model_config = config.SPECIALIZED_MODELS["reasoning"]
        client = create_specialist_client("reasoning", model_config)

        messages = [
            {
                "role": "system",
                "content": "You are a logical reasoning and planning expert. Break down complex problems into clear, actionable steps. Consider edge cases and trade-offs."
            },
            {
                "role": "user",
                "content": task
            }
        ]

        # Stream the response for real-time feedback
        print("\n", flush=True)  # New line before streaming
        full_response = []

        for chunk in client.chat_complete_stream(messages):
            print(chunk, end='', flush=True)
            full_response.append(chunk)

        print("\n", flush=True)  # New line after streaming

        content = ''.join(full_response)
        if not content or not content.strip():
            return "Error: Reasoning model returned empty response"

        return content.strip()

    except Exception as e:
        logger.error(f"Reasoning model error: {e}")
        return f"Error: Failed to call Reasoning model: {str(e)}"
