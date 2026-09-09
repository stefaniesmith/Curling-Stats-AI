"""Validation and execution of read-only analytics queries."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError

from curlchat.repositories.analytics import AnalyticsRepository

_MAXIMUM_ROWS = 500
_STATEMENT_TIMEOUT_MS = 5_000


class AnalyticsQueryStatus(StrEnum):
    """Structured outcomes exposed by the analytics-query tool."""

    SUCCESS = "success"
    UNSUPPORTED = "unsupported"
    EXECUTION_FAILURE = "execution_failure"


class AnalyticsQueryResult(BaseModel):
    """Rows and metadata returned by one validated analytics query."""

    status: AnalyticsQueryStatus
    columns: tuple[str, ...] = Field(default_factory=tuple)
    rows: tuple[dict[str, Any], ...] = Field(default_factory=tuple)
    truncated: bool = False
    message: str | None = None
    repair_error: str | None = None


class StatsService:
    """Execute one analytics statement through the restricted database role."""

    def __init__(
        self,
        repository: AnalyticsRepository,
        row_limit: int = _MAXIMUM_ROWS,
        statement_timeout_ms: int = _STATEMENT_TIMEOUT_MS,
    ) -> None:
        if row_limit < 1:
            raise ValueError("row_limit must be at least one.")
        if statement_timeout_ms < 1:
            raise ValueError("statement_timeout_ms must be at least one.")
        self._repository = repository
        self._row_limit = row_limit
        self._statement_timeout_ms = statement_timeout_ms

    def execute(self, sql: str, parameters: dict[str, Any] | None = None) -> AnalyticsQueryResult:
        """Execute one statement with bound parameters and bounded resource use."""
        try:
            validated_sql = self._single_statement_sql(sql)
        except QueryValidationError as error:
            return AnalyticsQueryResult(status=AnalyticsQueryStatus.UNSUPPORTED, message=str(error))

        try:
            columns, rows, truncated = self._repository.execute(
                validated_sql,
                parameters or {},
                self._row_limit,
                self._statement_timeout_ms,
            )
        except SQLAlchemyError as error:
            self._repository.rollback()
            return AnalyticsQueryResult(
                status=AnalyticsQueryStatus.EXECUTION_FAILURE,
                message="The analytics query could not be executed.",
                repair_error=_database_error_for_repair(error),
            )
        return AnalyticsQueryResult(
            status=AnalyticsQueryStatus.SUCCESS,
            columns=columns,
            rows=rows,
            truncated=truncated,
        )

    @staticmethod
    def _single_statement_sql(sql: str) -> str:
        validated_sql = sql.strip()
        if validated_sql.endswith(";"):
            validated_sql = validated_sql[:-1].rstrip()
        if not validated_sql:
            raise QueryValidationError("An analytics query is required.")
        if ";" in validated_sql:
            raise QueryValidationError(
                "Exactly one analytics query is allowed without a semicolon."
            )
        return validated_sql


class QueryValidationError(ValueError):
    """A query violates the single-statement analytics-tool contract."""


def _database_error_for_repair(error: SQLAlchemyError) -> str:
    """Extract a concise database diagnostic without exposing it to the user."""
    original_error = getattr(error, "orig", None)
    diagnostics = getattr(original_error, "diag", None)
    primary_message = getattr(diagnostics, "message_primary", None)
    sqlstate = getattr(diagnostics, "sqlstate", None)
    if primary_message:
        prefix = f"PostgreSQL error {sqlstate}: " if sqlstate else "PostgreSQL error: "
        return f"{prefix}{primary_message}"[:500]
    return str(original_error or error).splitlines()[0][:500]
