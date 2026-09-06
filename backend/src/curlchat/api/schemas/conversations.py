"""HTTP schemas for application-owned conversation metadata."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ConversationResponse(BaseModel):
    """Metadata for a persisted conversation; messages live in LangGraph."""

    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime
