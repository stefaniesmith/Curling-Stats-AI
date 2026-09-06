from fastapi import APIRouter, HTTPException, status

from curlchat.agent.graph.app_graph import (
    AgentConfigurationError,
    AgentInvocationError,
    respond_to_message,
)
from curlchat.api.schemas.chat import ChatRequest, ChatResponse

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def create_chat_response(request: ChatRequest) -> ChatResponse:
    try:
        response = respond_to_message(request.message)
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
        conversation_id=request.conversation_id,
        message=response.message,
        blocks=[
            {"type": "markdown", "payload": {"content": response.message}},
            *(
                {"type": artifact.type, "payload": artifact.payload}
                for artifact in response.artifacts
            ),
        ],
    )
