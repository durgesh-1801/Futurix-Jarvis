"""
Futurix Jarvis — Memory Service.

High-level wrapper over ``DatabaseManager`` that manages conversation context
for the LLM, including automatic history summarisation when the context window
grows too large.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from database.db_manager import DatabaseManager, MessageRecord

logger = logging.getLogger(__name__)

# Maximum messages before we trigger a summarisation pass
_SUMMARISE_THRESHOLD = 50


class MemoryService:
    """Manages conversation memory and context for the LLM.

    Responsibilities:
    - Track the current active conversation.
    - Convert stored messages into the ``[{role, content}]`` format LangChain expects.
    - Summarise long histories to keep the context window manageable.

    Usage::

        mem = MemoryService(db)
        mem.start_conversation("Planning meeting")
        mem.save_exchange("What is 2+2?", "2 + 2 equals 4.")
        context = mem.get_context(limit=20)
    """

    def __init__(self, db: DatabaseManager) -> None:
        self._db = db
        self._current_conversation_id: Optional[int] = None

    # ── Properties ───────────────────────────────────────────────────────

    @property
    def current_conversation_id(self) -> Optional[int]:
        """The ID of the active conversation, or ``None``."""
        return self._current_conversation_id

    # ── Conversation lifecycle ───────────────────────────────────────────

    def start_conversation(self, title: str = "New Conversation") -> int:
        """Create a new conversation and set it as active.

        Args:
            title: Display title for the conversation.

        Returns:
            The new conversation ID.
        """
        conv_id = self._db.create_conversation(title)
        self._current_conversation_id = conv_id
        logger.info("Started conversation %d: %s", conv_id, title)
        return conv_id

    def load_conversation(self, conversation_id: int) -> None:
        """Switch to an existing conversation.

        Args:
            conversation_id: The conversation to load.
        """
        self._current_conversation_id = conversation_id
        logger.info("Loaded conversation %d", conversation_id)

    # ── Message persistence ──────────────────────────────────────────────

    def save_exchange(
        self,
        user_message: str,
        assistant_message: str,
        metadata: Optional[dict] = None,
    ) -> None:
        """Persist a user–assistant exchange.

        Args:
            user_message: What the user said.
            assistant_message: What the assistant replied.
            metadata: Optional metadata dict (tool calls, model info, etc.).
        """
        if self._current_conversation_id is None:
            self.start_conversation()
        conv_id = self._current_conversation_id
        assert conv_id is not None

        meta_json = json.dumps(metadata) if metadata else None
        self._db.add_message(conv_id, "user", user_message)
        self._db.add_message(conv_id, "assistant", assistant_message, meta_json)

        # Auto-title the conversation from the first user message
        count = self._db.get_message_count(conv_id)
        if count <= 2:
            title = user_message[:80].strip() or "New Conversation"
            self._db.update_conversation_title(conv_id, title)

        logger.debug("Saved exchange in conversation %d", conv_id)

    def save_system_message(self, content: str) -> None:
        """Persist a system-level message (e.g. tool output, summary)."""
        if self._current_conversation_id is None:
            return
        self._db.add_message(self._current_conversation_id, "system", content)

    # ── Context retrieval ────────────────────────────────────────────────

    def get_context(self, limit: int = 20) -> list[dict[str, str]]:
        """Build the message context list for the LLM.

        Returns a list of ``{role, content}`` dicts containing the most
        recent messages, suitable for passing to ``ChatOllama``.

        Args:
            limit: Maximum number of messages to include.

        Returns:
            List of role/content dicts in chronological order.
        """
        if self._current_conversation_id is None:
            return []

        messages = self._db.get_messages(self._current_conversation_id, limit=limit)
        return [{"role": m.role, "content": m.content} for m in messages]

    def get_full_history(self) -> list[MessageRecord]:
        """Return all messages in the current conversation."""
        if self._current_conversation_id is None:
            return []
        return self._db.get_messages(self._current_conversation_id, limit=10000)

    # ── History summarisation ────────────────────────────────────────────

    def needs_summarisation(self) -> bool:
        """Check whether the current conversation is long enough to summarise."""
        if self._current_conversation_id is None:
            return False
        count = self._db.get_message_count(self._current_conversation_id)
        return count > _SUMMARISE_THRESHOLD

    def build_summarisation_prompt(self) -> str:
        """Build a prompt asking the LLM to summarise the conversation.

        The caller should invoke the LLM with this prompt and then call
        ``apply_summary()`` with the result.

        Returns:
            A prompt string containing the conversation history to summarise.
        """
        messages = self.get_context(limit=_SUMMARISE_THRESHOLD)
        history_text = "\n".join(
            f"{m['role'].upper()}: {m['content']}" for m in messages
        )
        return (
            "Summarise the following conversation into a concise paragraph. "
            "Preserve key facts, decisions, and context:\n\n"
            f"{history_text}"
        )

    def apply_summary(self, summary: str) -> None:
        """Replace old messages with a summary message.

        This is a destructive operation — old messages are removed and
        replaced with a single system message containing the summary.

        Args:
            summary: The LLM-generated summary text.
        """
        if self._current_conversation_id is None:
            return
        self.save_system_message(f"[CONVERSATION SUMMARY]\n{summary}")
        logger.info(
            "Applied summary to conversation %d", self._current_conversation_id
        )

    # ── Conversation list ────────────────────────────────────────────────

    def get_conversations(self, limit: int = 50) -> list[dict]:
        """Return recent conversations as dicts (for the history panel).

        Returns:
            List of dicts with ``id``, ``title``, ``created_at``, ``updated_at``.
        """
        records = self._db.get_conversations(limit=limit)
        return [
            {
                "id": r.id,
                "title": r.title,
                "created_at": r.created_at,
                "updated_at": r.updated_at,
            }
            for r in records
        ]

    def delete_conversation(self, conversation_id: int) -> None:
        """Delete a conversation.  Clears active ID if it matches."""
        self._db.delete_conversation(conversation_id)
        if self._current_conversation_id == conversation_id:
            self._current_conversation_id = None
