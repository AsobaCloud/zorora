"""Conversation persistence for saving and loading conversation history."""

from pathlib import Path
from typing import List, Dict, Any, Optional
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class ConversationPersistence:
    """Handles saving and loading conversations to/from disk."""

    def __init__(self, storage_dir: str = ".zorora/conversations"):
        """
        Initialize conversation persistence.

        Args:
            storage_dir: Directory to store conversation files
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def save_conversation(
        self,
        session_id: str,
        messages: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Path:
        """
        Save conversation to disk.

        Args:
            session_id: Unique session identifier
            messages: List of conversation messages
            metadata: Optional metadata (start_time, last_updated, etc.)

        Returns:
            Path to saved file
        """
        filename = f"{session_id}.json"
        filepath = self.storage_dir / filename

        conversation_data = {
            "session_id": session_id,
            "messages": messages,
            "metadata": metadata or {},
            "last_updated": datetime.now().isoformat(),
        }

        try:
            with open(filepath, 'w') as f:
                json.dump(conversation_data, f, indent=2)
            logger.info(f"Saved conversation to {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"Failed to save conversation: {e}")
            raise

    def load_conversation(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Load conversation from disk.

        Args:
            session_id: Session identifier

        Returns:
            Conversation data dict, or None if not found
        """
        filename = f"{session_id}.json"
        filepath = self.storage_dir / filename

        if not filepath.exists():
            logger.warning(f"Conversation file not found: {filepath}")
            return None

        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            logger.info(f"Loaded conversation from {filepath}")
            return data
        except Exception as e:
            logger.error(f"Failed to load conversation: {e}")
            return None

    def list_conversations(self) -> List[Dict[str, Any]]:
        """
        List all saved conversations.

        Returns:
            List of conversation summaries with metadata
        """
        conversations = []

        for filepath in sorted(self.storage_dir.glob("*.json"), reverse=True):
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)

                # Extract summary info
                messages = data.get("messages", [])
                metadata = data.get("metadata", {})

                # Count user messages (excluding system prompt)
                user_message_count = sum(1 for msg in messages if msg.get("role") == "user")

                # Get first user message as preview
                preview = "No messages"
                for msg in messages:
                    if msg.get("role") == "user":
                        preview = msg.get("content", "")[:60]
                        if len(msg.get("content", "")) > 60:
                            preview += "..."
                        break

                conversations.append({
                    "session_id": data.get("session_id"),
                    "filepath": str(filepath),
                    "message_count": len(messages),
                    "user_message_count": user_message_count,
                    "start_time": metadata.get("start_time"),
                    "last_updated": data.get("last_updated"),
                    "preview": preview,
                })
            except Exception as e:
                logger.warning(f"Failed to parse conversation file {filepath}: {e}")
                continue

        return conversations

    def delete_conversation(self, session_id: str) -> bool:
        """
        Delete a conversation file.

        Args:
            session_id: Session identifier

        Returns:
            True if deleted, False if not found
        """
        filename = f"{session_id}.json"
        filepath = self.storage_dir / filename

        if not filepath.exists():
            return False

        try:
            filepath.unlink()
            logger.info(f"Deleted conversation: {filepath}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete conversation: {e}")
            return False

    def get_latest_session_id(self) -> Optional[str]:
        """
        Get the most recently updated session ID.

        Returns:
            Session ID of most recent conversation, or None if no conversations exist
        """
        conversations = self.list_conversations()
        if not conversations:
            return None

        # Already sorted by modification time (most recent first)
        return conversations[0]["session_id"]
