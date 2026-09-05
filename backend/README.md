# CurlChat backend

Initial backend scaffold aligned with the repository architecture docs.

Planned implementation order:

1. SQLAlchemy models
2. Alembic migrations
3. Import pipeline
4. Player resolver service
5. Stats service
6. LangGraph tool wrappers
7. Streaming chat endpoint

Suggested local commands after dependencies are installed:

- `uv sync`
- `uv run uvicorn curlchat.main:app --reload`
- `uv run pytest`
