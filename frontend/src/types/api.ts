export type BlockType = "markdown" | "table" | "summary" | "chart";

export interface ResponseBlock {
  type: BlockType;
  payload: Record<string, unknown>;
}

export interface ChatResponse {
  conversation_id: string;
  message: string;
  blocks: ResponseBlock[];
}

export interface Conversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface ConversationMessage {
  role: "user" | "assistant";
  content: string;
  blocks: ResponseBlock[];
}

export interface ChatRequest {
  message: string;
  conversation_id?: string;
}

export type ChatStreamEvent =
  | { type: "message_start"; payload: { conversation_id: string } }
  | { type: "status"; payload: { label: string } }
  | { type: "markdown_delta"; payload: { delta: string } }
  | { type: "artifact"; payload: { type: Exclude<BlockType, "markdown">; payload: Record<string, unknown> } }
  | { type: "complete"; payload: Record<string, never> };
