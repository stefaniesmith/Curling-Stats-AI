# 07 - API

## Overview

CurlChat exposes a synchronous HTTP API from FastAPI. The API validates and serializes requests at the boundary; agent orchestration, deterministic services, and database access remain behind it.

## Synchronous Chat

`POST /api/chat` accepts a `message` and optional `conversation_id` UUID. Without an ID, the server creates conversation metadata before invoking the agent and returns the new UUID. With an ID, the server verifies that metadata exists, then invokes the persisted LangGraph thread with the same UUID.

The response contains the conversation ID, the assistant's Markdown message, and ordered renderable blocks. This endpoint always returns the complete turn and remains available as a fallback for clients that do not consume SSE.

## Streaming Chat

`POST /api/chat/stream` accepts the same JSON request as synchronous chat and
returns server-sent events. It emits a conversation ID first, then ephemeral
deterministic progress statuses, final assistant Markdown, and completed
visualization artifacts as they are available. See `docs/09-streaming.md` for
the event lifecycle and error behavior.

## Conversations

`GET /api/conversations` returns conversation metadata ordered by most recent activity. It does not return database or checkpointer internals.

`GET /api/conversations/{conversation_id}/messages` returns the persisted user messages and final assistant messages for one known conversation. Assistant responses include their original Markdown block plus any table, summary, or chart artifacts created during that turn. Internal LangGraph messages and tool traffic are not exposed.

An unknown conversation ID returns `404` with `The requested conversation does not exist.` Both endpoints use the application UUID as the authoritative LangGraph thread ID.

## Errors

The chat endpoint returns `503` when the agent is unconfigured or its provider is temporarily unavailable. The frontend presents these as user-facing request errors. Invalid request data uses FastAPI's standard validation responses.
