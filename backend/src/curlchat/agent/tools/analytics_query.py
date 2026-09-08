"""Analytics-query boundary and LangChain tool."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
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
from curlchat.repositories.events import EventRepository
from curlchat.repositories.players import PlayerRepository
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
        try:
            _validate_resolved_players(PlayerRepository(session), resolved_players or ())
            _validate_resolved_events(EventRepository(session), resolved_events or ())
        except ResolvedIdentityMismatchError as error:
            return AnalyticsQueryResult(status=AnalyticsQueryStatus.UNSUPPORTED, message=str(error))
        settings = get_settings()
        workflow = AnalyticsQueryWorkflow(
            StatsService(
                AnalyticsRepository(session),
                statement_timeout_ms=settings.analytics_statement_timeout_ms,
            ),
            OpenAISqlGenerator(settings, analytics_schema_description(session.get_bind())),
        )
        return workflow.query(request, resolved_players or (), resolved_events or ())


def _validate_resolved_events(
    repository: EventRepository,
    resolved_events: list[ResolvedEventIdentity] | tuple[ResolvedEventIdentity, ...],
) -> None:
    """Reject fabricated or inconsistent Event Resolver identity pairs."""
    _validate_resolved_identities(
        resolved_events,
        repository.display_names_by_id,
        lambda event: event.event_id,
        lambda event: event.display_name,
        "event",
    )


def _validate_resolved_players(
    repository: PlayerRepository,
    resolved_players: list[ResolvedPlayerIdentity] | tuple[ResolvedPlayerIdentity, ...],
) -> None:
    """Reject fabricated or inconsistent Player Resolver identity pairs."""
    _validate_resolved_identities(
        resolved_players,
        repository.display_names_by_id,
        lambda player: player.player_id,
        lambda player: player.display_name,
        "player",
    )


def _validate_resolved_identities[ResolvedIdentity](
    identities: Sequence[ResolvedIdentity],
    display_names_by_id: Callable[[tuple[int, ...]], Mapping[int, str]],
    identity_id: Callable[[ResolvedIdentity], int],
    display_name: Callable[[ResolvedIdentity], str],
    identity_type: str,
) -> None:
    """Reject claimed resolver identities that do not match their canonical records."""
    canonical_names = display_names_by_id(tuple(identity_id(identity) for identity in identities))
    for identity in identities:
        identifier = identity_id(identity)
        claimed_name = display_name(identity)
        canonical_name = canonical_names.get(identifier)
        if canonical_name is None:
            raise ResolvedIdentityMismatchError(
                f"The resolved {identity_type} ID {identifier} does not exist. "
                f"Resolve the {identity_type} before querying."
            )
        if canonical_name != claimed_name:
            raise ResolvedIdentityMismatchError(
                f"Resolved {identity_type} mismatch: ID {identifier} is {canonical_name!r}, "
                f"not {claimed_name!r}. Resolve the {identity_type} before querying."
            )


class ResolvedIdentityMismatchError(ValueError):
    """A claimed resolver result does not match the imported identity catalog."""


@tool
def query_analytics(
    request: Annotated[
        str,
        Field(
            description=(
                "A concise natural-language statement of the user's analytical request, never SQL. "
                "Retain every stated constraint—such as years, competition, players, filters, thresholds, "
                "ranking, and requested output—while you may normalize wording for clarity."
            )
        ),
    ],
    tool_call_id: Annotated[str, InjectedToolCallId],
    resolved_players: Annotated[
        list[ResolvedPlayerIdentity] | None,
        Field(
            description=(
                "Exact, unchanged display_name/player_id pairs from successful Player Resolver "
                "results only. Never reconstruct, modify, or invent identities."
            )
        ),
    ] = None,
    resolved_events: Annotated[
        list[ResolvedEventIdentity] | None,
        Field(
            description=(
                "Exact, unchanged display_name/event_id pairs from successful Event Resolver "
                "results only. Never reconstruct, modify, or invent identities."
            )
        ),
    ] = None,
) -> Command:
    """Answer a statistics request after identity resolution; never provide SQL."""
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
