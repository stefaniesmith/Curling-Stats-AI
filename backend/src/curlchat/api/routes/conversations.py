"""Endpoints for browsing persisted conversation metadata."""

from fastapi import APIRouter

from curlchat.api.schemas.conversations import ConversationResponse
from curlchat.db.session import StateSessionLocal
from curlchat.services.conversation_service import ConversationService

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


def get_conversation_service() -> ConversationService:
    """Build the state-only service used by the public conversation endpoints."""
    return ConversationService(StateSessionLocal)


@router.get("", response_model=list[ConversationResponse])
def list_conversations() -> list[ConversationResponse]:
    """List metadata without exposing or duplicating LangGraph messages."""
    return [ConversationResponse.model_validate(item) for item in get_conversation_service().list()]
