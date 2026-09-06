"""Validation and execution of read-only analytics queries."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlglot import exp, parse
from sqlglot.errors import ParseError

from curlchat.repositories.analytics import AnalyticsRepository

_ALLOWED_TABLES = frozenset({"players", "events", "player_event_statistics"})
_MAXIMUM_ROWS = 500


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


class StatsService:
    """Run validated, read-only SQL against CurlChat analytics data."""

    def __init__(self, repository: AnalyticsRepository, row_limit: int = _MAXIMUM_ROWS) -> None:
        if row_limit < 1:
            raise ValueError("row_limit must be at least one.")
        self._repository = repository
        self._row_limit = row_limit

    def execute(
        self, sql: str, parameters: dict[str, Any] | None = None
    ) -> AnalyticsQueryResult:
        """Validate and execute one SQL SELECT statement with bound parameters."""
        try:
            validated_sql = self._validated_sql(sql)
        except QueryValidationError as error:
            return AnalyticsQueryResult(
                status=AnalyticsQueryStatus.UNSUPPORTED, message=str(error)
            )

        try:
            columns, rows, truncated = self._repository.execute(
                validated_sql, parameters or {}, self._row_limit
            )
        except SQLAlchemyError:
            return AnalyticsQueryResult(
                status=AnalyticsQueryStatus.EXECUTION_FAILURE,
                message="The analytics query could not be executed.",
            )
        return AnalyticsQueryResult(
            status=AnalyticsQueryStatus.SUCCESS,
            columns=columns,
            rows=rows,
            truncated=truncated,
        )

    @staticmethod
    def _validated_sql(sql: str) -> str:
        validated_sql = sql.strip()
        if validated_sql.endswith(";"):
            validated_sql = validated_sql[:-1].rstrip()
        if not validated_sql:
            raise QueryValidationError("An analytics query is required.")
        if ";" in validated_sql:
            raise QueryValidationError("Exactly one analytics query is allowed without a semicolon.")
        try:
            statements = parse(validated_sql, read="postgres")
        except ParseError as error:
            raise QueryValidationError("The analytics query is not valid PostgreSQL SQL.") from error
        if len(statements) != 1:
            raise QueryValidationError("Exactly one analytics query is allowed.")

        statement = statements[0]
        if not isinstance(statement, (exp.Select, exp.Union, exp.Intersect, exp.Except)):
            raise QueryValidationError("Only read-only SELECT queries are supported.")
        forbidden_expression = next(
            (
                expression
                for expression in statement.walk()
                if isinstance(
                    expression,
                    (
                        exp.Delete,
                        exp.Insert,
                        exp.Update,
                        exp.Create,
                        exp.Drop,
                        exp.Alter,
                        exp.Command,
                    ),
                )
            ),
            None,
        )
        if forbidden_expression is not None:
            raise QueryValidationError("Only read-only SELECT queries are supported.")

        tables = tuple(statement.find_all(exp.Table))
        if not tables:
            raise QueryValidationError("Analytics queries must read from an approved analytics table.")
        disallowed_table = next(
            (
                table
                for table in tables
                if table.name.casefold() not in _ALLOWED_TABLES or table.db
            ),
            None,
        )
        if disallowed_table is not None:
            raise QueryValidationError(
                "Analytics queries may only read players, events, and player_event_statistics."
            )
        return validated_sql


class QueryValidationError(ValueError):
    """A query violated the analytics tool's read-only contract."""
