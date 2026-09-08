"""Internal LangGraph workflow for generating and executing analytics queries."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any, Protocol

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from openai import OpenAIError
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Connection, Engine, inspect

from curlchat.agent.prompts.prompt_loader import sql_generator_system_prompt
from curlchat.core.identities import ResolvedEventIdentity, ResolvedPlayerIdentity
from curlchat.db.session import Settings
from curlchat.services.stats_service import AnalyticsQueryResult, AnalyticsQueryStatus, StatsService

_ANALYTICS_TABLES = ("players", "events", "player_event_statistics")


class GeneratedAnalyticsQuery(BaseModel):
    """The only structured output accepted from the SQL-generation model."""

    supported: bool = Field(description="Whether the request can be answered from the analytics schema.")
    sql: str | None = Field(default=None, description="One read-only PostgreSQL SELECT query.")
    parameters: dict[str, Any] = Field(default_factory=dict)
    reason: str | None = Field(default=None, description="Reason a request is unsupported, if applicable.")


class AnalyticsQueryState(BaseModel):
    """Pydantic state shared by the Analytics Query Tool's internal graph."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    request: str
    resolved_players: tuple[ResolvedPlayerIdentity, ...] = Field(default_factory=tuple)
    resolved_events: tuple[ResolvedEventIdentity, ...] = Field(default_factory=tuple)
    generated_query: GeneratedAnalyticsQuery | None = None
    result: AnalyticsQueryResult | None = None
    retry_count: int = 0
    repair_error: str | None = None
    retryable: bool = False


class SqlGenerator(Protocol):
    """Generates a validated-shape query without executing it."""

    def generate(
        self,
        request: str,
        resolved_players: Sequence[ResolvedPlayerIdentity],
        resolved_events: Sequence[ResolvedEventIdentity],
        repair_error: str | None = None,
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
        resolved_events: Sequence[ResolvedEventIdentity],
        repair_error: str | None = None,
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
                            "resolved_events": [
                                event.model_dump() for event in resolved_events
                            ],
                            "previous_execution_error": repair_error,
                        }
                    )
                ),
            ]
        )
        if not isinstance(result, GeneratedAnalyticsQuery):
            raise TypeError("SQL generator returned an unexpected response type.")
        return result


