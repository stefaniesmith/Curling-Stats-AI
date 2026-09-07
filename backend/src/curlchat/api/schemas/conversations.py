"""HTTP schemas for application-owned conversation metadata."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from curlchat.api.schemas.chat import ResponseBlock


class ConversationResponse(BaseModel):
    """Metadata for a persisted conversation; messages live in LangGraph."""

    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime


class ConversationMessageResponse(BaseModel):
    """One user or assistant message reconstructed from a persisted conversation."""

    role: Literal["user", "assistant"]
    content: str
    blocks: list[ResponseBlock] = Field(default_factory=list)
