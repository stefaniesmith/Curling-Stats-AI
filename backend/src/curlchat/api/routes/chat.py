from fastapi import APIRouter

from curlchat.api.schemas.chat import ChatRequest, ChatResponse

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def create_chat_response(request: ChatRequest) -> ChatResponse:
    return ChatResponse(
        conversation_id=request.conversation_id,
        message="Chat endpoint scaffolded. Agent orchestration not implemented yet.",
        blocks=[],
    )
