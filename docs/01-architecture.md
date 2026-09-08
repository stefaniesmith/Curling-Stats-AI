# System Architecture

## Purpose

This document describes the high-level architecture of CurlChat and defines the responsibilities of each layer of the application.

The primary goal of the architecture is to separate **AI reasoning** from **application logic**. The language model is responsible for understanding user intent and planning actions, while deterministic application code is responsible for data access, validation, business rules, and presentation.

This separation produces an application that is easier to test, easier to maintain, and safer than embedding application logic inside prompts.

---

# Architectural Principles

The application is built around a small number of guiding principles.

## AI is an orchestrator, not the application

The AI agent should coordinate application functionality rather than implement it.

The language model should:

* Understand user intent
* Plan a sequence of actions
* Decide which tools to use
* Generate analytical SQL
* Decide how information should be presented
* Explain results to the user

The language model should **not**:

* Resolve player names
* Access the database directly
* Build charts
* Validate SQL
* Implement business rules

Those responsibilities belong to deterministic application code.

---

## Application logic is deterministic

Application services should behave identically regardless of whether they are called by:

* LangGraph
* A REST endpoint
* A scheduled task
* Unit tests
* Future applications

The AI layer should be optional rather than foundational.

---

## Single Responsibility

Each layer owns one responsibility.

| Layer                | Responsibility                              |
| -------------------- | ------------------------------------------- |
| React                | User interface                              |
| FastAPI              | HTTP API and streaming                      |
| LangGraph            | Conversation orchestration                  |
| Tools                | Expose application functionality to the LLM |
| Application Services | Business and application logic              |
| Database Layer       | Persistence and SQL execution               |
| PostgreSQL           | Persistent storage                          |

---

# High-Level Architecture

```text
                 React
                   │
        Conversation UI
        Charts
        Tables
        Streaming
                   │
                   ▼
               FastAPI
         REST + Streaming API
                   │
                   ▼
             LangGraph Agent
      Planning & Conversation State
                   │
             LangGraph Tools
                   │
                   ▼
         Application Services
                   │
        ┌──────────┼──────────┐
        │          │          │
        ▼          ▼          ▼
 PlayerResolver StatsService VisualizationService
                   │
                   ▼
            Database Layer
      SQLAlchemy + SQL Execution
                   │
                   ▼
              PostgreSQL
```

Each layer communicates only with the layer directly below it.

Lower layers never depend on higher layers.

## Local Portfolio Distribution

The repository includes a Docker Compose configuration intended for local review.
It packages the browser-facing frontend separately from the backend while keeping
the production-style boundary visible:

```text
Browser
  │ http://localhost:5173
  ▼
Nginx frontend container
  │ serves the Vite production build
  │ proxies /api and /api/chat/stream
  ▼
FastAPI backend container ─────────► PostgreSQL container
  │
  └────────────────────────────────► Phoenix container (optional tracing)
```

Nginx disables proxy buffering for the streaming route so Server-Sent Events
reach the browser incrementally. In development, Vite may run directly on the
host instead; its development proxy has the same `/api` contract. The archive
importer is a Compose profile rather than a long-running service. It mounts a
separately cloned archive checkout read-only and writes through the owner
connection, while the running API continues to use restricted runtime roles.

---

# Application Layers

## React

React is responsible for presentation only.

Responsibilities include:

* Conversation list
* Chat interface
* Rendering assistant responses
* Rendering charts
* Rendering tables
* Managing streaming updates
* User interaction

React should never contain business logic or database knowledge.

---

## FastAPI

FastAPI provides the public interface to the backend.

Responsibilities include:

* Request validation
* Response serialization
* Streaming responses
* Error translation
* Routing

FastAPI should remain intentionally thin.

Business logic belongs elsewhere.

---

## LangGraph

LangGraph is the application's orchestration engine.

Responsibilities include:

* Maintaining conversation state
* Understanding user requests
* Planning tool usage
* Executing tools
* Generating assistant responses
* Persisting conversational context

LangGraph should never directly access PostgreSQL.

Every interaction with application data occurs through tools.

---

## Tools

Tools expose deterministic application functionality to the language model.

Examples include:

* Resolving player names
* Executing statistical queries
* Creating visualizations

Tools should remain extremely small.

A typical tool should do little more than:

