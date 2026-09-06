# 05 - Tools

## Overview

The CurlChat agent delegates specialized work to a small set of tools. Each tool has a clearly defined responsibility and exposes a stable interface to the agent.

This separation allows the agent to focus on understanding user intent and orchestrating workflows, while individual tools encapsulate domain-specific logic.

The current architecture consists of three primary tools:

```text
Player Resolver
        │
        ▼
Analytics Query Tool
        │
        ▼
Visualization Tool
```

Each tool is designed to operate independently and can evolve without requiring significant changes to the agent itself.

The initial LangGraph implementation exposes the Player Resolver and Analytics
Query Tool. The Visualization Tool remains part of the documented architecture
but is not yet wired into the graph.

---

## Design Principles

All tools follow the same architectural principles.

### Single Responsibility

Each tool performs one well-defined task.

Examples include resolving player identities, retrieving analytical data, or preparing visualization artifacts.

Avoiding overlapping responsibilities keeps the overall system easier to understand and maintain.

---

### Stable Contracts

Tools communicate with the agent through structured inputs and outputs rather than implementation-specific details.

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
* resolved event identifiers
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

---

### Safety

The Analytics Query Tool operates using a read-only database connection.

Database access is limited to the analytics schema, and all requests are validated before execution to prevent unsafe operations.

The initial implementation parses each query, permits exactly one read-only
`SELECT` statement, restricts table references to `players`, `events`, and
`player_event_statistics`, binds query parameters separately, and caps returned
rows. The production database role must also remain read-only as defense in
depth.

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

* structured query results
* query metadata

---

### Outputs

* chart specifications
* table definitions
* summary artifacts

The frontend is responsible for rendering these artifacts into interactive user interface components.

---

## Tool Contracts

Each tool exposes a stable contract to the LangGraph agent.

| Tool                 | Input              | Output                       |
| -------------------- | ------------------ | ---------------------------- |
| Player Resolver      | Player names       | Canonical player identifiers |
| Analytics Query Tool | Analytical request | Structured query results     |
| Visualization Tool   | Query results      | Visualization artifacts      |

The agent interacts only with these contracts.

Internal implementation details remain encapsulated within each tool.

---

## Summary

The tool architecture separates conversational reasoning from domain-specific implementation.

By assigning each tool a single responsibility and a well-defined interface, CurlChat remains modular, testable, and extensible while allowing individual components to evolve independently.
