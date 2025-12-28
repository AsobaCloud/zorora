"""LLM client for OpenAI-compatible chat completions API."""

from typing import List, Dict, Any, Optional

from config import API_URL, MODEL, MAX_TOKENS, TIMEOUT, TEMPERATURE, TOOL_CHOICE, PARALLEL_TOOL_CALLS
from providers.openai_compatible_adapter import OpenAICompatibleAdapter


class LLMClient:
    """Client for interacting with LM Studio API or HuggingFace endpoints (OpenAI-compatible)."""

    def __init__(
        self,
        api_url: str = API_URL,
        model: str = MODEL,
        max_tokens: int = MAX_TOKENS,
        timeout: int = TIMEOUT,
        temperature: float = TEMPERATURE,
        tool_choice: str = TOOL_CHOICE,
        parallel_tool_calls: bool = PARALLEL_TOOL_CALLS,
        auth_token: Optional[str] = None,
    ):
        # Use adapter internally (Phase 1: refactoring, no behavior change)
        self.adapter = OpenAICompatibleAdapter(
            api_url=api_url,
            model=model,
            max_tokens=max_tokens,
            timeout=timeout,
            temperature=temperature,
            tool_choice=tool_choice,
            parallel_tool_calls=parallel_tool_calls,
            auth_token=auth_token,
        )
        # Maintain backward compatibility - expose these attributes
        self.api_url = api_url
        self.model = model
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.temperature = temperature
        self.tool_choice = tool_choice
        self.parallel_tool_calls = parallel_tool_calls
        self.auth_token = auth_token

    def chat_complete(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Send chat completion request to LLM.

        Args:
            messages: List of message dicts with 'role' and 'content'
            tools: Optional list of tool definitions

        Returns:
            Full API response as dict

        Raises:
            RuntimeError: If API call fails
        """
        return self.adapter.chat_complete(messages, tools, self.temperature, self.max_tokens)

    def extract_tool_calls(self, response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract tool calls from API response.

        Args:
            response: Full API response dict

        Returns:
            List of tool call dicts
        """
        if "choices" not in response or len(response["choices"]) == 0:
            return []

        choice = response["choices"][0]
        if "message" not in choice:
            return []

        message = choice["message"]
        return message.get("tool_calls", [])

    def extract_content(self, response: Dict[str, Any]) -> Optional[str]:
        """
        Extract text content from assistant message.

        Args:
            response: Full API response dict

        Returns:
            Message content string or None
        """
        if "choices" not in response or len(response["choices"]) == 0:
            return None

        choice = response["choices"][0]
        if "message" not in choice:
            return None

        message = choice["message"]
        return message.get("content")


    def extract_finish_reason(self, response: Dict[str, Any]) -> Optional[str]:
        """
        Extract finish_reason from API response.

        Args:
            response: Full API response dict

        Returns:
            finish_reason string or None
        """
        if "choices" not in response or len(response["choices"]) == 0:
            return None

        choice = response["choices"][0]
        return choice.get("finish_reason")

    def chat_complete_stream(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ):
        """
        Stream chat completion response from LLM (generator).

        Args:
            messages: List of message dicts with 'role' and 'content'
            tools: Optional list of tool definitions

        Yields:
            Chunks of response content as they arrive

        Raises:
            RuntimeError: If API call fails
        """
        yield from self.adapter.chat_complete_stream(messages, tools)

    def list_models(self) -> List[str]:
        """
        List available models from LM Studio or HF endpoint.

        Returns:
            List of model IDs

        Raises:
            RuntimeError: If API call fails
        """
        return self.adapter.list_models()
