"""Adapter for OpenAI-compatible APIs (LM Studio and HuggingFace endpoints)."""

import requests
import time
from typing import List, Dict, Any, Optional
from providers.base import BaseAdapter


class OpenAICompatibleAdapter(BaseAdapter):
    """Adapter for OpenAI-compatible APIs (LM Studio, HuggingFace Inference Endpoints)."""
    
    def __init__(
        self,
        api_url: str,
        model: str,
        max_tokens: int = 2048,
        timeout: int = 60,
        temperature: float = 0.7,
        tool_choice: str = "auto",
        parallel_tool_calls: bool = True,
        auth_token: Optional[str] = None,
    ):
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
        temperature: float = None,
        max_tokens: int = None,
    ) -> Dict[str, Any]:
        """
        Send chat completion request to OpenAI-compatible API.
        
        Uses instance temperature/max_tokens if not provided.
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.temperature,
            "max_tokens": max_tokens if max_tokens is not None else self.max_tokens,
        }

        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = self.tool_choice
            payload["parallel_tool_calls"] = self.parallel_tool_calls

        # Retry policy: 3 retries (4 total attempts)
        # Retry on: network errors, HTTP 429, HTTP 5xx
        # Do NOT retry on: HTTP 4xx (except 429), auth errors
        max_retries = 3
        base_delay = 0.5  # Start at 500ms

        # Prepare headers
        headers = {}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"

        for attempt in range(max_retries + 1):
            try:
                response = requests.post(
                    self.api_url,
                    json=payload,
                    headers=headers,
                    timeout=self.timeout,
                )
                response.raise_for_status()
                response_data = response.json()

                # Validate response structure
                if not self._validate_response(response_data):
                    raise RuntimeError(f"Invalid API response structure: {response_data}")

                return response_data

            except requests.Timeout:
                if attempt < max_retries:
                    # Exponential backoff with jitter (±20%)
                    delay = base_delay * (2 ** attempt)
                    jitter = delay * 0.2 * (2 * (time.time() % 1) - 1)  # ±20% random
                    time.sleep(delay + jitter)
                    continue
                raise RuntimeError(f"LLM API call timed out after {self.timeout}s (tried {max_retries + 1} times).")

            except requests.ConnectionError:
                if attempt < max_retries:
                    delay = base_delay * (2 ** attempt)
                    jitter = delay * 0.2 * (2 * (time.time() % 1) - 1)
                    time.sleep(delay + jitter)
                    continue
                raise RuntimeError(f"Could not connect to API at {self.api_url} (tried {max_retries + 1} times).")

            except requests.HTTPError as e:
                status_code = e.response.status_code
                # Don't retry 4xx errors (client errors) except 429
                if 400 <= status_code < 500 and status_code != 429:
                    raise RuntimeError(f"LLM API client error (HTTP {status_code}): {e.response.text}") from e
                # Retry 429 (rate limit) and 5xx errors (server errors)
                if attempt < max_retries:
                    delay = base_delay * (2 ** attempt)
                    jitter = delay * 0.2 * (2 * (time.time() % 1) - 1)
                    time.sleep(delay + jitter)
                    continue
                raise RuntimeError(f"LLM API server error (HTTP {status_code}, tried {max_retries + 1} times): {e}") from e

            except requests.RequestException as e:
                if attempt < max_retries:
                    delay = base_delay * (2 ** attempt)
                    jitter = delay * 0.2 * (2 * (time.time() % 1) - 1)
                    time.sleep(delay + jitter)
                    continue
                raise RuntimeError(f"LLM API call failed (tried {max_retries + 1} times): {e}") from e
    
    def list_models(self) -> List[str]:
        """List available models from OpenAI-compatible API."""
        # Convert chat/completions URL to models endpoint
        models_url = self.api_url.replace("/chat/completions", "/models")

        # Prepare headers
        headers = {}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"

        try:
            response = requests.get(models_url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()

            # OpenAI format: {"data": [{"id": "model-name"}, ...]}
            if "data" in data and isinstance(data["data"], list):
                return [model["id"] for model in data["data"] if "id" in model]

            return []

        except requests.RequestException as e:
            raise RuntimeError(f"Failed to fetch models: {e}") from e
    
    def chat_complete_stream(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ):
        """
        Stream chat completion from OpenAI-compatible API.
        
        **MUST NOT support tool calls during streaming.** If tools are provided,
        raises ValueError.
        """
        if tools is not None:
            raise ValueError("Tool calls are not supported during streaming. Use chat_complete() instead.")
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": True,
        }

        # Prepare headers
        headers = {}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"

        try:
            response = requests.post(
                self.api_url,
                json=payload,
                headers=headers,
                timeout=self.timeout,
                stream=True,
            )
            response.raise_for_status()

            # Process SSE stream
            for line in response.iter_lines():
                if not line:
                    continue

                line = line.decode('utf-8')

                # Skip SSE prefix
                if line.startswith('data: '):
                    line = line[6:]  # Remove 'data: ' prefix

                # Check for stream end
                if line == '[DONE]':
                    break

                try:
                    import json
                    chunk = json.loads(line)

                    # Extract content delta from chunk
                    if 'choices' in chunk and len(chunk['choices']) > 0:
                        delta = chunk['choices'][0].get('delta', {})
                        content = delta.get('content', '')
                        if content:
                            yield content

                except json.JSONDecodeError:
                    continue

        except requests.Timeout:
            raise RuntimeError(f"LLM API streaming timed out after {self.timeout}s")
        except requests.ConnectionError:
            raise RuntimeError(f"Could not connect to API at {self.api_url}")
        except requests.HTTPError as e:
            raise RuntimeError(f"LLM API error (HTTP {e.response.status_code}): {e.response.text}") from e
        except requests.RequestException as e:
            raise RuntimeError(f"LLM API streaming failed: {e}") from e
    
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
