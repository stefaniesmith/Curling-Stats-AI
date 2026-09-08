"""Event-resolver boundary and LangChain tool."""

from __future__ import annotations

from typing import Annotated

from langchain_core.tools import tool
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from curlchat.core.identities import ResolvedPlayerIdentity
from curlchat.db.session import SessionLocal
from curlchat.repositories.events import EventRepository
from curlchat.services.event_resolver import EventResolution, EventResolutionStatus, EventResolver


class ResolvedEventMatch(BaseModel):
    """One event candidate exposed by the Event Resolver tool."""

    event_id: int
    display_name: str
    confidence: float


class EventResolutionToolResult(BaseModel):
    """Structured output returned by the Event Resolver tool."""

    query: str
    status: EventResolutionStatus
    matches: tuple[ResolvedEventMatch, ...] = Field(default_factory=tuple)
    has_any_records_for_resolved_players: bool | None = None


def resolve_event_name(
    session: Session, name: str, resolved_players: tuple[ResolvedPlayerIdentity, ...] = ()
) -> EventResolution:
    """Resolve one user-provided event name through the application service."""
    return EventResolver(EventRepository(session)).resolve(name, resolved_players)


@tool
def resolve_event(
    name: Annotated[
        str,
        Field(
            description=(
                "Use the competition catalog in the system prompt to choose the appropriate "
                "canonical competition name or documented alias for the user's request. Do not "
                "invent a name or alias. Pass one competition name without years or database IDs."
            )
        ),
    ],
    resolved_players: Annotated[
        list[ResolvedPlayerIdentity] | None,
        Field(
            description=(
                "Successful Player Resolver results, when available. The resolver uses these "
                "exact, unchanged identity pairs only to disambiguate otherwise matching events "
                "from source statistics and reports whether the matched event has records for all of them."
            )
        ),
    ] = None,
) -> str:
    """Resolve an event name before asking a question about event statistics."""
    with SessionLocal() as session:
        resolution = resolve_event_name(
            session, name, tuple(resolved_players or ())
        )
    return EventResolutionToolResult(
        query=resolution.query,
        status=resolution.status,
        matches=tuple(
            ResolvedEventMatch(
                event_id=match.event_id,
                display_name=match.display_name,
                confidence=match.confidence,
            )
            for match in resolution.matches
        ),
        has_any_records_for_resolved_players=resolution.has_any_records_for_resolved_players,
    ).model_dump_json()
