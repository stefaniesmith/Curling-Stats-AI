"""Scoped SQL generation and execution behind the analytics-query boundary."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any, Protocol

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from openai import OpenAIError
from pydantic import BaseModel, Field
from sqlalchemy import Connection, Engine, inspect

from curlchat.db.session import Settings
from curlchat.services.stats_service import AnalyticsQueryResult, AnalyticsQueryStatus, StatsService

_ANALYTICS_TABLES = ("players", "events", "player_event_statistics")


class GeneratedAnalyticsQuery(BaseModel):
    """The only structured output accepted from the SQL-generation model."""

    supported: bool = Field(description="Whether the request can be answered from the analytics schema.")
    sql: str | None = Field(default=None, description="One read-only PostgreSQL SELECT query.")
    parameters: dict[str, Any] = Field(default_factory=dict)
    reason: str | None = Field(default=None, description="Reason a request is unsupported, if applicable.")


class ResolvedPlayerIdentity(BaseModel):
    """A player identity passed between the resolver and analytics boundaries."""

    display_name: str = Field(description="The resolved player's display name.")
    player_id: int = Field(description="The resolved player's database identifier.")


class SqlGenerator(Protocol):
    """Generates a validated-shape query without executing it."""

    def generate(
        self,
        request: str,
        resolved_players: Sequence[ResolvedPlayerIdentity],
        event_ids: Sequence[int],
    ) -> GeneratedAnalyticsQuery: ...


class OpenAISqlGenerator:
    """A narrow model client used only by the Analytics Query Tool."""

    def __init__(self, settings: Settings, schema_description: str) -> None:
        if settings.openai_api_key is None:
            raise ValueError("OPENAI_API_KEY is not configured.")
        self._schema_description = schema_description
        self._model = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key.get_secret_value(),
            temperature=0,
            max_completion_tokens=600,
        ).with_structured_output(GeneratedAnalyticsQuery, method="function_calling")

    def generate(
        self,
        request: str,
        resolved_players: Sequence[ResolvedPlayerIdentity],
        event_ids: Sequence[int],
    ) -> GeneratedAnalyticsQuery:
        result = self._model.invoke(
            [
                SystemMessage(sql_generation_prompt(self._schema_description)),
                HumanMessage(
                    json.dumps(
                        {
                            "request": request,
                            "resolved_players": [
                                player.model_dump() for player in resolved_players
                            ],
                            "resolved_event_ids": list(event_ids),
                        }
                    )
                ),
            ]
        )
        if not isinstance(result, GeneratedAnalyticsQuery):
            raise TypeError("SQL generator returned an unexpected response type.")
        return result


class AnalyticsQueryService:
    """Own SQL generation, SQL validation, execution, and query outcomes."""

    def __init__(self, stats_service: StatsService, sql_generator: SqlGenerator) -> None:
        self._stats_service = stats_service
        self._sql_generator = sql_generator

    def query(
        self,
        request: str,
        resolved_players: Sequence[ResolvedPlayerIdentity] = (),
        event_ids: Sequence[int] = (),
    ) -> AnalyticsQueryResult:
        """Fulfill an analytical request without exposing SQL to the main agent."""
        try:
            generated_query = self._sql_generator.generate(request, resolved_players, event_ids)
        except (OpenAIError, TypeError, ValueError):
            return AnalyticsQueryResult(
                status=AnalyticsQueryStatus.EXECUTION_FAILURE,
                message="The analytics query could not be generated.",
            )
        if not generated_query.supported:
            return AnalyticsQueryResult(
                status=AnalyticsQueryStatus.UNSUPPORTED,
                message=generated_query.reason or "This request is not supported by the analytics data.",
            )
        if not generated_query.sql:
            return AnalyticsQueryResult(
                status=AnalyticsQueryStatus.EXECUTION_FAILURE,
                message="The analytics query could not be generated.",
            )
        return self._stats_service.execute(generated_query.sql, generated_query.parameters)


def analytics_schema_description(bind: Engine | Connection) -> str:
    """Create SQL-model context from live analytics database metadata."""
    inspector = inspect(bind)
    return "\n".join(
        f"{table}: " + ", ".join(column["name"] for column in inspector.get_columns(table))
        for table in _ANALYTICS_TABLES
    )


def sql_generation_prompt(schema_description: str) -> str:
    """Build the SQL model's scoped prompt from live database metadata."""
    return f"""You generate PostgreSQL SELECT queries for CurlChat's Analytics Query Tool.
Return a structured result that is either supported with one query and bound parameters,
or unsupported with a concise reason. Never resolve player names. Each resolved player
in the request contains an authoritative display_name and player_id pair; preserve that
mapping, especially when comparing players. Never write data, use multiple statements,
or query tables outside this schema:

{schema_description}

Join player_event_statistics.player_id to players.id and
player_event_statistics.event_id to events.id. Use supplied resolved player or event
IDs as SQLAlchemy-style named bound parameters whenever they constrain the request,
for example `p.id = :player_id` with `{{ "player_id": 123 }}`. Never use PostgreSQL
positional placeholders such as `$1`. If the request names an event and no resolved
event ID is supplied, join `events` and filter its display_name with a named parameter.
Do not invent columns.
"""
