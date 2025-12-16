"""Conversation manager for maintaining conversation history and context."""

from typing import List, Dict, Any, Optional
import logging

from config import MAX_CONTEXT_MESSAGES

logger = logging.getLogger(__name__)


class ConversationManager:
    """Manages conversation history and context window."""

    def __init__(self, system_prompt: str):
        """
        Initialize conversation manager.

        Args:
            system_prompt: System prompt to initialize conversation
        """
        self.messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt}
        ]

    def add_user_message(self, content: str) -> None:
        """Add user message to conversation."""
        self.messages.append({"role": "user", "content": content})
        self._manage_context()

    def add_assistant_message(self, content: Optional[str] = None, tool_calls: Optional[List[Dict[str, Any]]] = None) -> None:
        """
        Add assistant message to conversation.

        Args:
            content: Text content (empty string "" if tool calls only, never None for final messages)
            tool_calls: List of tool call dicts
        """
        message: Dict[str, Any] = {"role": "assistant"}

        # Always include content field - OpenAI API requirement
        if content is not None:
            message["content"] = content
        elif tool_calls:
            # Per OpenAI spec: messages with tool_calls must have content (can be empty)
            message["content"] = ""
        else:
            # Message with neither content nor tool_calls - validation error
            raise ValueError("Assistant message must have either content or tool_calls")

        if tool_calls:
            message["tool_calls"] = tool_calls

        self.messages.append(message)
        self._manage_context()

    def add_tool_result(self, tool_call_id: str, name: str, content: str) -> None:
        """Add tool result to conversation."""
        self.messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "name": name,
            "content": content
        })
        self._manage_context()

    def get_messages(self) -> List[Dict[str, Any]]:
        """Get current conversation messages."""
        return self.messages.copy()

    def clear(self) -> None:
        """Clear conversation history (keeps system prompt)."""
        system_msg = self.messages[0]
        self.messages = [system_msg]
        logger.info("Conversation context cleared")

    def get_context_stats(self) -> Dict[str, Any]:
        """
        Get statistics about current context usage.

        Returns:
            Dict with message_count, estimated_tokens, max_messages
        """
        message_count = len(self.messages)

        # Estimate tokens (rough: 1 token ≈ 4 characters)
        total_chars = sum(
            len(str(msg.get("content", "")))
            for msg in self.messages
        )
        estimated_tokens = total_chars // 4

        return {
            "message_count": message_count,
            "estimated_tokens": estimated_tokens,
            "max_messages": MAX_CONTEXT_MESSAGES,
        }

    def _manage_context(self) -> None:
        """
        Manage context window to prevent overflow.

        Strategy: Keep system message + recent messages.
        If context exceeds limit, remove oldest non-system messages.
        """
        if MAX_CONTEXT_MESSAGES is None:
            return  # No limit

        if len(self.messages) <= MAX_CONTEXT_MESSAGES:
            return  # Within limit

        # Keep system message + recent messages
        removed_count = len(self.messages) - MAX_CONTEXT_MESSAGES
        logger.warning(f"Context limit reached: removing {removed_count} oldest messages (keeping {MAX_CONTEXT_MESSAGES})")

        system_msg = self.messages[0]
        recent_messages = self.messages[-(MAX_CONTEXT_MESSAGES - 1):]
        self.messages = [system_msg] + recent_messages
