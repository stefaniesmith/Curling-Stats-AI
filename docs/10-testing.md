# 10 - Testing

## Overview

CurlChat uses focused tests at the layer that owns each behavior. Deterministic services, tools, agent-graph boundaries, API routes, and React interaction state are tested without requiring a live OpenAI provider or imported production archive.

## Backend

Backend unit tests use pytest and FastAPI's test client. They mock provider calls and database-facing boundaries where appropriate. The default local URLs, Compose runtime URLs, and role provisioning all use `POSTGRES_PASSWORD` (defaulting to `curlchat`), so no tests need to be deselected for state-checkpointer authentication. Route coverage includes synchronous chat error translation, conversation metadata serialization, and persisted-history reconstruction. Run the suite with `uv run pytest -q` from the backend directory; run `uv run ruff check src tests` for linting.

## Frontend

The frontend uses Vitest, jsdom, and React Testing Library. Plotly is mocked at the component boundary so tests verify CurlChat's artifact-to-chart props without needing browser canvas support.

Initial coverage verifies:

* first-message creation and follow-up conversation IDs
* sidebar history hydration and API-error feedback
* Markdown, summary, and table artifact rendering
* typed HTTP and SSE artifact-contract validation
* multi-series chart colors, title wrapping, and legend spacing
* streaming conversation IDs, deterministic progress statuses, and final Markdown event handling

Run frontend tests with `pnpm test` and create a production bundle with `pnpm build`.
