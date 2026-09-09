# 07 - API

## Overview

CurlChat exposes JSON endpoints plus a Server-Sent Events (SSE) chat endpoint.
FastAPI validates requests and renderable response blocks at the boundary;
agent orchestration, deterministic services, and database access remain internal.

During local development the API is at `http://localhost:8000`. The frontend
proxies browser requests beginning with `/api` to that origin.

## Conventions

* Request and ordinary response bodies are JSON.
* Conversation IDs are UUID strings and timestamps are ISO 8601 with UTC offsets.
* Errors use `{ "detail": "user-safe message" }`.
* Renderable blocks use a `type` discriminator. Unknown fields and malformed
  payloads are rejected at the API boundary.

## `POST /api/chat`

Runs one complete chat turn. It is the fallback for callers that do not consume SSE.

### Request

```json
{
  "message": "Show Brad Jacobs' wins at the 2024 Brier.",
  "conversation_id": "c160762c-6156-4270-8bbb-d57c63ab4696"
}
```

| Field | Required | Type | Rules |
| --- | --- | --- | --- |
| `message` | Yes | string | At least one non-whitespace character; at most 2,000 characters. |
| `conversation_id` | No | UUID string | Continues an existing conversation. Omit it to create one. |

### Response

```json
{
  "conversation_id": "c160762c-6156-4270-8bbb-d57c63ab4696",
  "message": "Brad Jacobs recorded 8 wins at the 2024 Brier.",
  "blocks": [
    {
      "type": "markdown",
      "payload": {"content": "Brad Jacobs recorded 8 wins at the 2024 Brier."}
    },
    {
      "type": "table",
      "payload": {
        "columns": ["display_name", "event_year", "wins"],
        "column_labels": {
          "display_name": "Display Name",
          "event_year": "Event Year",
          "wins": "Wins"
        },
        "rows": [{"display_name": "Brad Jacobs", "event_year": 2024, "wins": 8}],
        "title": "2024 Brier results"
      }
    }
  ]
}
```

`message` duplicates the first Markdown block for simple consumers. Rich clients
should render the ordered `blocks` array.

## Renderable blocks

Every assistant response begins with Markdown. Table, summary, and chart artifacts
follow only when the agent creates them.

### Markdown

```json
{"type": "markdown", "payload": {"content": "A source-grounded explanation in Markdown."}}
```

### Table

```json
{
  "type": "table",
  "payload": {
    "columns": ["display_name", "wins"],
    "column_labels": {"display_name": "Display Name", "wins": "Wins"},
    "rows": [{"display_name": "Brad Jacobs", "wins": 8}],
    "title": null
  }
}
```

`columns` specifies display order. `column_labels` must have a label for every
column. Row values may be JSON scalars or null.

### Summary

```json
{
  "type": "summary",
  "payload": {
    "label": "Average Wins",
    "value": 6.5,
    "source_column": "wins",
    "aggregation": "average",
    "title": "Average Brier wins"
  }
}
```

`aggregation` is one of `average`, `maximum`, `minimum`, or `sum`.

### Chart

```json
{
  "type": "chart",
  "payload": {
    "chart_type": "line",
    "x_column": "event_year",
    "y_column": "draw_percent",
    "x_label": "Event Year",
    "y_label": "Draw Percentage",
    "title": "Draw percentage by year",
    "points": [{"x": 2023, "y": 86.0}, {"x": 2024, "y": 88.0}]
  }
}
```

`chart_type` is `bar`, `line`, or `dot`. A chart has exactly one data shape:

* `points`: `{ "x": string | number, "y": number }` values; or
* `series`: named point lists for comparisons. Series charts include
  `series_column`; grouped bar charts include `bar_mode: "group"`.

Wide result mappings may include `value_columns`. Clients should display the
backend-provided `x_label` and `y_label`, rather than deriving labels from columns.

## `POST /api/chat/stream`

Accepts the same request and validation rules as `POST /api/chat`, but returns
`text/event-stream`.

```text
event: message_start
data: {"conversation_id":"c160762c-6156-4270-8bbb-d57c63ab4696"}

event: markdown_delta
data: {"delta":"Brad Jacobs recorded "}

event: artifact
data: {"type":"table","payload":{...}}

event: complete
data: {}
```

Artifact event payloads use the exact table, summary, and chart shapes above.
`status` has `{ "label": "Querying statistics" }`; `markdown_delta` has
`{ "delta": "text" }`; `complete` has `{}`. A failed active stream ends with
an `error` event containing `{ "detail": "user-safe message" }`. See
[09-streaming.md](09-streaming.md) for event ordering and frontend lifecycle details.

## Conversation endpoints

### `GET /api/conversations`

Returns metadata ordered by most recent completed activity.

```json
[
  {
    "id": "c160762c-6156-4270-8bbb-d57c63ab4696",
    "title": "Show Brad Jacobs' wins at the 2024 Brier.",
    "created_at": "2026-09-06T12:00:00Z",
    "updated_at": "2026-09-06T12:01:04Z"
  }
]
```

### `GET /api/conversations/{conversation_id}/messages`

Returns persisted user and final assistant messages. Assistant messages contain
their Markdown block followed by original artifacts; user messages have an empty
`blocks` array. Internal LangGraph messages and tool traffic are never exposed.

```json
[
  {"role": "user", "content": "Show Brad Jacobs' wins at the 2024 Brier.", "blocks": []},
  {
    "role": "assistant",
    "content": "Brad Jacobs recorded 8 wins at the 2024 Brier.",
    "blocks": [{"type": "markdown", "payload": {"content": "..."}}]
  }
]
```

## Status and error behavior

| Status or event | Meaning |
| --- | --- |
| `200 OK` | A synchronous turn, conversation list, or message history was returned. |
| `422 Unprocessable Entity` | JSON is invalid, a message is blank or over 2,000 characters, or a UUID is malformed. |
| `404 Not Found` | The supplied conversation UUID has no CurlChat metadata record. |
| `503 Service Unavailable` | The synchronous chat provider is unconfigured or temporarily unavailable. |
| SSE `error` event | A streamed turn failed after the response began; its payload has a user-safe `detail` message. |
