"""Adapter for HuggingFace Inference Toolkit endpoints (native format)."""

import json
import logging
import requests
import time
from typing import List, Dict, Any, Optional

from providers.base import BaseAdapter

logger = logging.getLogger(__name__)


class HuggingFaceAdapter(BaseAdapter):
    """Adapter for HF Inference Toolkit endpoints that use {"inputs": ...} format."""

    def __init__(
        self,
        api_url: str,
        model: str,
        auth_token: str,
        timeout: int = 120,
        chat_template: str = "mistral",
    ):
        self.api_url = api_url.rstrip("/")
        self.model = model
        self.auth_token = auth_token
        self.timeout = timeout
        self.chat_template = chat_template

    def _format_prompt(self, messages: List[Dict[str, Any]]) -> str:
        """Convert chat messages to a single prompt string using the configured template."""
        formatter = {
            "mistral": self._format_mistral,
            "chatml": self._format_chatml,
            "alpaca": self._format_alpaca,
            "raw": self._format_raw,
        }.get(self.chat_template, self._format_mistral)
        return formatter(messages)

    def _format_mistral(self, messages: List[Dict[str, Any]]) -> str:
        """Mistral instruct format: <s>[INST] ... [/INST]"""
        system_parts = []
        conversation = []

        for msg in messages:
            if msg["role"] == "system":
                system_parts.append(msg["content"])
            else:
                conversation.append(msg)

        parts = []
        system_text = "\n\n".join(system_parts) if system_parts else ""

        for i, msg in enumerate(conversation):
            if msg["role"] == "user":
                user_content = msg["content"]
                if i == 0 and system_text:
                    user_content = f"{system_text}\n\n{user_content}"
                parts.append(f"<s>[INST] {user_content} [/INST]")
            elif msg["role"] == "assistant":
                parts.append(f"{msg['content']}</s>")

        return "".join(parts)

    def _format_chatml(self, messages: List[Dict[str, Any]]) -> str:
        """ChatML format: <|im_start|>role\\n...<|im_end|>"""
        parts = []
        for msg in messages:
            parts.append(f"<|im_start|>{msg['role']}\n{msg['content']}<|im_end|>")
        parts.append("<|im_start|>assistant\n")
        return "\n".join(parts)

    def _format_alpaca(self, messages: List[Dict[str, Any]]) -> str:
        """Alpaca format: ### Instruction:\\n...\\n\\n### Response:\\n"""
        system_parts = []
        user_parts = []

        for msg in messages:
            if msg["role"] == "system":
                system_parts.append(msg["content"])
            elif msg["role"] == "user":
                user_parts.append(msg["content"])

        parts = []
        if system_parts:
            parts.append("\n\n".join(system_parts))
            parts.append("")
        parts.append(f"### Instruction:\n{user_parts[-1] if user_parts else ''}")
        parts.append("\n### Response:\n")
        return "\n".join(parts)

    def _format_raw(self, messages: List[Dict[str, Any]]) -> str:
        """Simple concatenation: Role: content"""
        parts = []
        role_map = {"system": "System", "user": "User", "assistant": "Assistant"}
        for msg in messages:
            label = role_map.get(msg["role"], msg["role"].capitalize())
            parts.append(f"{label}: {msg['content']}")
        parts.append("Assistant:")
        return "\n".join(parts)

    def chat_complete(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> Dict[str, Any]:
        """Send completion request to HF Inference Toolkit endpoint."""
        if tools:
            logger.warning("Tool calls not supported on HF Inference Toolkit — ignoring tools parameter")

        prompt = self._format_prompt(messages)

        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": max_tokens,
                "temperature": temperature,
                "return_full_text": False,
            },
        }

        headers = {
            "Authorization": f"Bearer {self.auth_token}",
            "Content-Type": "application/json",
        }

        # Retry policy: 3 retries (4 total attempts)
        max_retries = 3
        base_delay = 0.5

        for attempt in range(max_retries + 1):
            try:
                response = requests.post(
                    self.api_url,
                    json=payload,
                    headers=headers,
                    timeout=self.timeout,
                )
                response.raise_for_status()
                hf_data = response.json()

                return self._convert_response(hf_data)

            except requests.Timeout:
                if attempt < max_retries:
                    delay = base_delay * (2 ** attempt)
                    jitter = delay * 0.2 * (2 * (time.time() % 1) - 1)
                    time.sleep(delay + jitter)
                    continue
                raise RuntimeError(
                    f"HF Inference API timed out after {self.timeout}s (tried {max_retries + 1} times)"
                )

            except requests.ConnectionError:
                if attempt < max_retries:
                    delay = base_delay * (2 ** attempt)
                    jitter = delay * 0.2 * (2 * (time.time() % 1) - 1)
                    time.sleep(delay + jitter)
                    continue
                raise RuntimeError(
                    f"Could not connect to HF endpoint at {self.api_url} (tried {max_retries + 1} times)"
                )

            except requests.HTTPError as e:
                status_code = e.response.status_code
                if 400 <= status_code < 500 and status_code != 429:
                    raise RuntimeError(
                        f"HF Inference API client error (HTTP {status_code}): {e.response.text}"
                    ) from e
                if attempt < max_retries:
                    delay = base_delay * (2 ** attempt)
                    jitter = delay * 0.2 * (2 * (time.time() % 1) - 1)
                    time.sleep(delay + jitter)
                    continue
                raise RuntimeError(
                    f"HF Inference API server error (HTTP {status_code}, tried {max_retries + 1} times): {e}"
                ) from e

            except requests.RequestException as e:
                if attempt < max_retries:
                    delay = base_delay * (2 ** attempt)
                    jitter = delay * 0.2 * (2 * (time.time() % 1) - 1)
                    time.sleep(delay + jitter)
                    continue
                raise RuntimeError(
                    f"HF Inference API call failed (tried {max_retries + 1} times): {e}"
                ) from e

    def _convert_response(self, hf_data: Any) -> Dict[str, Any]:
        """Convert HF Inference Toolkit response to OpenAI format.

        HF returns either:
        - List: [{"generated_text": "..."}]
        - Dict: {"generated_text": "..."} or {"error": "..."}
        """
        generated_text = ""

        if isinstance(hf_data, list) and len(hf_data) > 0:
            generated_text = hf_data[0].get("generated_text", "")
        elif isinstance(hf_data, dict):
            if "error" in hf_data:
                raise RuntimeError(f"HF Inference API error: {hf_data['error']}")
            generated_text = hf_data.get("generated_text", "")

        return {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": generated_text,
                },
                "finish_reason": "stop",
            }],
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
            },
        }

    def chat_complete_stream(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ):
        """Stream completion from HF Inference Toolkit endpoint."""
        if tools is not None:
            raise ValueError("Tool calls are not supported during streaming. Use chat_complete() instead.")

        prompt = self._format_prompt(messages)

        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": 2048,
                "return_full_text": False,
            },
            "stream": True,
        }

        headers = {
            "Authorization": f"Bearer {self.auth_token}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(
                self.api_url,
                json=payload,
                headers=headers,
                timeout=self.timeout,
                stream=True,
            )
            response.raise_for_status()

            for line in response.iter_lines():
                if not line:
                    continue

                line = line.decode("utf-8")

                if line.startswith("data:"):
                    line = line[5:].strip()

                if not line or line == "[DONE]":
                    continue

                try:
                    chunk = json.loads(line)
                    # HF streaming format: {"token": {"text": "..."}}
                    token = chunk.get("token", {})
                    text = token.get("text", "")
                    if text:
                        yield text
                except json.JSONDecodeError:
                    continue

        except requests.Timeout:
            raise RuntimeError(f"HF Inference API streaming timed out after {self.timeout}s")
        except requests.ConnectionError:
            raise RuntimeError(f"Could not connect to HF endpoint at {self.api_url}")
        except requests.HTTPError as e:
            raise RuntimeError(
                f"HF Inference API error (HTTP {e.response.status_code}): {e.response.text}"
            ) from e
        except requests.RequestException as e:
            raise RuntimeError(f"HF Inference API streaming failed: {e}") from e

    def list_models(self) -> List[str]:
        """Return configured model (HF Inference Toolkit has no models endpoint)."""
        return [self.model]
