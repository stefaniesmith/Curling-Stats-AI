# CurlChat - Project Overview

## Overview

CurlChat is an AI-powered conversational analytics platform for Curling Canada athlete statistics. The application allows users to explore historical player performance through natural language, combining large language models, structured statistical data, and interactive visualizations into a single conversational experience.

Unlike a traditional statistics website, CurlChat enables users to ask analytical questions in plain English, such as:

* "Compare Rachel Homan and Jennifer Jones from 2018 to 2024."
* "Who had the highest draw percentage at the 2023 Hearts?"
* "Show Rachelle Brown's shot percentage over time."
* "Which lead had the best takeout percentage in 2019?"

The application interprets each request, retrieves the appropriate data, determines the best way to present the results, and responds using a combination of natural language, tables, and charts.

---

# Goals

The primary goal of this project is to demonstrate the design and implementation of a modern AI-powered web application.
The project emphasizes:

* AI agent orchestration using LangGraph
* Modern Python backend development with FastAPI
* React-based frontend development
* PostgreSQL database design
* SQLAlchemy ORM and database access
* Interactive data visualization
* Streaming AI responses
* Clean software architecture
* Testable, maintainable code

---

# Target Users

The application is intended for:

* Curling fans interested in historical statistics
* Coaches and analysts exploring player performance
* Developers interested in AI-powered analytics applications

Although the initial dataset focuses on Curling Canada statistics, the architecture should remain sufficiently generic that other sports datasets could be incorporated in the future with minimal architectural changes.

---

# Core Features

## Conversational Analytics

Users interact with the application through a conversational interface rather than traditional forms or filters.

The AI assistant should understand natural language requests and maintain conversational context across multiple messages.

---

## Player Search

Users should be able to reference athletes naturally, including handling common misspellings or incomplete names.

Examples:

* "Rachelle Brown"
* "Rachel Brown"
* "Brown"
* "R. Brown"

The application should resolve these references to the appropriate athlete whenever possible.

---

## Statistical Analysis

The assistant should answer questions involving:

* Individual player performance
* Player comparisons
* Event statistics
* Historical trends
* Rankings
* Aggregations
* Filtering by year, event, position, province, and other available dimensions

Analytical queries should be performed against a structured PostgreSQL database.

---

## Visualizations

When appropriate, the assistant should supplement responses with visualizations.

Examples include:

* Line charts
* Bar charts
* Comparison charts
* Sortable tables

The AI agent should determine whether a visualization adds value and select an appropriate presentation.

---

## Persistent Conversations

Users may maintain multiple conversations.

Each conversation preserves its own context, allowing follow-up questions without requiring users to restate previous requests.

Examples:

> Show Rachel Homan's statistics.

> Only after 2020.

> Compare her to Jennifer Jones.

---

## Streaming Responses

Assistant responses should be streamed to the frontend to create a responsive user experience.

Visualizations and other UI artifacts may appear before the assistant has completed generating its textual explanation.

---

# Technology Stack

## Frontend

* React
* TypeScript
* Vite
* Plotly (interactive visualizations)

## Backend

* FastAPI
* LangGraph
* LangChain
* SQLAlchemy
* Pydantic

## Database

* PostgreSQL
* Alembic for schema migrations

---

# Design Principles

The project follows several guiding principles.

## AI for reasoning

The language model is responsible for:

* Understanding user intent
* Planning actions
* Generating SQL queries
* Choosing appropriate visualizations
* Explaining results

## Deterministic application logic

Business logic should remain deterministic wherever practical.

Examples include:

* Player name resolution
* Database access
* SQL validation
* Visualization generation
* Data import

## Separation of concerns

Responsibilities should be clearly divided between:

* Agent orchestration
* Business services
* Database repositories
* API layer
* Frontend presentation

Each component should have a single, well-defined responsibility.

## Structured data over retrieval

Because the source data is highly structured, the application uses a relational database rather than Retrieval-Augmented Generation (RAG).

The language model reasons over structured query results instead of searching document embeddings.

---

# Project Scope

The initial release will include:

* Importing Curling Canada athlete statistics into PostgreSQL
* Conversational AI interface
* Persistent conversations
* AI-generated read-only SQL queries
* Interactive charts and tables
* Streaming assistant responses
* Responsive React frontend

---

# Out of Scope

The following features are intentionally excluded from the initial release:

* User authentication
* User accounts
* Administrative interface
* Live competition data
* Statistical prediction models
* Mobile applications
* Public API for third-party developers

These features may be considered as future enhancements after the core application is complete.

---

# Success Criteria

The project will be considered successful when a user can:

1. Ask analytical questions using natural language.
2. Receive accurate answers derived from structured statistical data.
3. View charts and tables when appropriate.
4. Continue a conversation naturally using follow-up questions.
5. Start multiple independent conversations.
6. Explore historical curling statistics without needing knowledge of SQL or the underlying database.

---

# Vision

CurlChat aims to demonstrate how modern AI agents can provide a more natural and powerful interface for exploring structured analytical data.

Rather than replacing traditional software engineering, the application combines deterministic backend services with AI reasoning to create an experience that is conversational, interactive, and data-driven.
