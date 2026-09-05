# CurlChat backend

Initial backend scaffold aligned with the repository architecture docs.

Planned implementation order:

1. Import pipeline
2. Player resolver service
3. Stats service
4. LangGraph tool wrappers
5. Streaming chat endpoint

Suggested local commands after dependencies are installed:

- `uv sync`
- `uv run alembic upgrade head`
- `uv run uvicorn curlchat.main:app --reload`
- `uv run pytest`