1. Validate its inputs.
2. Call an application service.
3. Return the result.

Business logic belongs inside services rather than tools.

---

## Application Services

Application services contain the core functionality of the application.

Examples include:

### PlayerResolver

Responsible for:

* Fuzzy player matching
* Alias handling
* Returning confidence scores

### StatsService

Responsible for:

* Executing bounded analytical SQL through the restricted runtime role
* Returning structured statistical results

### VisualizationService

Responsible for:

* Creating chart specifications
* Creating table specifications
* Producing visualization artifacts

### ConversationService

Responsible for:

* Creating conversations
* Listing conversations
* Managing conversation metadata

Application services should be completely independent of LangGraph.

This allows them to be tested independently and reused elsewhere in the application.

---

## Database Layer

The Database Layer owns all interaction with PostgreSQL.

Responsibilities include:

* SQLAlchemy models
* Database sessions
* Alembic migrations
* Import pipeline
* SQL validation
* Executing validated SQL

The Database Layer does not contain application logic.

Its responsibility is persistence rather than decision making.

---

## PostgreSQL

PostgreSQL serves as the authoritative source for structured data.

It stores:

* Players
* Events
* Statistical records
* Conversation metadata
* LangGraph checkpoints

No other component should duplicate this information.

---

# Request Lifecycle

A typical request follows this sequence.

```text
User

↓

React

↓

FastAPI

↓

LangGraph

↓

Tool

↓

Application Service

↓

Database Layer

↓

PostgreSQL

↓

Structured Results

↓

Application Service

↓

Tool

↓

LangGraph

↓

Streaming Response

↓

React
```

Each component performs one responsibility before passing control to the next layer.

## Observability

Optional OpenTelemetry tracing runs alongside the request lifecycle and exports
agent and tool spans to a self-hosted Phoenix instance. Phoenix is operational
infrastructure: it does not participate in business decisions and does not
store analytics data. See `06-observability.md` for configuration and data
handling.

---

# Conversation Architecture

Each conversation is identified by a unique conversation ID.

The conversation ID is used consistently throughout the application.

It identifies:

* The conversation shown in the frontend
* Conversation metadata
* The LangGraph thread
* The persisted conversation state

A single identifier is used across the entire application to simplify state management.

Conversation metadata is stored in the `conversations` table. It contains a
deterministic title and timestamps, but never duplicates user or assistant
messages. LangGraph's PostgreSQL checkpointer stores message history and graph
state under the same ID as its `thread_id`.

The backend creates a conversation on the first `POST /api/chat` request when
the client omits `conversation_id`. Later requests must send that returned ID;
unknown IDs return `404` rather than creating an untracked LangGraph thread.
`GET /api/conversations` lists metadata for the conversation sidebar.

Two restricted runtime database connections enforce the boundary:

* `curlchat_app` is read-only and can access only analytics tables.
* `curlchat_state` can read and write only `conversations` and LangGraph
  checkpoint tables.

The owner role, `curlchat_owner`, owns these tables and runs migrations. This
means LLM-generated analytics SQL cannot read or modify conversations even if
an application-level validation boundary were to fail.

---

# Visualization Architecture

The AI agent decides whether information should be visualized.

If a visualization is appropriate, the agent calls the Visualization Tool.

The Visualization Service produces a structured visualization artifact.

Example artifact types include:

* Line chart
* Bar chart
* Table

The frontend owns rendering these artifacts.

The backend never generates chart images.

This separation keeps presentation concerns inside React while allowing the AI to decide *what* should be presented.

---

# Streaming Architecture

Assistant responses are streamed to the frontend.

Rather than treating a response as a single message, the application treats each assistant turn as a sequence of content blocks.

An assistant response may contain:

* Markdown
* Charts
* Tables

These blocks may arrive incrementally.

For example, a chart may appear before the assistant has completed its written explanation.

This creates a more responsive user experience and more closely resembles modern AI interfaces.

---

# Why This Architecture?

The architecture intentionally separates AI reasoning from application implementation.

The language model is responsible for making decisions.

The application is responsible for executing those decisions safely and deterministically.

This allows the strengths of modern language models—reasoning, planning, and natural language understanding—to be combined with the reliability, maintainability, and testability of conventional software engineering.

The result is an application that is conversational, extensible, and suitable for production-quality software development.
