"""Conversation manager for maintaining conversation history and context."""

from typing import List, Dict, Any, Optional
import logging
from datetime import datetime

from config import MAX_CONTEXT_MESSAGES, ENABLE_CONTEXT_SUMMARIZATION, CONTEXT_KEEP_RECENT

logger = logging.getLogger(__name__)


class ConversationManager:
    """Manages conversation history and context window."""

    def __init__(
        self,
        system_prompt: str,
        session_id: Optional[str] = None,
        persistence = None,
        auto_save: bool = True,
        tool_executor = None
    ):
        """
        Initialize conversation manager.

        Args:
            system_prompt: System prompt to initialize conversation
            session_id: Optional session identifier for persistence
            persistence: Optional ConversationPersistence instance
            auto_save: Whether to auto-save after each message
            tool_executor: Optional ToolExecutor for context summarization
        """
        self.messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt}
        ]
        self.session_id = session_id or self._generate_session_id()
        self.persistence = persistence
        self.auto_save_enabled = auto_save
        self.tool_executor = tool_executor
        self.metadata = {
            "start_time": datetime.now().isoformat(),
        }

    def _generate_session_id(self) -> str:
        """Generate a unique session ID based on timestamp."""
        return f"session_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"

    def add_user_message(self, content: str) -> None:
        """Add user message to conversation."""
        self.messages.append({"role": "user", "content": content})
        self._manage_context()
        self._auto_save()

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
        self._auto_save()

    def add_tool_result(self, tool_call_id: str, name: str, content: str) -> None:
        """Add tool result to conversation."""
        self.messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "name": name,
            "content": content
        })
        self._manage_context()
        self._auto_save()

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

    def _summarize_conversation(self, messages_to_summarize: List[Dict[str, Any]]) -> str:
        """
        Create a summary of old messages using the reasoning model.

        Args:
            messages_to_summarize: List of message dicts to summarize

        Returns:
            Summary text
        """
        if not self.tool_executor:
            logger.warning("No tool_executor available for summarization, using fallback")
            return "[Previous conversation context unavailable]"

        try:
            # Format messages for summarization
            formatted_messages = []
            for msg in messages_to_summarize:
                role = msg.get("role", "unknown")
                content = msg.get("content", "")

                # Skip empty messages
                if not content or content == "":
                    continue

                # Truncate very long messages
                if len(content) > 1000:
                    content = content[:1000] + "..."

                formatted_messages.append(f"{role.upper()}: {content}")

            conversation_text = "\n\n".join(formatted_messages)

            # Call reasoning model to create summary
            summary_prompt = f"""Summarize the following conversation history concisely. Focus on:
- Key decisions made
- Important facts or context established
- Files created/modified
- Tools used and their results

Keep the summary under 500 words.

Conversation to summarize:
{conversation_text}

Provide a concise summary:"""

            logger.info(f"Creating summary of {len(messages_to_summarize)} messages...")
            summary = self.tool_executor.execute("use_reasoning_model", {"task": summary_prompt})

            # Clean up the summary
            summary = summary.strip()
            if len(summary) > 2000:
                summary = summary[:2000] + "..."

            logger.info(f"Created summary: {len(summary)} chars")
            return summary

        except Exception as e:
            logger.error(f"Summarization failed: {e}")
            return "[Conversation summary unavailable due to error]"

    def _manage_context(self) -> None:
        """
        Manage context window to prevent overflow.

        Strategy with summarization enabled:
        - When limit is reached, summarize oldest messages
        - Keep system message + summary + recent messages

        Fallback strategy (no summarization):
        - Keep system message + recent messages
        - Remove oldest non-system messages
        """
        if MAX_CONTEXT_MESSAGES is None:
            return  # No limit

        if len(self.messages) <= MAX_CONTEXT_MESSAGES:
            return  # Within limit

        logger.warning(f"Context limit reached: {len(self.messages)} messages (limit: {MAX_CONTEXT_MESSAGES})")

        # Use summarization if enabled and available
        if ENABLE_CONTEXT_SUMMARIZATION and self.tool_executor:
            try:
                system_msg = self.messages[0]

                # Check if we already have a summary
                has_summary = len(self.messages) > 1 and "Previous conversation summary:" in str(self.messages[1].get("content", ""))

                if has_summary:
                    # Already have a summary - append to it
                    old_summary = self.messages[1]
                    messages_to_summarize = self.messages[2:-(CONTEXT_KEEP_RECENT)]
                    recent_messages = self.messages[-(CONTEXT_KEEP_RECENT):]

                    logger.info(f"Appending to existing summary: summarizing {len(messages_to_summarize)} messages")
                    new_summary_text = self._summarize_conversation(messages_to_summarize)

                    # Combine summaries
                    combined_summary = f"{old_summary['content']}\n\n[Additional context:]\n{new_summary_text}"
                    summary_message = {"role": "user", "content": combined_summary}

                    self.messages = [system_msg, summary_message] + recent_messages
                else:
                    # First summarization
                    messages_to_summarize = self.messages[1:-(CONTEXT_KEEP_RECENT)]
                    recent_messages = self.messages[-(CONTEXT_KEEP_RECENT):]

                    logger.info(f"Creating first summary: summarizing {len(messages_to_summarize)} messages, keeping {len(recent_messages)} recent")
                    summary_text = self._summarize_conversation(messages_to_summarize)

                    summary_message = {"role": "user", "content": f"[Previous conversation summary: {summary_text}]"}

                    self.messages = [system_msg, summary_message] + recent_messages

                logger.info(f"Context managed with summarization: now {len(self.messages)} messages")
                return

            except Exception as e:
                logger.error(f"Context summarization failed: {e}, falling back to FIFO")
                # Fall through to FIFO fallback

        # Fallback: Simple FIFO
        removed_count = len(self.messages) - MAX_CONTEXT_MESSAGES
        logger.warning(f"Using FIFO fallback: removing {removed_count} oldest messages")

        system_msg = self.messages[0]
        recent_messages = self.messages[-(MAX_CONTEXT_MESSAGES - 1):]
        self.messages = [system_msg] + recent_messages

    def _auto_save(self) -> None:
        """Auto-save conversation if persistence is enabled."""
        if not self.auto_save_enabled or not self.persistence:
            return

        try:
            self.persistence.save_conversation(
                session_id=self.session_id,
                messages=self.messages,
                metadata=self.metadata
            )
        except Exception as e:
            logger.error(f"Auto-save failed: {e}")

    def load_from_session(self, session_id: str) -> bool:
        """
        Load conversation from a saved session.

        Args:
            session_id: Session identifier to load

        Returns:
            True if loaded successfully, False otherwise
        """
        if not self.persistence:
            logger.error("Cannot load session: persistence not enabled")
            return False

        data = self.persistence.load_conversation(session_id)
        if not data:
            logger.error(f"Failed to load session: {session_id}")
            return False

        self.messages = data.get("messages", [])
        self.session_id = data.get("session_id", session_id)
        self.metadata = data.get("metadata", {})

        logger.info(f"Loaded session {session_id} with {len(self.messages)} messages")
        return True
