from pydantic import BaseModel, Field


class ResponseBlock(BaseModel):
    type: str = Field(description="Renderable block type such as markdown, table, or chart.")
    payload: dict = Field(default_factory=dict)


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None


class ChatResponse(BaseModel):
    conversation_id: str | None = None
    message: str
    blocks: list[ResponseBlock] = Field(default_factory=list)
