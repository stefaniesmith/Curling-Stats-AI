import json
from collections.abc import Iterator

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from curlchat.agent.graph.app_graph import (
    AgentConfigurationError,
    AgentInvocationError,
    respond_to_message,
    stream_response,
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


@router.post("/stream")
def stream_chat_response(request: ChatRequest) -> StreamingResponse:
    """Stream one chat turn as server-sent events while preserving the conversation thread."""
    conversation_service = get_conversation_service()
    try:
        conversation = (
            conversation_service.get(request.conversation_id)
            if request.conversation_id is not None
            else conversation_service.create(request.message)
        )
    except ConversationNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The requested conversation does not exist.",
        ) from error

    def events() -> Iterator[str]:
        yield _sse_event("message_start", {"conversation_id": str(conversation.id)})
        try:
            for event in stream_response(request.message, conversation.id):
                yield _sse_event(event.type, event.payload)
            conversation_service.touch(conversation.id)
        except AgentConfigurationError:
            yield _sse_event("error", {"detail": "The chat service is not configured."})
        except AgentInvocationError:
            yield _sse_event("error", {"detail": "The chat service is temporarily unavailable."})
        except Exception:
            yield _sse_event("error", {"detail": "The chat service is temporarily unavailable."})

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _sse_event(event: str, payload: dict) -> str:
    """Serialize one small, trusted server-sent event."""
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"
