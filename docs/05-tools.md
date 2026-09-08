# 05 - Tools

## Overview

The CurlChat agent delegates specialized work to a small set of tools. Each tool has a clearly defined responsibility and exposes a stable interface to the agent.

This separation allows the agent to focus on understanding user intent and orchestrating workflows, while individual tools encapsulate domain-specific logic.

The current architecture consists of four primary tools:

```text
Player Resolver
        │
        ▼
Event Resolver
        │
        ▼
Analytics Query Tool
        │
        ▼
Visualization Tool
```

Each tool is designed to operate independently and can evolve without requiring significant changes to the agent itself.

The initial LangGraph implementation exposes all four tools. The Visualization
Tool creates artifacts from an already-successful Analytics Query Tool result;
it never queries the database or renders charts itself.

---

## Design Principles

All tools follow the same architectural principles.

### Single Responsibility

Each tool performs one well-defined task.

Examples include resolving player identities, retrieving analytical data, or preparing visualization artifacts.

Avoiding overlapping responsibilities keeps the overall system easier to understand and maintain.

---

### Stable Contracts

Tools communicate with the agent through Pydantic-validated structured inputs and
outputs rather than implementation-specific details.

The agent depends only on each tool's contract, allowing the internal implementation to change without affecting the rest of the application.

---

### Encapsulation

Implementation details remain internal to each tool.

For example, the Analytics Query Tool is responsible for fulfilling analytical data requests, but the agent does not need to know how those requests are translated into database queries.

---

### Deterministic Behavior

Whenever possible, deterministic application logic is preferred over AI reasoning.

Language models are used where interpretation or reasoning is required, while business logic, validation, and data access remain deterministic.

---

### Independent Testing

Each tool should be testable in isolation.

This allows functionality to be verified without requiring the entire conversational workflow to execute.

---

## Player Resolver

### Purpose

The Player Resolver converts player names supplied by the user into canonical player identities used throughout the application.

This hides historical aliases and alternate spellings from the rest of the system.

---

### Responsibilities

* resolve player aliases
* identify canonical player records
* handle historical player names
* return canonical player identifiers

---

### Inputs

* player names extracted from the user's request

---

### Outputs

* canonical player identifiers
* canonical player names

---

### Workflow

```text
Player Name
        │
        ▼
Alias Resolution
        │
        ▼
Canonical Player
```

The Player Resolver is responsible only for identity resolution.

It does not generate analytical queries or access player statistics.

---

## Event Resolver

### Purpose

The Event Resolver converts a named competition into a canonical event identity
used by the Analytics Query Tool.

### Responsibilities

* match an exact event display name or source slug
* match clear event shorthand or spelling variations
* return ambiguity rather than silently combining distinct competitions

### Inputs

* event names extracted from the user's request; a year in the phrase is ignored
* optional resolved player identities, used only to narrow ambiguous event candidates

### Outputs

* canonical event identity pairs (`display_name` and `event_id`)
* ambiguous event candidates when clarification is required

For example, “Canada Cup” produces the distinct men's and women's event
candidates as an ambiguous result. The agent must ask the user to choose, or
explicitly resolve both events if the user asks for both.

When resolved player identities are supplied, the resolver may narrow an
ambiguous event only if exactly one candidate contains source statistics for
every supplied player. This is a data-based disambiguation rule; it does not
infer personal attributes from a player's name.

---

## Analytics Query Tool

### Purpose

The Analytics Query Tool fulfills analytical data requests against the Curling Canada statistics database.

It acts as the boundary between the conversational agent and the analytics database, returning structured results that the agent can interpret.

---

### Responsibilities

* determine whether an analytical request can be fulfilled
* retrieve data from the analytics database
* return structured query results
* communicate unsupported requests when appropriate

---

### Inputs

* analytical request
* resolved player identity pairs (`display_name` and `player_id`)
* resolved event identity pairs (`display_name` and `event_id`)
* analytics schema description

---

### Outputs

The tool returns one of three outcomes:

* successful query results
* unsupported request
* execution failure

The agent determines how each outcome should be presented to the user.

---

### Internal Workflow

The Analytics Query Tool encapsulates the complete workflow required to fulfill analytical requests.

