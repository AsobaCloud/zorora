"""LLM client for OpenAI-compatible chat completions API."""

import requests
from typing import List, Dict, Any, Optional

from config import API_URL, MODEL, MAX_TOKENS, TIMEOUT, TEMPERATURE, TOOL_CHOICE, PARALLEL_TOOL_CALLS


class LLMClient:
    """Client for interacting with LM Studio API (OpenAI-compatible)."""

    def __init__(
        self,
        api_url: str = API_URL,
        model: str = MODEL,
        max_tokens: int = MAX_TOKENS,
        timeout: int = TIMEOUT,
        temperature: float = TEMPERATURE,
        tool_choice: str = TOOL_CHOICE,
        parallel_tool_calls: bool = PARALLEL_TOOL_CALLS,
    ):
        self.api_url = api_url
        self.model = model
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.temperature = temperature
        self.tool_choice = tool_choice
        self.parallel_tool_calls = parallel_tool_calls

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
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = self.tool_choice
            payload["parallel_tool_calls"] = self.parallel_tool_calls

        import time

        max_retries = 3
        retry_delay = 1  # seconds

        for attempt in range(max_retries):
            try:
                response = requests.post(
                    self.api_url,
                    json=payload,
                    timeout=self.timeout,
                )
                response.raise_for_status()
                response_data = response.json()

                # Validate response structure
                if not self._validate_response(response_data):
                    raise RuntimeError(f"Invalid API response structure: {response_data}")

                return response_data

            except requests.Timeout:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                    continue
                raise RuntimeError(f"LLM API call timed out after {self.timeout}s (tried {max_retries} times). Is LM Studio running?")

            except requests.ConnectionError:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (2 ** attempt))
                    continue
                raise RuntimeError(f"Could not connect to LM Studio at {self.api_url} (tried {max_retries} times). Is the server running?")

            except requests.HTTPError as e:
                # Don't retry 4xx errors (client errors)
                if 400 <= e.response.status_code < 500:
                    raise RuntimeError(f"LLM API client error (HTTP {e.response.status_code}): {e.response.text}") from e
                # Retry 5xx errors (server errors)
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (2 ** attempt))
                    continue
                raise RuntimeError(f"LLM API server error (tried {max_retries} times): {e}") from e

            except requests.RequestException as e:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (2 ** attempt))
                    continue
                raise RuntimeError(f"LLM API call failed (tried {max_retries} times): {e}") from e

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

    def _validate_response(self, response: Dict[str, Any]) -> bool:
        """
        Validate OpenAI API response structure.

        Args:
            response: API response dict

        Returns:
            True if valid, False otherwise
        """
        # Check required top-level fields
        if "choices" not in response:
            return False
        if not isinstance(response["choices"], list):
            return False
        if len(response["choices"]) == 0:
            return False

        # Check choice structure
        choice = response["choices"][0]
        if "message" not in choice:
            return False
        if "finish_reason" not in choice:
            return False

        return True

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
