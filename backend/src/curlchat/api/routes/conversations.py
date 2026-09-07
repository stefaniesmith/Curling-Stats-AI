"""Endpoints for browsing persisted conversation metadata."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from curlchat.agent.graph.app_graph import load_conversation_history
from curlchat.api.schemas.conversations import ConversationMessageResponse, ConversationResponse
from curlchat.db.session import StateSessionLocal
from curlchat.services.conversation_service import ConversationNotFoundError, ConversationService

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


def get_conversation_service() -> ConversationService:
    """Build the state-only service used by the public conversation endpoints."""
    return ConversationService(StateSessionLocal)


@router.get("", response_model=list[ConversationResponse])
def list_conversations() -> list[ConversationResponse]:
    """List metadata without exposing or duplicating LangGraph messages."""
    return [
        ConversationResponse.model_validate(item, from_attributes=True)
        for item in get_conversation_service().list()
    ]


@router.get("/{conversation_id}/messages", response_model=list[ConversationMessageResponse])
def get_conversation_messages(conversation_id: UUID) -> list[ConversationMessageResponse]:
    """Return persisted user and final assistant messages for one known conversation."""
    try:
        get_conversation_service().get(conversation_id)
    except ConversationNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The requested conversation does not exist.",
        ) from error
    return [
        ConversationMessageResponse(
            role=message.role,
            content=message.content,
            blocks=(
                [{"type": "markdown", "payload": {"content": message.content}}]
                + [
                    {"type": artifact.type, "payload": artifact.payload}
                    for artifact in message.artifacts
                ]
                if message.role == "assistant"
                else []
            ),
        )
        for message in load_conversation_history(conversation_id)
    ]