Its implementation includes query planning, validation, execution, and error handling. These implementation details remain internal to the tool and are intentionally hidden from the agent.

This separation allows the internal implementation to evolve independently while preserving a stable interface.

The current implementation invokes a two-node internal LangGraph from the
agent layer, with Pydantic state: an LLM generation node produces a structured
query, then a deterministic node checks the one-statement contract and executes
it. A validation or execution failure returns the failed SQL, bound parameters,
and a concise database diagnostic to the generation node for one repair attempt;
the user-facing error remains sanitized. A second failure is returned as an execution failure; a
model-declared unsupported request does not retry.

---

### Safety

The Analytics Query Tool operates using a read-only database connection.

The database role is the authoritative access boundary: it is read-only and
has access only to analytics tables. The application accepts one statement per
request, binds query parameters separately, sets a database-side statement
timeout, and caps returned rows. It deliberately does not maintain a
parser-based table allow-list, so ordinary PostgreSQL constructs such as CTEs,
unions, subqueries, and window functions remain available to generated SQL.
Before SQL generation, the tool deterministically verifies every supplied
Player Resolver and Event Resolver display-name/ID pair against the imported
identity catalogs. A mismatch is rejected rather than querying an identity
identified by a fabricated ID.

The agent-facing contract accepts an analytical request and resolved player
identity pairs (`display_name` and `player_id`), not SQL. Keeping each name
paired with its ID means comparison requests retain the exact identity mapping
through SQL generation. Event identifiers will join the contract when an Event
Resolver exists. Internally, the tool supplies a separate SQL-generation model
with a schema description inspected from the live analytics database, then
validates and executes the generated query.

---

## Visualization Tool

### Purpose

The Visualization Tool transforms analytical query results into structured visualization artifacts suitable for rendering by the frontend.

The tool does not render charts itself.

---

### Responsibilities

* determine appropriate visualization types
* prepare chart specifications
* prepare tabular data
* generate summary statistics when appropriate

---

### Inputs

* a Pydantic-discriminated visualization specification with a `type` of
  `table`, `summary`, or `chart`

The successful query result is injected from the LangGraph conversation state,
not supplied by the agent. The query tool records the original typed result as
the latest successful result while returning a readable serialized copy to the
model. This keeps the visualization call small, prevents copied values from
changing type, and lets a follow-up request reuse the prior result.

---

### Outputs

* chart specifications
* table definitions
* summary artifacts

The frontend is responsible for rendering these artifacts into interactive user interface components.

### Initial Artifact Contract

The first implementation creates exactly one artifact per tool call. It
supports:

* `table`, preserving the analytics columns and rows
* `summary`, using an explicit deterministic `average`, `minimum`, `maximum`,
  or `sum` over one numeric result column
* `chart`, using an explicit `bar`, `line`, or `dot` renderer and either a
  `long` row-based mapping with validated x- and numeric y-axis columns, or a
  `wide` mapping that reshapes selected numeric stat columns into categories;
  an optional series column produces grouped bars or multiple line/dot traces

The agent decides whether an artifact improves the answer and, for a chart,
which supported renderer suits the result. The service validates its selected
fields and builds only the frontend-ready payload. Invalid requests return a
structured tool error rather than silently changing the visualization.

The agent-facing input is one typed `spec` object. The specification is a
discriminated union: the table variant exposes only a title;
the summary variant requires a value column and aggregation; and the chart
variant requires its renderer plus a typed `long` or `wide` data mapping. This
keeps unrelated fields out of each tool call shape.

---

## Tool Contracts

Each tool exposes a stable contract to the LangGraph agent.

| Tool                 | Input              | Output                       |
| -------------------- | ------------------ | ---------------------------- |
| Player Resolver      | Player names       | Canonical player identities  |
| Event Resolver       | Event names        | Canonical event identities   |
| Analytics Query Tool | Analytical request | Structured query results     |
| Visualization Tool   | Visualization spec | Visualization artifacts      |

The agent interacts only with these contracts.

Internal implementation details remain encapsulated within each tool.

---

## Summary

The tool architecture separates conversational reasoning from domain-specific implementation.

By assigning each tool a single responsibility and a well-defined interface, CurlChat remains modular, testable, and extensible while allowing individual components to evolve independently.
