# CurlChat backend

Initial backend scaffold aligned with the repository architecture docs.

Planned implementation order:

1. Import pipeline
2. Player resolver service
3. Stats service
4. LangGraph tool wrappers
5. Conversation persistence
6. Streaming chat endpoint

Suggested local commands after dependencies are installed:

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
