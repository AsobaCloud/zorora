"""Adapter for Anthropic API (Claude)."""

import requests
import time
import json
import os
from typing import List, Dict, Any, Optional, Tuple
from providers.base import BaseAdapter


class AnthropicAdapter(BaseAdapter):
    """Adapter for Anthropic API (Claude)."""
    
    def __init__(
        self,
        api_key: str,
        model: str,
        timeout: int = 60,
        base_url: str = "https://api.anthropic.com/v1",
    ):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.base_url = base_url.rstrip("/")
        self.messages_url = f"{self.base_url}/messages"
    
    def _convert_messages_to_anthropic(
        self, messages: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """
        Convert OpenAI message format to Anthropic format.
        
        **System Message Handling:**
        - If multiple system messages are present, concatenate them with "\\n\\n"
        - Pass as single Anthropic "system" field (not in messages array)
        - If no system messages, system_content is None
        
        **Message Format:**
        - OpenAI "user" → Anthropic "user" (unchanged)
        - OpenAI "assistant" → Anthropic "assistant" (unchanged)
        - OpenAI "system" → Extracted to system_content (not in messages array)
        
        Returns:
            Tuple of (anthropic_messages, system_content)
        """
        anthropic_messages = []
        system_parts = []
        
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            
            if role == "system":
                system_parts.append(content)
            elif role == "user":
                anthropic_messages.append({
                    "role": "user",
                    "content": content,
                })
            elif role == "assistant":
                anthropic_messages.append({
                    "role": "assistant",
                    "content": content,
                })
        
        # Concatenate multiple system messages
        system_content = "\n\n".join(system_parts) if system_parts else None
        
        return anthropic_messages, system_content
    
    def _convert_tools_to_anthropic(
        self, tools: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Convert OpenAI tools format to Anthropic format."""
        anthropic_tools = []
        
        for tool in tools:
            if tool.get("type") == "function":
                func = tool["function"]
                anthropic_tools.append({
                    "name": func["name"],
                    "description": func["description"],
                    "input_schema": func["parameters"],
                })
        
        return anthropic_tools
    
    def _convert_response_to_openai(
        self, anthropic_response: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Convert Anthropic response format to OpenAI format.
        
        **Conversion Rules (MUST be deterministic):**
        
        1. **Content Blocks:**
           - Extract all "text" type blocks from Anthropic response
           - Concatenate text blocks with "\\n" separator
           - Set as OpenAI message "content" field
        
        2. **Tool Calls:**
           - Extract all "tool_use" type blocks from Anthropic response
           - Convert each tool_use block to OpenAI tool_call format
           - Collect all tool calls into single "tool_calls" array
           - Set in OpenAI message "tool_calls" field
        
        3. **Finish Reason:**
           - Map Anthropic "stop_reason" to OpenAI "finish_reason"
        
        4. **Usage:**
           - Extract "usage" from Anthropic response if present
           - Map to OpenAI format
        
        5. **Multiple Blocks:**
           - If response contains both text and tool_use blocks:
             - Text blocks → concatenated into "content"
             - Tool_use blocks → all collected into "tool_calls"
             - Both fields present in final message
        """
        # Extract content blocks
        content_parts = []
        tool_calls = []
        
        # Anthropic response structure: {"content": [{"type": "text", "text": "..."}, ...]}
        content_blocks = anthropic_response.get("content", [])
        
        for block in content_blocks:
            if block.get("type") == "text":
                content_parts.append(block.get("text", ""))
            elif block.get("type") == "tool_use":
                tool_calls.append({
                    "id": block.get("id", ""),
                    "type": "function",
                    "function": {
                        "name": block.get("name", ""),
                        "arguments": json.dumps(block.get("input", {}))
                    }
                })
        
        # Build OpenAI format message
        message = {
            "role": "assistant",
            "content": "\n".join(content_parts) if content_parts else None
        }
        
        if tool_calls:
            message["tool_calls"] = tool_calls
        
        # Map finish reason
        stop_reason = anthropic_response.get("stop_reason", "end_turn")
        finish_reason_map = {
            "end_turn": "stop",
            "max_tokens": "length",
            "tool_use": "tool_calls"
        }
        finish_reason = finish_reason_map.get(stop_reason, "stop")
        
        # Extract usage
        usage = anthropic_response.get("usage", {})
        openai_usage = {
            "prompt_tokens": usage.get("input_tokens", 0),
            "completion_tokens": usage.get("output_tokens", 0)
        }
        
        return {
            "choices": [{
                "message": message,
                "finish_reason": finish_reason
            }],
            "usage": openai_usage
        }
    
    def chat_complete(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> Dict[str, Any]:
        """Send chat completion request to Anthropic API."""
        anthropic_messages, system_content = self._convert_messages_to_anthropic(messages)
        
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": self.model,
            "messages": anthropic_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        
        if system_content:
            payload["system"] = system_content
        
        if tools:
            anthropic_tools = self._convert_tools_to_anthropic(tools)
            payload["tools"] = anthropic_tools
        
        # Retry policy: 3 retries (4 total attempts)
        # Retry on: network errors, HTTP 429, HTTP 5xx
        # Do NOT retry on: HTTP 4xx (except 429), auth errors
        max_retries = 3
        base_delay = 0.5  # Start at 500ms
        
        for attempt in range(max_retries + 1):
            try:
                response = requests.post(
                    self.messages_url,
                    json=payload,
                    headers=headers,
                    timeout=self.timeout,
                )
                response.raise_for_status()
                anthropic_data = response.json()
                
                # Convert to OpenAI format
                return self._convert_response_to_openai(anthropic_data)
                
            except requests.Timeout:
                if attempt < max_retries:
                    delay = base_delay * (2 ** attempt)
                    jitter = delay * 0.2 * (2 * (time.time() % 1) - 1)
                    time.sleep(delay + jitter)
                    continue
                raise RuntimeError(f"Anthropic API call timed out after {self.timeout}s (tried {max_retries + 1} times)")
                
            except requests.ConnectionError:
                if attempt < max_retries:
                    delay = base_delay * (2 ** attempt)
                    jitter = delay * 0.2 * (2 * (time.time() % 1) - 1)
                    time.sleep(delay + jitter)
                    continue
                raise RuntimeError(f"Could not connect to Anthropic API at {self.messages_url} (tried {max_retries + 1} times)")
                
            except requests.HTTPError as e:
                status_code = e.response.status_code
                # Don't retry 4xx errors (client errors) except 429
                if 400 <= status_code < 500 and status_code != 429:
                    raise RuntimeError(f"Anthropic API client error (HTTP {status_code}): {e.response.text}") from e
                # Retry 429 (rate limit) and 5xx errors (server errors)
                if attempt < max_retries:
                    delay = base_delay * (2 ** attempt)
                    jitter = delay * 0.2 * (2 * (time.time() % 1) - 1)
                    time.sleep(delay + jitter)
                    continue
                raise RuntimeError(f"Anthropic API server error (HTTP {status_code}, tried {max_retries + 1} times): {e}") from e
                
            except requests.RequestException as e:
                if attempt < max_retries:
                    delay = base_delay * (2 ** attempt)
                    jitter = delay * 0.2 * (2 * (time.time() % 1) - 1)
                    time.sleep(delay + jitter)
                    continue
                raise RuntimeError(f"Anthropic API call failed (tried {max_retries + 1} times): {e}") from e
    
    def list_models(self) -> List[str]:
        """List available Anthropic models (from configured ANTHROPIC_ENDPOINTS dict)."""
        # Anthropic doesn't provide models API
        # Return models from configured ANTHROPIC_ENDPOINTS
        import config
        if hasattr(config, 'ANTHROPIC_ENDPOINTS'):
            return list(config.ANTHROPIC_ENDPOINTS.keys())
        return []
    
    def chat_complete_stream(self, messages, tools=None):
        """
        Stream chat completion from Anthropic API.
        
        **MUST NOT support tool calls during streaming.** If tools parameter
        is not None, MUST raise ValueError.
        """
        if tools is not None:
            raise ValueError("Tool calls are not supported during streaming. Use chat_complete() instead.")
        
        anthropic_messages, system_content = self._convert_messages_to_anthropic(messages)
        
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": self.model,
            "messages": anthropic_messages,
            "stream": True,
        }
        
        if system_content:
            payload["system"] = system_content
        
        try:
            response = requests.post(
                self.messages_url,
                json=payload,
                headers=headers,
                timeout=self.timeout,
                stream=True,
            )
            response.raise_for_status()
            
            # Process Anthropic SSE stream
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
                    chunk = json.loads(line)
                    
                    # Extract text content from Anthropic stream format
                    if chunk.get("type") == "content_block_delta":
                        delta = chunk.get("delta", {})
                        if delta.get("type") == "text_delta":
                            text = delta.get("text", "")
                            if text:
                                yield text
                                
                except json.JSONDecodeError:
                    continue
                    
        except requests.Timeout:
            raise RuntimeError(f"Anthropic API streaming timed out after {self.timeout}s")
        except requests.ConnectionError:
            raise RuntimeError(f"Could not connect to Anthropic API at {self.messages_url}")
        except requests.HTTPError as e:
            raise RuntimeError(f"Anthropic API error (HTTP {e.response.status_code}): {e.response.text}") from e
        except requests.RequestException as e:
            raise RuntimeError(f"Anthropic API streaming failed: {e}") from e
