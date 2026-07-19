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

* Executing validated analytical SQL
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
