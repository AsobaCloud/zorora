"""Adapter for OpenAI API (ChatGPT)."""

import requests
import time
import os
from typing import List, Dict, Any, Optional
from providers.base import BaseAdapter


class OpenAIAdapter(BaseAdapter):
    """Adapter for OpenAI API (ChatGPT)."""
    
    def __init__(
        self,
        api_key: str,
        model: str,
        timeout: int = 60,
        base_url: str = "https://api.openai.com/v1",
    ):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.base_url = base_url.rstrip("/")
        self.chat_url = f"{self.base_url}/chat/completions"
    
    def chat_complete(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> Dict[str, Any]:
        """Send chat completion request to OpenAI API."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        
        # Retry policy: 3 retries (4 total attempts)
        # Retry on: network errors, HTTP 429, HTTP 5xx
        # Do NOT retry on: HTTP 4xx (except 429), auth errors
        max_retries = 3
        base_delay = 0.5  # Start at 500ms
        
        for attempt in range(max_retries + 1):
            try:
                response = requests.post(
                    self.chat_url,
                    json=payload,
                    headers=headers,
                    timeout=self.timeout,
                )
                response.raise_for_status()
                return response.json()
                
            except requests.Timeout:
                if attempt < max_retries:
                    delay = base_delay * (2 ** attempt)
                    jitter = delay * 0.2 * (2 * (time.time() % 1) - 1)
                    time.sleep(delay + jitter)
                    continue
                raise RuntimeError(f"OpenAI API call timed out after {self.timeout}s (tried {max_retries + 1} times)")
                
            except requests.ConnectionError:
                if attempt < max_retries:
                    delay = base_delay * (2 ** attempt)
                    jitter = delay * 0.2 * (2 * (time.time() % 1) - 1)
                    time.sleep(delay + jitter)
                    continue
                raise RuntimeError(f"Could not connect to OpenAI API at {self.chat_url} (tried {max_retries + 1} times)")
                
            except requests.HTTPError as e:
                status_code = e.response.status_code
                # Don't retry 4xx errors (client errors) except 429
                if 400 <= status_code < 500 and status_code != 429:
                    raise RuntimeError(f"OpenAI API client error (HTTP {status_code}): {e.response.text}") from e
                # Retry 429 (rate limit) and 5xx errors (server errors)
                if attempt < max_retries:
                    delay = base_delay * (2 ** attempt)
                    jitter = delay * 0.2 * (2 * (time.time() % 1) - 1)
                    time.sleep(delay + jitter)
                    continue
                raise RuntimeError(f"OpenAI API server error (HTTP {status_code}, tried {max_retries + 1} times): {e}") from e
                
            except requests.RequestException as e:
                if attempt < max_retries:
                    delay = base_delay * (2 ** attempt)
                    jitter = delay * 0.2 * (2 * (time.time() % 1) - 1)
                    time.sleep(delay + jitter)
                    continue
                raise RuntimeError(f"OpenAI API call failed (tried {max_retries + 1} times): {e}") from e
    
    def list_models(self) -> List[str]:
        """List available OpenAI models (from configured OPENAI_ENDPOINTS dict)."""
        # Note: We use configured dicts for consistency with HF_ENDPOINTS pattern
        # Users configure which OpenAI models they want to use in OPENAI_ENDPOINTS
        import config
        if hasattr(config, 'OPENAI_ENDPOINTS'):
            return list(config.OPENAI_ENDPOINTS.keys())
        return []
    
    def chat_complete_stream(self, messages, tools=None):
        """
        Stream chat completion from OpenAI API.
        
        **MUST NOT support tool calls during streaming.** If tools parameter
        is not None, MUST raise ValueError.
        """
        if tools is not None:
            raise ValueError("Tool calls are not supported during streaming. Use chat_complete() instead.")
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
        }
        
        try:
            response = requests.post(
                self.chat_url,
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
                    line = line[6:]
                
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
            raise RuntimeError(f"OpenAI API streaming timed out after {self.timeout}s")
        except requests.ConnectionError:
            raise RuntimeError(f"Could not connect to OpenAI API at {self.chat_url}")
        except requests.HTTPError as e:
            raise RuntimeError(f"OpenAI API error (HTTP {e.response.status_code}): {e.response.text}") from e
        except requests.RequestException as e:
            raise RuntimeError(f"OpenAI API streaming failed: {e}") from e
