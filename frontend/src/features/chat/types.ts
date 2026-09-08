import type { ResponseBlock } from "../../types/api";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content?: string;
  blocks?: ResponseBlock[];
}
