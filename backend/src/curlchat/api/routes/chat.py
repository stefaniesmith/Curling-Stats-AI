from fastapi import APIRouter, HTTPException, status

from curlchat.agent.graph.app_graph import (
    AgentConfigurationError,
    AgentInvocationError,
    respond_to_message,
)
from curlchat.api.routes.conversations import get_conversation_service
from curlchat.api.schemas.chat import ChatRequest, ChatResponse
from curlchat.services.conversation_service import ConversationNotFoundError

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def create_chat_response(request: ChatRequest) -> ChatResponse:
    conversation_service = get_conversation_service()
    try:
        conversation = (
            conversation_service.get(request.conversation_id)
            if request.conversation_id is not None
            else conversation_service.create(request.message)
        )
        response = respond_to_message(request.message, conversation.id)
        conversation_service.touch(conversation.id)
    except ConversationNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The requested conversation does not exist.",
        ) from error
    except AgentConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The chat service is not configured.",
        ) from error
    except AgentInvocationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The chat service is temporarily unavailable.",
        ) from error
    return ChatResponse(
        conversation_id=conversation.id,
        message=response.message,
        blocks=[
            {"type": "markdown", "payload": {"content": response.message}},
            *(
                {"type": artifact.type, "payload": artifact.payload}
                for artifact in response.artifacts
            ),
        ],
    )
