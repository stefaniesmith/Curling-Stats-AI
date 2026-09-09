# CurlChat backend

FastAPI, PostgreSQL, and LangGraph provide CurlChat's conversational analytics
backend. The application keeps orchestration, deterministic services,
repositories, API routes, and archive ingestion as explicit layers.

## Included capabilities

* idempotent Curling Canada archive import and Alembic migrations
* deterministic player and event resolution
* read-only, bounded analytics SQL execution through a restricted database role
* LangGraph conversation persistence, streaming, and frontend-ready artifacts

## Run locally

- `uv sync`
- `uv run alembic upgrade head`
- `uv run python scripts/provision_app_role.py`
- `uv run python -m curlchat.ingest.cli --source /path/to/curling-canada-stats-archive`
- `uv run uvicorn curlchat.main:app --reload`
- `uv run pytest`

`ADMIN_DATABASE_URL` uses `curlchat_owner` for Alembic and archive import.
`DATABASE_URL` uses the `curlchat_app` runtime role, which has `SELECT` access
to the analytics tables only. `STATE_DATABASE_URL` uses `curlchat_state`, which
can access conversation metadata and LangGraph checkpoint tables only.

## Quality checks

Run `uv run ruff check src tests` for linting and `uv run pytest -q` for the
backend test suite.
