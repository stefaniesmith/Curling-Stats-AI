"""Application services for conversation metadata."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from curlchat.db.models import Conversation
from curlchat.repositories.conversations import ConversationRepository


class ConversationNotFoundError(LookupError):
    """The requested conversation has no application metadata record."""


class ConversationMetadata(BaseModel):
    """Frontend-safe metadata; messages remain in LangGraph checkpoints."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime


class ConversationService:
    """Create, retrieve, list, and update conversation metadata."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def create(self, initial_message: str) -> ConversationMetadata:
        """Create a metadata record before the first LangGraph invocation."""
        with self._session_factory() as session:
            repository = ConversationRepository(session)
            conversation = Conversation(id=uuid4(), title=self._title(initial_message))
            repository.add(conversation)
            session.commit()
            session.refresh(conversation)
            return self._metadata(conversation)

    def get(self, conversation_id: UUID) -> ConversationMetadata:
        """Return metadata or signal that the ID is not an application conversation."""
        with self._session_factory() as session:
            conversation = ConversationRepository(session).get(conversation_id)
            if conversation is None:
                raise ConversationNotFoundError(str(conversation_id))
            return self._metadata(conversation)

    def list(self) -> list[ConversationMetadata]:
        """List conversation metadata without loading checkpointed messages."""
        with self._session_factory() as session:
            return [
                self._metadata(conversation)
                for conversation in ConversationRepository(session).list()
            ]

    def touch(self, conversation_id: UUID) -> ConversationMetadata:
        """Record a successfully completed conversational turn."""
        with self._session_factory() as session:
            conversation = ConversationRepository(session).get(conversation_id)
            if conversation is None:
                raise ConversationNotFoundError(str(conversation_id))
            conversation.updated_at = datetime.now(tz=UTC)
            session.commit()
            session.refresh(conversation)
            return self._metadata(conversation)

    @staticmethod
    def _title(message: str) -> str:
        """Create a compact deterministic title without a second model call."""
        normalized = " ".join(message.split())
        return normalized[:120] or "New conversation"

    @staticmethod
    def _metadata(conversation: Conversation) -> ConversationMetadata:
        return ConversationMetadata(
            id=conversation.id,
            title=conversation.title,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
        )
