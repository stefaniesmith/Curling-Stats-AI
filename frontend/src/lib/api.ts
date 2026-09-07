import type {
  ChatRequest,
  ChatResponse,
  ChatStreamEvent,
  Conversation,
  ConversationMessage,
} from "../types/api";

export class ApiError extends Error {
  constructor(message: string, public readonly status?: number) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, init);
  } catch {
    throw new ApiError("CurlChat could not reach the API. Start the FastAPI server and try again.");
  }

  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new ApiError(body?.detail ?? "The API could not complete that request.", response.status);
  }
  return response.json() as Promise<T>;
}

export const listConversations = () => request<Conversation[]>("/api/conversations");

export const getConversationMessages = (conversationId: string) =>
  request<ConversationMessage[]>(`/api/conversations/${conversationId}/messages`);

export const sendMessage = (body: ChatRequest) =>
  request<ChatResponse>("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

export async function streamMessage(
  body: ChatRequest,
  onEvent: (event: ChatStreamEvent) => void,
): Promise<void> {
  const response = await fetch("/api/chat/stream", {
    method: "POST",
    headers: { "Accept": "text/event-stream", "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new ApiError(payload?.detail ?? "The API could not complete that request.", response.status);
  }
  if (!response.body) throw new ApiError("The API returned an empty streaming response.");

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value, { stream: !done }).replaceAll("\r\n", "\n");
    const events = buffer.split("\n\n");
    buffer = events.pop() ?? "";
    for (const rawEvent of events) {
      const event = parseStreamEvent(rawEvent);
      if (!event) continue;
      if (event.type === "error") throw new ApiError(String(event.payload.detail ?? "The chat stream failed."));
      onEvent(event as ChatStreamEvent);
    }
    if (done) break;
  }
}

function parseStreamEvent(rawEvent: string): { type: string; payload: Record<string, unknown> } | undefined {
  const eventType = rawEvent.match(/^event: (.+)$/m)?.[1];
  const data = rawEvent.match(/^data: (.+)$/m)?.[1];
  if (!eventType || !data) return undefined;
  try {
    return { type: eventType, payload: JSON.parse(data) as Record<string, unknown> };
  } catch {
    throw new ApiError("The API returned an invalid streaming event.");
  }
}
