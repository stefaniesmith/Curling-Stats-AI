import type { ChatRequest, ChatResponse, Conversation } from "../types/api";

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

export const sendMessage = (body: ChatRequest) =>
  request<ChatResponse>("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
