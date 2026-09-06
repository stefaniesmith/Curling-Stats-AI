"""ORM model for application-owned conversation metadata."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from curlchat.db.session import Base


class Conversation(Base):
    """Metadata for one LangGraph thread without duplicating its messages."""

    __tablename__ = "conversations"
    __table_args__ = {
        "comment": "Application metadata for a persisted CurlChat conversation."
    }

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, comment="Shared application and LangGraph thread ID."
    )
    title: Mapped[str] = mapped_column(
        String(120), nullable=False, comment="Deterministic title derived from the first user message."
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), comment="Creation timestamp."
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="Timestamp of the most recently completed conversation turn.",
    )
