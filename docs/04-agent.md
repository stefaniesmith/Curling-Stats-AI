# 04 - Agent

## Overview

CurlChat uses an AI agent to translate natural language questions into deterministic operations against the application's analytics database.

The agent is responsible for understanding user intent, orchestrating the appropriate tools, and producing structured responses that the frontend can render incrementally.

Rather than embedding business logic inside the language model, CurlChat follows a tool-based architecture. The LLM acts as an orchestrator, while application services perform deterministic work such as player resolution, SQL execution, and chart generation.

The agent is implemented using LangGraph, providing explicit workflow orchestration and a path to later conversation persistence and streaming execution.

---

## Initial Implementation

The first implemented graph uses a configurable OpenAI chat model and exposes
two tools: Player Resolver and Analytics Query. It is stateless and returns a
single Markdown response through the chat endpoint. The model is instructed to
resolve player identities before querying statistics, and it has no direct
database access or SQL-generation responsibility.

Conversation persistence, streaming, and visualization selection remain later
implementation steps.

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

### Visualization Tool

Transforms query results into frontend-friendly visualization artifacts.

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
* tool-specific validation

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
