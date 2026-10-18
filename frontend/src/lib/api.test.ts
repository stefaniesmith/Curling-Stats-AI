import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getConversationMessages, listConversations, streamMessage } from "./api";
import { jsonResponse, sseEvent, streamResponse, streamResponseChunks } from "../test/http";

describe("API client", () => {
  beforeEach(() => vi.stubGlobal("fetch", vi.fn()));
  afterEach(() => vi.unstubAllGlobals());

  it("parses SSE events split across chunks and normalizes CRLF delimiters", async () => {
    vi.mocked(fetch).mockResolvedValue(
      streamResponseChunks([
        'event: message_start\r\ndata: {"conversation_',
        'id":"conversation-id"}\r\n\r\nevent: markdown_delta\r\ndata: {"delta":"Hello"}\r\n\r\n',
      ]),
    );
    const events: object[] = [];

    await streamMessage({ message: "Hello" }, (event) => events.push(event));

    expect(events).toEqual([
      { type: "message_start", payload: { conversation_id: "conversation-id" } },
      { type: "markdown_delta", payload: { delta: "Hello" } },
    ]);
  });

  it.each([
    ["malformed SSE JSON", ["event: status\ndata: not-json\n\n"]],
    ["invalid typed event payload", [sseEvent({ type: "status", payload: {} })]],
  ])("rejects %s", async (_, chunks) => {
    vi.mocked(fetch).mockResolvedValue(streamResponseChunks(chunks));

    await expect(streamMessage({ message: "Hello" }, vi.fn())).rejects.toThrow(
      "invalid streaming event",
    );
  });

  it("surfaces a server-stream error payload", async () => {
    vi.mocked(fetch).mockResolvedValue(
      streamResponse([{ type: "error", payload: { detail: "Model unavailable" } }]),
    );

    await expect(streamMessage({ message: "Hello" }, vi.fn())).rejects.toMatchObject({
      message: "Model unavailable",
    });
  });

  it("wraps a network failure from a standard API request", async () => {
    vi.mocked(fetch).mockRejectedValue(new TypeError("network down"));

    await expect(listConversations()).rejects.toMatchObject({
      message: "CurlChat could not reach the API. Start the FastAPI server and try again.",
    });
  });

  it("preserves HTTP status and detail from standard API requests", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse({ detail: "Database unavailable" }, 503));

    await expect(listConversations()).rejects.toMatchObject({
      message: "Database unavailable",
      status: 503,
    });
  });

  it("rejects an empty streaming response and preserves aborted history requests", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(new Response(null))
      .mockRejectedValueOnce(new DOMException("Aborted", "AbortError"));

    await expect(streamMessage({ message: "Hello" }, vi.fn())).rejects.toThrow(
      "empty streaming response",
    );
    await expect(getConversationMessages("conversation-id")).rejects.toMatchObject({
      name: "AbortError",
    });
  });
});
