"""Data access for application-owned conversation metadata."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from curlchat.db.models import Conversation


class ConversationRepository:
    """Read/write access to metadata, never to LangGraph message history."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, conversation: Conversation) -> None:
        """Stage a new conversation metadata record."""
        self._session.add(conversation)

    def get(self, conversation_id: UUID) -> Conversation | None:
        """Return one conversation metadata record when it exists."""
        return self._session.get(Conversation, conversation_id)

    def list(self) -> list[Conversation]:
        """Return conversations in most-recently-active order."""
        return list(
            self._session.scalars(
                select(Conversation).order_by(Conversation.updated_at.desc(), Conversation.id.desc())
            )
        )
