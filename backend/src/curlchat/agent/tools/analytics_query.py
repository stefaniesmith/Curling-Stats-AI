"""Analytics-query boundary and LangChain tool."""

from __future__ import annotations

from typing import Annotated

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from curlchat.agent.graph.analytics_query_graph import (
    AnalyticsQueryWorkflow,
    OpenAISqlGenerator,
    ResolvedEventIdentity,
    ResolvedPlayerIdentity,
    analytics_schema_description,
)
from curlchat.db.session import SessionLocal, get_settings
from curlchat.repositories.analytics import AnalyticsRepository
from curlchat.services.stats_service import AnalyticsQueryResult, AnalyticsQueryStatus, StatsService


class AnalyticsQueryToolResult(BaseModel):
    """Structured output returned by the Analytics Query Tool."""

    status: AnalyticsQueryStatus
    columns: tuple[str, ...] = Field(default_factory=tuple)
    rows: tuple[dict[str, object], ...] = Field(default_factory=tuple)
    truncated: bool = False
    message: str | None = None

    @classmethod
    def from_workflow_result(cls, result: AnalyticsQueryResult) -> AnalyticsQueryToolResult:
        return cls(
            status=result.status,
            columns=result.columns,
            rows=result.rows,
            truncated=result.truncated,
            message=result.message,
        )


@tool
def query_analytics(
    request: Annotated[
        str,
        Field(description="The user's analytical question in natural language, never SQL."),
    ],
    resolved_players: Annotated[
        list[ResolvedPlayerIdentity] | None,
        Field(
            description=(
                "Successful Player Resolver results only. Each display_name/player_id pair "
                "preserves the identity mapping for this request."
            )
        ),
    ] = None,
    resolved_events: Annotated[
        list[ResolvedEventIdentity] | None,
        Field(
            description=(
                "Successful Event Resolver results only. Each display_name/event_id pair "
                "preserves the event identity for this request."
            )
        ),
    ] = None,
) -> str:
    """Answer an analytical request using resolved identities; never provide SQL."""
    with SessionLocal() as session:
        workflow = AnalyticsQueryWorkflow(
            StatsService(AnalyticsRepository(session)),
            OpenAISqlGenerator(get_settings(), analytics_schema_description(session.get_bind())),
        )
        result = workflow.query(request, resolved_players or (), resolved_events or ())
    return AnalyticsQueryToolResult.from_workflow_result(result).model_dump_json()
