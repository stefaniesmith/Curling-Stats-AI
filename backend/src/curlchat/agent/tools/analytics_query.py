"""Analytics-query boundary and LangChain tool."""

from __future__ import annotations

from typing import Annotated

from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId, tool
from langgraph.types import Command
from pydantic import BaseModel, Field

from curlchat.agent.graph.analytics_query_graph import (
    AnalyticsQueryWorkflow,
    OpenAISqlGenerator,
    analytics_schema_description,
)
from curlchat.core.identities import ResolvedEventIdentity, ResolvedPlayerIdentity
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


def run_analytics_query(
    request: str,
    resolved_players: list[ResolvedPlayerIdentity] | None = None,
    resolved_events: list[ResolvedEventIdentity] | None = None,
) -> AnalyticsQueryResult:
    """Run the deterministic analytics workflow behind the agent tool."""
    with SessionLocal() as session:
        workflow = AnalyticsQueryWorkflow(
            StatsService(AnalyticsRepository(session)),
            OpenAISqlGenerator(get_settings(), analytics_schema_description(session.get_bind())),
        )
        return workflow.query(request, resolved_players or (), resolved_events or ())


@tool
def query_analytics(
    request: Annotated[
        str,
        Field(description="The user's analytical question in natural language, never SQL."),
    ],
    tool_call_id: Annotated[str, InjectedToolCallId],
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
) -> Command:
    """Answer an analytical request using resolved identities; never provide SQL."""
    result = run_analytics_query(request, resolved_players, resolved_events)
    update: dict[str, object] = {
        "messages": [
            ToolMessage(
                content=AnalyticsQueryToolResult.from_workflow_result(result).model_dump_json(),
                tool_call_id=tool_call_id,
            )
        ]
    }
    if result.status is AnalyticsQueryStatus.SUCCESS:
        update["latest_analytics_result"] = {"columns": result.columns, "rows": result.rows}
    return Command(update=update)