class AnalyticsQueryWorkflow:
    """Orchestrate SQL generation and deterministic query execution."""

    def __init__(self, stats_service: StatsService, sql_generator: SqlGenerator) -> None:
        self._stats_service = stats_service
        self._sql_generator = sql_generator
        self._graph = self._build_graph()

    def query(
        self,
        request: str,
        resolved_players: Sequence[ResolvedPlayerIdentity] = (),
        resolved_events: Sequence[ResolvedEventIdentity] = (),
    ) -> AnalyticsQueryResult:
        """Fulfill an analytical request without exposing SQL to the main agent."""
        final_state = AnalyticsQueryState.model_validate(
            self._graph.invoke(
                AnalyticsQueryState(
                    request=request,
                    resolved_players=tuple(resolved_players),
                    resolved_events=tuple(resolved_events),
                ).model_dump()
            )
        )
        return final_state.result or AnalyticsQueryResult(
            status=AnalyticsQueryStatus.EXECUTION_FAILURE,
            message="The analytics query could not be completed.",
        )

    def _build_graph(self):
        graph = StateGraph(AnalyticsQueryState)
        graph.add_node("generate_query", self._generate_query)
        graph.add_node("execute_query", self._execute_query)
        graph.add_edge(START, "generate_query")
        graph.add_edge("generate_query", "execute_query")
        graph.add_conditional_edges(
            "execute_query",
            self._next_step,
            {"retry": "generate_query", "complete": END},
        )
        return graph.compile()

    def _generate_query(self, state: AnalyticsQueryState) -> dict[str, object]:
        try:
            generated_query = self._sql_generator.generate(
                state.request,
                state.resolved_players,
                state.resolved_events,
                state.repair_error,
            )
        except (OpenAIError, TypeError, ValueError):
            return {
                "result": AnalyticsQueryResult(
                    status=AnalyticsQueryStatus.EXECUTION_FAILURE,
                    message="The analytics query could not be generated.",
                )
            }
        updates: dict[str, object] = {
            "generated_query": generated_query,
            "result": None,
            "retryable": False,
        }
        if state.repair_error is not None:
            updates["retry_count"] = state.retry_count + 1
        return updates

    def _execute_query(self, state: AnalyticsQueryState) -> dict[str, object]:
        if state.result is not None:
            return {}
        generated_query = state.generated_query
        if generated_query is None:
            return {
                "result": AnalyticsQueryResult(
                    status=AnalyticsQueryStatus.EXECUTION_FAILURE,
                    message="The analytics query could not be generated.",
                )
            }
        if not generated_query.supported:
            return {
                "result": AnalyticsQueryResult(
                    status=AnalyticsQueryStatus.UNSUPPORTED,
                    message=generated_query.reason
                    or "This request is not supported by the analytics data.",
                )
            }
        if not generated_query.sql:
            return {
                "result": AnalyticsQueryResult(
                    status=AnalyticsQueryStatus.EXECUTION_FAILURE,
                    message="The analytics query could not be generated.",
                )
            }
        result = self._stats_service.execute(generated_query.sql, generated_query.parameters)
        retryable = result.status is not AnalyticsQueryStatus.SUCCESS
        if retryable and state.retry_count >= 1:
            return {
                "result": AnalyticsQueryResult(
                    status=AnalyticsQueryStatus.EXECUTION_FAILURE,
                    message="The analytics query could not be completed after a repair attempt.",
                ),
                "retryable": False,
            }
        updates: dict[str, object] = {"result": result, "retryable": retryable}
        if retryable and state.retry_count < 1:
            updates["repair_error"] = result.message or "The previous query could not run."
        return updates

    @staticmethod
    def _next_step(state: AnalyticsQueryState) -> str:
        if (
            state.retryable
            and state.retry_count < 1
            and state.result is not None
        ):
            return "retry"
        return "complete"


def analytics_schema_description(bind: Engine | Connection) -> str:
    """Create SQL-model context from live analytics database metadata."""
    inspector = inspect(bind)
    descriptions: list[str] = []
    for table in _ANALYTICS_TABLES:
        columns = inspector.get_columns(table)
        primary_key = set(inspector.get_pk_constraint(table).get("constrained_columns") or ())
        foreign_keys = {
            column: f"{foreign_key['referred_table']}.{foreign_key['referred_columns'][index]}"
            for foreign_key in inspector.get_foreign_keys(table)
            for index, column in enumerate(foreign_key["constrained_columns"])
        }
        table_comment = _table_comment(inspector, table)
        heading = table if not table_comment else f"{table} — {table_comment}"
        lines = [heading]
        for column in columns:
            details = [str(column["type"]).upper(), "NULL" if column["nullable"] else "NOT NULL"]
            if column["name"] in primary_key:
                details.append("PRIMARY KEY")
            if reference := foreign_keys.get(column["name"]):
                details.append(f"REFERENCES {reference}")
            if default := column.get("default"):
                details.append(f"DEFAULT {default}")
            if comment := column.get("comment"):
                details.append(str(comment))
            lines.append(f"- {column['name']}: {'; '.join(details)}")
        for constraint in inspector.get_check_constraints(table):
            if sqltext := constraint.get("sqltext"):
                lines.append(f"- CHECK: {sqltext}")
        descriptions.append("\n".join(lines))
    return "\n\n".join(descriptions)


def _table_comment(inspector: Any, table: str) -> str | None:
    """Read optional table documentation without requiring every dialect to support it."""
    try:
        comment = inspector.get_table_comment(table).get("text")
    except NotImplementedError:
        return None
    return str(comment) if comment else None


def sql_generation_prompt(schema_description: str) -> str:
    """Build the SQL model's scoped prompt from live database metadata."""
    return sql_generator_system_prompt(schema_description)
