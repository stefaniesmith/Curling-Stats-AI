# 08 - Frontend

## Overview

The CurlChat frontend is a React, TypeScript, and Vite single-page application in `frontend`. It presents a chat-first analytics experience using the synchronous API as a fallback and the streaming API for active turns.

## Responsibilities

The frontend owns presentation and browser-local interaction state only:

* fetches conversation metadata from `GET /api/conversations`
* sends active messages to `POST /api/chat/stream` and consumes its SSE response
* retains the returned conversation UUID for subsequent messages
* renders the response block contract: Markdown, tables, summaries, and Plotly charts
* exposes loading, API-unavailable, and configuration-error feedback

It does not implement player resolution, query logic, or visualization construction.

During an active turn, Markdown deltas update one in-progress assistant
message. Completed table, summary, and chart artifacts append atomically to
that message. The synchronous endpoint remains available in the API client for
non-streaming callers.

## Conversation Behavior

On a user's first message, the UI omits `conversation_id`. The API creates the conversation and returns its UUID; the UI stores it as the active conversation and includes it with each follow-up request. The sidebar refreshes after a completed response so the new or updated metadata is immediately visible.

Selecting a previous conversation fetches its persisted history from `GET /api/conversations/{conversation_id}/messages`, disables the composer during hydration, and renders the returned user and assistant blocks. The server owns history reconstruction from LangGraph state; the browser never reads checkpointer tables or recreates artifacts.

## Response Blocks

The UI treats `blocks` from the chat response as the rendering contract. Supported blocks are:

* `markdown` with `payload.content`
* `table` with `payload.columns`, `payload.rows`, and optional `payload.title`
* `summary` with label, numeric value, and optional title
* `chart` with `bar`, `line`, or `dot` points or named series

Charts are rendered by Plotly in the browser. The backend Visualization Service remains the authority for chart types, mappings, and payload construction.

## Development

Run the FastAPI backend on port 8000, then from `frontend` run `pnpm install` and `pnpm dev`. Vite proxies `/api` to `http://localhost:8000`; `VITE_API_TARGET` can override the target for local development. The local Docker Compose stack builds this application with Vite and serves the output from an Nginx container. Nginx proxies `/api` to FastAPI and disables buffering for `/api/chat/stream`, preserving incremental SSE delivery without exposing a second browser-facing API origin.

The canonical brand asset is `assets/CurlChatLogo.png` at the repository root. The welcome state uses the full mark; the sidebar uses a compact crop of that same source asset. Styling draws from its navy, red, and ice-blue palette.

Frontend component and interaction tests use Vitest, jsdom, and React Testing Library. See `docs/10-testing.md` for the covered behavior and commands.
