# 04 - Agent

## Overview

CurlChat uses an AI agent to translate natural language questions into deterministic operations against the application's analytics database.

The agent is responsible for understanding user intent, orchestrating the appropriate tools, and producing structured responses that the frontend can render incrementally.

Rather than embedding business logic inside the language model, CurlChat follows a tool-based architecture. The LLM acts as an orchestrator, while application services perform deterministic work such as player resolution, SQL execution, and chart generation.

The agent is implemented using LangGraph, providing explicit workflow orchestration,
persisted conversations, and streaming execution.

---

## Initial Implementation

The first implemented graph uses a configurable OpenAI chat model and exposes
four tools: Player Resolver, Event Resolver, Analytics Query, and
Visualization. It returns Markdown plus any visualization artifacts created
during the turn through the chat endpoint. The model is
instructed to resolve player identities before querying statistics, and it has
no direct database access or SQL-generation responsibility.

The system prompt includes a deterministic, live-rendered competition reference
from imported event metadata. It gives each canonical competition name, its
earliest and latest imported years, all-shot-statistics availability, and a
small curated alias list (including “Scotties” and “Tournament of Hearts” for
“Hearts”). It does not expose event IDs. This lets the agent explain archive
coverage while the Event Resolver remains the authoritative deterministic path
for resolving a user phrase to an event identity used in analytics queries.

System instructions are versioned Markdown assets in `agent/prompts` rather
than inline Python strings. The SQL-generation prompt receives a live,
inspected analytics schema description containing column types, nullability,
keys, relationships, comments where supported, and check constraints. It
explicitly treats `NULL` statistical values as unavailable source data, not
zero, and requires null-safe ordering for nullable-metric rankings.
An event ID identifies a competition across multiple imported years, so the
prompt also requires every explicit requested year or year range to constrain
`player_event_statistics.event_year` with named parameters. The Event Resolver
ignores year tokens only while finding the event identity; it does not remove
the time constraint from the analytics query.
For rankings, position comparisons, and performance aggregates, it also
excludes alternate-designated stints by default while retaining historical
records where alternate status is unmarked.
It describes the statistics table as player stints, so event-wide and career
queries aggregate a player's multiple positions or teams when those dimensions
are not explicitly requested. Percentage rankings use the corresponding shot
quantities for volume-weighted calculations rather than ranking one small stint
or averaging row percentages. The prompt gives the SQL generator an explicit
`SUM(metric_total * metric_percent) / SUM(metric_total)` pattern rather than
leaving the weighted calculation implicit. Generated result aliases remain
user-facing statistic names rather than exposing calculation details such as
“weighted.”

After successful analytical queries, the main agent creates useful
visualizations proactively rather than asking permission in a follow-up turn.
It uses charts for trends, rankings, and comparisons, tables when exact values
or many categories matter, and answers a single winner or scalar result in
prose unless the user explicitly requests a table or chart.
When it includes an artifact, the written response states the takeaway directly
rather than announcing or describing the chart or table renderer.

Conversation persistence is implemented with LangGraph's PostgreSQL
checkpointer. Every chat request supplies the application's UUID as the
checkpointer `thread_id`, so successful turns become available to follow-up
requests in that conversation. The graph streams final assistant Markdown token
deltas and completed Visualization Tool outputs; the API translates those
internal events into a frontend-safe SSE contract.

The graph also retains the latest successful analytics result in its persisted
state. The Analytics Query Tool returns a readable serialized result to the
model and stores the original typed rows in that state. The Visualization Tool
receives only a typed table, summary, or chart specification and reads those
rows internally. This prevents the model from having to copy result values into
a second tool call, preserves database numeric types such as `Decimal`, and
allows a later request such as “visualize that” to use the previous result. A
failed query does not replace the retained successful result.

---

## Design Principles

The agent is designed around several core principles:

* Use the LLM for reasoning rather than computation.
* Delegate deterministic work to application services.
* Keep tools narrowly focused and independently testable.
* Stream responses as work completes.
* Persist conversations using LangGraph.
* Produce structured output that the frontend can render directly.

---

## Responsibilities

The agent is responsible for:

* interpreting user requests
* maintaining conversational context
* determining which tools to invoke
* requesting analytical results through the Analytics Query Tool
* requesting visualizations when appropriate
* assembling the final response
* streaming response blocks to the client

The agent is **not** responsible for:

