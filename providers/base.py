"""Abstract base class for LLM provider adapters."""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class BaseAdapter(ABC):
    """Abstract base class for LLM provider adapters."""
    
    @abstractmethod
    def chat_complete(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> Dict[str, Any]:
        """
        Send chat completion request.
        
        Args:
            messages: List of message dicts (OpenAI format)
            tools: Optional list of tool definitions (OpenAI format)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            
        Returns:
            Response dict in OpenAI format:
            {
                "choices": [{
                    "message": {
                        "content": "...",
                        "tool_calls": [...]
                    },
                    "finish_reason": "stop"
                }],
                "usage": {"prompt_tokens": 10, "completion_tokens": 20}
            }
        """
        pass
    
    @abstractmethod
    def list_models(self) -> List[str]:
        """
        List available models from this provider.
        
        Returns:
            List of model identifiers
        """
        pass
    
    @abstractmethod
    def chat_complete_stream(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ):
        """
        Stream chat completion response.
        
        **MUST NOT support tool calls during streaming.** If tools are provided,
        streaming MUST be disabled and fall back to non-streaming chat_complete().
        
        Yields:
            UTF-8 text chunks as plain strings (not structured objects).
            Each chunk is a partial completion of the assistant's response.
            Chunks are concatenated to form the full response.
        
        **Contract:**
        - Yields only text content (str), never tool calls
        - If tools parameter is not None, raise ValueError or fall back to non-streaming
        - Chunks are incremental (each chunk extends previous chunks)
        - Completion signaled by generator exhaustion (StopIteration); empty string chunks are optional and may be yielded but are not required
        """
        pass
