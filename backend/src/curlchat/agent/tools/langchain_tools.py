"""LangChain adapters for CurlChat's deterministic application tools."""

from __future__ import annotations

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from curlchat.agent.graph.analytics_query_graph import (
    AnalyticsQueryWorkflow,
    OpenAISqlGenerator,
    ResolvedPlayerIdentity,
    analytics_schema_description,
)
from curlchat.agent.tools.player_resolver import resolve_player_name
from curlchat.db.session import SessionLocal, get_settings
from curlchat.repositories.analytics import AnalyticsRepository
from curlchat.services.player_resolver import PlayerResolutionStatus
from curlchat.services.stats_service import AnalyticsQueryResult, AnalyticsQueryStatus, StatsService


class ResolvedPlayerMatch(BaseModel):
    """One player candidate exposed by the Player Resolver tool."""

    player_id: int
    display_name: str
    confidence: float
    matched_alias: bool


class PlayerResolutionToolResult(BaseModel):
    """Structured output returned by the Player Resolver tool."""

    query: str
    status: PlayerResolutionStatus
    matches: tuple[ResolvedPlayerMatch, ...] = Field(default_factory=tuple)


class AnalyticsQueryToolResult(BaseModel):
    """Structured output returned by the Analytics Query Tool."""

    status: AnalyticsQueryStatus
    columns: tuple[str, ...] = Field(default_factory=tuple)
    rows: tuple[dict[str, object], ...] = Field(default_factory=tuple)
    truncated: bool = False
    message: str | None = None

    @classmethod
    def from_service_result(cls, result: AnalyticsQueryResult) -> AnalyticsQueryToolResult:
        return cls(
            status=result.status,
            columns=result.columns,
            rows=result.rows,
            truncated=result.truncated,
            message=result.message,
        )


@tool
def resolve_player(name: str) -> str:
    """Resolve a player name before asking a question about that player's statistics."""
    with SessionLocal() as session:
        resolution = resolve_player_name(session, name)
    return PlayerResolutionToolResult(
        query=resolution.query,
        status=resolution.status,
        matches=tuple(
            ResolvedPlayerMatch(
                player_id=match.player_id,
                display_name=match.canonical_name,
                confidence=match.confidence,
                matched_alias=match.matched_alias,
            )
            for match in resolution.matches
        ),
    ).model_dump_json()


@tool
def query_analytics(
    request: str, resolved_players: list[ResolvedPlayerIdentity] | None = None
) -> str:
    """Answer an analytical request using resolved player identities; never provide SQL.

    This tool owns SQL generation, validation, and execution internally. Pass
    the user's analytical request and the display-name/ID pairs returned by resolution.
    """
    with SessionLocal() as session:
        stats_service = StatsService(AnalyticsRepository(session))
        workflow = AnalyticsQueryWorkflow(
            stats_service,
            OpenAISqlGenerator(get_settings(), analytics_schema_description(session.get_bind())),
        )
        result = workflow.query(request, resolved_players or ())
    return AnalyticsQueryToolResult.from_service_result(result).model_dump_json()