* executing SQL directly
* resolving player aliases itself
* generating charts itself
* implementing business rules
* formatting frontend components

Those responsibilities belong to dedicated tools and application services.

---

## High-Level Workflow

A typical request follows this sequence:

```text
User
    │
    ▼
LangGraph Agent
    │
    ├── Player Resolver
    │
        ├── Event Resolver
        │
        ├── Analytics Query Tool
    │
    ├── Visualization Tool (optional)
    │
    ▼
Structured Response
    │
    ▼
Streaming API
    │
    ▼
Frontend
```

The agent determines which tools are required based on the user's request and combines their outputs into a coherent response.

---

## LangGraph

LangGraph provides the orchestration layer for the conversational agent.

Its responsibilities include:

* maintaining conversation state
* coordinating tool execution
* persisting message history
* supporting streaming responses
* enabling future graph expansion

The graph represents the application's workflow rather than a collection of prompts.
Each node has a well-defined responsibility and communicates through Pydantic
state models.

---

## Conversation State

Conversation history is managed through LangGraph persistence.

The application maintains separate metadata for conversations (such as title and creation date), while LangGraph stores the conversational state and message history required by the agent.

This separation allows the application to manage conversations independently without duplicating message storage.

---

## Tool Pipeline

The agent delegates work to a small set of specialized tools.

### Player Resolver

Resolves player names before SQL generation.

Responsibilities include:

* canonical name resolution
* alias lookup
* historical name matching

The Analytics Query Tool always receives canonical player identities.

---

### Analytics Query Tool

Fulfills analytical data requests against the statistics database.

The tool:

* receives the user's analytical intent
* invokes an internal two-node agent graph: SQL generation followed by validation and execution
* retries SQL generation once with a sanitized validation or execution error when needed
* returns structured results

The tool only accesses the analytics schema.

It does not perform player alias resolution or business logic.

---

### Event Resolver

Resolves a named competition before analytics query generation.

The resolver returns one canonical event identity pair (`display_name` and
`event_id`) when matching is unambiguous. For shorthand such as “Canada Cup”
that matches distinct men's and women's events, it returns the candidates as
ambiguous and the main agent asks the user to clarify. When the agent has
already resolved player identities, it supplies them as context; the resolver
may then select one event only when source statistics show that every supplied
player has records for that candidate.

---

### Visualization Tool

Transforms the latest successful query result into frontend-friendly
visualization artifacts.

Examples include:

* line charts
* bar charts
* tables
* summary statistics

The tool returns structured metadata rather than rendered images, allowing the frontend to render interactive components.

---

## Agent Decision Making

The language model determines:

* which tools are required
* the order in which they should execute
* whether a visualization would improve the response
* how to summarize the results for the user

Business logic remains outside the model whenever deterministic behavior is possible.

---

## Streaming Responses

Responses are streamed incrementally as work completes.

Rather than waiting for an entire response, the frontend receives a sequence of response blocks.

A typical response might contain:

1. chart
2. explanatory markdown
3. data table
4. concluding summary

Because each block is independently renderable, users begin seeing useful information before the entire response has finished generating.

---

## Error Handling

Tools return structured errors rather than raising user-facing exceptions.

The agent is responsible for translating these failures into clear, conversational responses.

Examples include:

* player not found
* unsupported statistic
* SQL generation failure
* empty query results

Whenever possible, the agent should suggest alternative queries or clarify ambiguous requests.

---

## Safety

The Analytics Query Tool operates using a database account with read-only permissions.

The agent cannot modify application data.

Additional safeguards include:

* restricted schema visibility
* parameterized execution where appropriate
* deterministic application services
* a single-statement guard, database-side statement timeout, and result-row cap

These constraints reduce the likelihood of unsafe or unintended behavior while simplifying reasoning about the system.

---

## Extensibility

The tool-based architecture allows new capabilities to be added without significantly changing the agent.

Future tools might include:

* statistical analysis
* player comparisons
* tournament simulations
* external data sources
* report generation

Because the agent interacts with tools through well-defined interfaces, new functionality can be introduced with minimal impact on existing workflows.

---

## Summary

The CurlChat agent serves as an orchestration layer between natural language requests and deterministic application services.

By combining LangGraph, specialized tools, and structured streaming responses, the system provides an architecture that is understandable, extensible, and well suited to AI-assisted analytics while keeping business logic outside the language model wherever possible.
