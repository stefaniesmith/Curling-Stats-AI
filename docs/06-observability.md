# 06 - Observability

## Overview

CurlChat uses self-hosted Arize Phoenix for local AI tracing. Phoenix receives
OpenTelemetry/OpenInference traces separately from the CurlChat analytics
database. It is an optional development dependency and must never affect a
chat response when the collector is unavailable.

## Trace Boundaries

When tracing is enabled, Phoenix's LangChain instrumentor automatically records
LangGraph agent invocations, model calls, and tool calls. HTTP framework
instrumentation is deliberately disabled, so routine API requests do not create
traces. One chat turn is visible as a hierarchy such as:

```text
CurlChat agent
  ├── Player Resolver
  ├── Event Resolver
  ├── Analytics Query Tool
  │     ├── SQL-generation graph
  │     └── validated query execution
  └── Visualization Tool
```

The initial implementation deliberately does not add manual spans to every
service. Automatic framework instrumentation is sufficient for agent debugging
and keeps observability separate from deterministic business logic. Manual
attributes can be added later when an evaluated operational need arises.

## Local Setup

Start the self-hosted Phoenix service:

```bash
docker compose up -d phoenix
```

Phoenix is available at `http://localhost:6006`. Its data is persisted in the
separate `phoenix_data` Docker volume, not in the CurlChat Postgres volume.

Enable the backend exporter in the local environment:

```dotenv
PHOENIX_TRACING_ENABLED=true
PHOENIX_COLLECTOR_ENDPOINT=http://localhost:6006/v1/traces
PHOENIX_PROJECT_NAME=curlchat
```

Restart the API after changing these settings. Tracing is disabled by default,
which keeps unit tests and normal local runs independent of Phoenix.

## Data Handling

Phoenix traces can contain user chat text, model prompts, tool inputs, and tool
outputs. Do not add credentials, database URLs, API keys, or authorization
headers to trace attributes. Do not expose the Phoenix UI publicly without
adding authentication and access controls.
