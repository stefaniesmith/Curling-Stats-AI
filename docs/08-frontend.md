# 08 - Frontend

## Overview

The CurlChat frontend is a React, TypeScript, and Vite single-page application in `frontend`. It presents the existing synchronous FastAPI contract as a chat-first analytics experience. Streaming is intentionally not part of this implementation.

## Responsibilities

The frontend owns presentation and browser-local interaction state only:

* fetches conversation metadata from `GET /api/conversations`
* sends messages to `POST /api/chat`
* retains the returned conversation UUID for subsequent messages
* renders the response block contract: Markdown, tables, summaries, and Plotly charts
* exposes loading, API-unavailable, and configuration-error feedback

It does not implement player resolution, query logic, or visualization construction.

## Conversation Behavior

On a user's first message, the UI omits `conversation_id`. The API creates the conversation and returns its UUID; the UI stores it as the active conversation and includes it with each follow-up request. The sidebar refreshes after a completed response so the new or updated metadata is immediately visible.

The API currently exposes conversation metadata rather than persisted message history. Selecting a previous conversation establishes it as the active server-side context for the next message, but cannot reconstruct its prior messages in the browser. Message-history retrieval should be added as a deliberate API contract before the UI attempts to display it.

## Response Blocks

The UI treats `blocks` from the chat response as the rendering contract. Supported blocks are:

* `markdown` with `payload.content`
* `table` with `payload.columns`, `payload.rows`, and optional `payload.title`
* `summary` with label, numeric value, and optional title
* `chart` with `bar`, `line`, or `dot` points or named series

Charts are rendered by Plotly in the browser. The backend Visualization Service remains the authority for chart types, mappings, and payload construction.

## Development

Run the FastAPI backend on port 8000, then from `frontend` run `pnpm install` and `pnpm dev`. Vite proxies `/api` to `http://localhost:8000`; `VITE_API_TARGET` can override the target for local development. Production hosting should supply an equivalent reverse proxy or an explicit API base URL.

The canonical brand asset is `CurlChatLogo.png` at the repository root. The welcome state uses the full mark; the sidebar uses a compact crop of that same source asset. Styling draws from its navy, red, and ice-blue palette.
