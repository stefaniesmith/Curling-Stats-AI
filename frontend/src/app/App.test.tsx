import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";

const jsonResponse = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
  status,
  headers: { "Content-Type": "application/json" },
});

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
  let messageNumber = 0;
  vi.stubGlobal("crypto", { randomUUID: vi.fn(() => `message-${messageNumber++}`) });
  Element.prototype.scrollTo = vi.fn();
});

describe("App", () => {
  it("creates a conversation on the first message and includes its ID on a follow-up", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockImplementation(async (input, init) => {
      const url = String(input);
      if (url === "/api/conversations") return jsonResponse([]);
      if (url === "/api/chat") {
        const body = JSON.parse(String(init?.body));
        return jsonResponse({
          conversation_id: "conversation-id",
          message: `Answer: ${body.message}`,
          blocks: [{ type: "markdown", payload: { content: `Answer: ${body.message}` } }],
        });
      }
      return jsonResponse([]);
    });
    const user = userEvent.setup();
    render(<App />);

    const composer = await screen.findByPlaceholderText(/ask about a player/i);
    await user.type(composer, "Show Brier results");
    await user.keyboard("{Enter}");
    await screen.findByText("Answer: Show Brier results");

    await user.type(composer, "Only after 2020");
    await user.keyboard("{Enter}");
    await screen.findByText("Answer: Only after 2020");

    const chatBodies = fetchMock.mock.calls
      .filter(([url]) => url === "/api/chat")
      .map(([, init]) => JSON.parse(String(init?.body)));
    expect(chatBodies).toEqual([
      { message: "Show Brier results" },
      { message: "Only after 2020", conversation_id: "conversation-id" },
    ]);
  });

  it("hydrates persisted messages when a sidebar conversation is selected", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockImplementation(async (input) => {
      const url = String(input);
      if (url === "/api/conversations") {
        return jsonResponse([{ id: "history-id", title: "Historic Brier results", created_at: "2026-09-06T00:00:00Z", updated_at: "2026-09-06T00:00:00Z" }]);
      }
      if (url === "/api/conversations/history-id/messages") {
        return jsonResponse([
          { role: "user", content: "Show historic results", blocks: [] },
          { role: "assistant", content: "Historic answer", blocks: [{ type: "markdown", payload: { content: "Historic answer" } }] },
        ]);
      }
      return jsonResponse([]);
    });
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: /historic brier results/i }));

    expect(await screen.findByText("Show historic results")).toBeInTheDocument();
    expect(screen.getByText("Historic answer")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith("/api/conversations/history-id/messages", undefined);
  });

  it("shows a readable API error when the conversation list cannot load", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse({ detail: "The state database is unavailable." }, 503));
    render(<App />);

    await waitFor(() => expect(screen.getByText(/unable to complete the request/i)).toBeInTheDocument());
    expect(screen.getByText(/state database is unavailable/i)).toBeInTheDocument();
  });
});
