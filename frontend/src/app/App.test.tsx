import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";

const jsonResponse = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

const streamResponse = (events: Array<{ type: string; payload: object }>) =>
  new Response(
    events
      .map((event) => `event: ${event.type}\ndata: ${JSON.stringify(event.payload)}\n\n`)
      .join(""),
    { headers: { "Content-Type": "text/event-stream" } },
  );

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
  let messageNumber = 0;
  vi.stubGlobal("crypto", { randomUUID: vi.fn(() => `message-${messageNumber++}`) });
  Element.prototype.scrollTo = vi.fn();
});

afterEach(cleanup);

describe("App", () => {
  it("creates a conversation on the first message and includes its ID on a follow-up", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockImplementation(async (input, init) => {
      const url = String(input);
      if (url === "/api/conversations") return jsonResponse([]);
      if (url === "/api/chat/stream") {
        const body = JSON.parse(String(init?.body));
        return streamResponse([
          { type: "message_start", payload: { conversation_id: "conversation-id" } },
          { type: "markdown_delta", payload: { delta: "Answer: " } },
          { type: "markdown_delta", payload: { delta: body.message } },
          {
            type: "artifact",
            payload: {
              type: "table",
              payload: {
                columns: ["wins"],
                column_labels: { wins: "Wins" },
                rows: [{ wins: 8 }],
                title: null,
              },
            },
          },
          { type: "complete", payload: {} },
        ]);
      }
      return jsonResponse([]);
    });
    const user = userEvent.setup();
    render(<App />);

    const composer = await screen.findByPlaceholderText(/ask about a player/i);
    await user.type(composer, "Show Brier results");
    await user.keyboard("{Enter}");
    await screen.findByText("Answer: Show Brier results");
    expect(screen.getByRole("columnheader", { name: "Wins" })).toBeInTheDocument();

    await user.type(composer, "Only after 2020");
    await user.keyboard("{Enter}");
    await screen.findByText("Answer: Only after 2020");

    const chatBodies = fetchMock.mock.calls
      .filter(([url]) => url === "/api/chat/stream")
      .map(([, init]) => JSON.parse(String(init?.body)));
    expect(chatBodies).toEqual([
      { message: "Show Brier results" },
      { message: "Only after 2020", conversation_id: "conversation-id" },
    ]);
  });

  it("adds a completed artifact after streamed markdown even when it arrives first", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockImplementation(async (input) => {
      if (String(input) === "/api/conversations") return jsonResponse([]);
      if (String(input) === "/api/chat/stream") {
        return streamResponse([
          { type: "message_start", payload: { conversation_id: "conversation-id" } },
          {
            type: "artifact",
            payload: {
              type: "table",
              payload: {
                columns: ["wins"],
                column_labels: { wins: "Wins" },
                rows: [{ wins: 8 }],
                title: null,
              },
            },
          },
          { type: "markdown_delta", payload: { delta: "The answer is 8 wins." } },
          { type: "complete", payload: {} },
        ]);
      }
      return jsonResponse([]);
    });
    const user = userEvent.setup();
    render(<App />);

    await user.type(
      await screen.findByPlaceholderText(/ask about a player/i),
      "Show Brier results",
    );
    await user.keyboard("{Enter}");
    await screen.findByRole("columnheader", { name: "Wins" });

    const assistant = screen.getByText("The answer is 8 wins.").closest("article");
    expect(assistant?.textContent).toMatch(/The answer is 8 wins\.[\s\S]*Wins/);
  });

  it("hydrates persisted messages when a sidebar conversation is selected", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockImplementation(async (input) => {
      const url = String(input);
      if (url === "/api/conversations") {
        return jsonResponse([
          {
            id: "history-id",
            title: "Historic Brier results",
            created_at: "2026-09-06T00:00:00Z",
            updated_at: "2026-09-06T00:00:00Z",
          },
        ]);
      }
      if (url === "/api/conversations/history-id/messages") {
        return jsonResponse([
          { role: "user", content: "Show historic results", blocks: [] },
          {
            role: "assistant",
            content: "Historic answer",
            blocks: [{ type: "markdown", payload: { content: "Historic answer" } }],
          },
        ]);
      }
      return jsonResponse([]);
    });
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: /historic brier results/i }));

    expect(await screen.findByText("Show historic results")).toBeInTheDocument();
    expect(screen.getByText("Historic answer")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/conversations/history-id/messages",
      expect.objectContaining({ signal: expect.anything() }),
    );
  });

  it("keeps the most recently selected conversation when an earlier history load finishes late", async () => {
    let resolveFirstHistory: (response: Response) => void;
    vi.mocked(fetch).mockImplementation((input) => {
      const url = String(input);
      if (url === "/api/conversations") {
        return Promise.resolve(
          jsonResponse([
            {
              id: "first-id",
              title: "First conversation",
              created_at: "2026-09-06T00:00:00Z",
              updated_at: "2026-09-06T00:00:00Z",
            },
            {
              id: "second-id",
              title: "Second conversation",
              created_at: "2026-09-06T00:00:00Z",
              updated_at: "2026-09-06T00:00:00Z",
            },
          ]),
        );
      }
      if (url === "/api/conversations/first-id/messages") {
        return new Promise((resolve) => {
          resolveFirstHistory = resolve;
        });
      }
      if (url === "/api/conversations/second-id/messages") {
        return Promise.resolve(
          jsonResponse([{ role: "user", content: "Second conversation message", blocks: [] }]),
        );
      }
      return Promise.resolve(jsonResponse([]));
    });
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: /first conversation/i }));
    await user.click(screen.getByRole("button", { name: /second conversation/i }));
    expect(await screen.findByText("Second conversation message")).toBeInTheDocument();

    resolveFirstHistory!(
      jsonResponse([{ role: "user", content: "Stale first conversation message", blocks: [] }]),
    );

    await waitFor(() =>
      expect(screen.queryByText("Stale first conversation message")).not.toBeInTheDocument(),
    );
    expect(screen.getByText("Second conversation message")).toBeInTheDocument();
  });

  it("does not render a cancelled stream after selecting another conversation", async () => {
    let resolveStream: (response: Response) => void;
    vi.mocked(fetch).mockImplementation((input) => {
      const url = String(input);
      if (url === "/api/conversations") {
        return Promise.resolve(
          jsonResponse([
            {
              id: "history-id",
              title: "Saved conversation",
              created_at: "2026-09-06T00:00:00Z",
              updated_at: "2026-09-06T00:00:00Z",
            },
          ]),
        );
      }
      if (url === "/api/chat/stream") {
        return new Promise((resolve) => {
          resolveStream = resolve;
        });
      }
      if (url === "/api/conversations/history-id/messages") {
        return Promise.resolve(
          jsonResponse([{ role: "user", content: "Saved conversation message", blocks: [] }]),
        );
      }
      return Promise.resolve(jsonResponse([]));
    });
    const user = userEvent.setup();
    render(<App />);

    const composer = await screen.findByPlaceholderText(/ask about a player/i);
    await user.type(composer, "Question for the new conversation");
    await user.keyboard("{Enter}");
    await user.click(screen.getByRole("button", { name: /saved conversation/i }));
    expect(await screen.findByText("Saved conversation message")).toBeInTheDocument();

    resolveStream!(
      streamResponse([
        { type: "message_start", payload: { conversation_id: "stale-conversation-id" } },
        { type: "markdown_delta", payload: { delta: "Stale streamed answer" } },
      ]),
    );

    await waitFor(() =>
      expect(screen.queryByText("Stale streamed answer")).not.toBeInTheDocument(),
    );
    expect(screen.getByText("Saved conversation message")).toBeInTheDocument();
  });

  it("clears an unsent draft when starting a new conversation", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse([]));
    const user = userEvent.setup();
    render(<App />);

    const composer = await screen.findByPlaceholderText(/ask about a player/i);
    await user.type(composer, "A question for later");
    await user.click(screen.getByRole("button", { name: /new conversation/i }));

    expect(screen.getByPlaceholderText(/ask about a player/i)).toHaveValue("");
  });

  it("shows a readable API error when the conversation list cannot load", async () => {
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse({ detail: "The state database is unavailable." }, 503),
    );
    render(<App />);

    await waitFor(() =>
      expect(screen.getByText(/unable to complete the request/i)).toBeInTheDocument(),
    );
    expect(screen.getByText(/state database is unavailable/i)).toBeInTheDocument();
  });
});
