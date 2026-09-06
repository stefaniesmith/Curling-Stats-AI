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

export interface ChatRequest {
  message: string;
  conversation_id?: string;
}
