"""Read-only execution of validated analytics queries."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


class AnalyticsRepository:
    """Execute pre-validated queries without exposing ORM implementation details."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def execute(
        self, sql: str, parameters: dict[str, Any], row_limit: int
    ) -> tuple[tuple[str, ...], tuple[dict[str, Any], ...], bool]:
        """Execute SQL and return its columns, capped rows, and truncation state."""
        limited_sql = f"SELECT * FROM ({sql}) AS analytics_query LIMIT :_curlchat_row_limit"
        result = self._session.execute(
            text(limited_sql), {**parameters, "_curlchat_row_limit": row_limit + 1}
        )
        rows = tuple(dict(row) for row in result.mappings())
        return tuple(result.keys()), rows[:row_limit], len(rows) > row_limit
