# 09 - Streaming

## Overview

CurlChat supports progressive chat responses through `POST /api/chat/stream`.
The existing `POST /api/chat` endpoint remains the complete-response fallback.
Both endpoints create or continue the same UUID-backed LangGraph conversation.

The frontend uses `fetch` with a request body and reads the response stream;
browser `EventSource` is not used because it cannot send the required POST JSON
payload.

## Event Contract

The endpoint returns `text/event-stream`. Every event has one JSON `data`
payload and arrives in this order:

1. `message_start` — `{ "conversation_id": "UUID" }`; emitted before agent work.
2. Zero or more `status` events — `{ "label": "Querying statistics…" }`; replace
   the ephemeral UI progress label. Statuses are never saved as conversation messages.
3. Zero or more `markdown_delta` events — `{ "delta": "text" }`; append to the
   in-progress Markdown block.
4. Zero or more `artifact` events — `{ "type": "table|summary|chart", "payload": { ... } }`;
   append one complete, validated response block.
5. `complete` — `{}`; marks a successful persisted turn.

An `error` event has `{ "detail": "user-safe message" }` and terminates the
turn. An unknown conversation is rejected as an ordinary HTTP 404 before an
SSE response starts.

## Agent and Artifact Behavior

CurlChat converts graph lifecycle updates into deterministic progress statuses
such as resolving context, querying statistics, and preparing a visualization.
It forwards only a completed assistant message that has no tool calls as a
Markdown delta. Tool calls and internal agent planning are never sent to the
browser or persisted as conversation content.

The Visualization Tool remains deterministic. Its artifacts are emitted only
after the tool returns a fully validated table, summary, or chart payload;
charts are never partially rendered. The response's conversation metadata is
touched only after a successful stream completes.

## Frontend Lifecycle

The UI adds the user message immediately and displays a pending assistant
state with the latest ephemeral `status` label. The first `markdown_delta` or
`artifact` creates the assistant message; later deltas update its Markdown
block in place. On `message_start`, the UI stores the returned UUID so
subsequent turns continue the correct conversation. After the stream completes,
it clears the progress label and refreshes the sidebar metadata.
