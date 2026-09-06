"""Event-resolver boundary and LangChain tool."""

from __future__ import annotations

from typing import Annotated

from langchain_core.tools import tool
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

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


def resolve_event_name(session: Session, name: str) -> EventResolution:
    """Resolve one user-provided event name through the application service."""
    return EventResolver(EventRepository(session)).resolve(name)


@tool
def resolve_event(
    name: Annotated[
        str,
        Field(description="The event name exactly as the user expressed it, including shorthand. Omit years."),
    ],
) -> str:
    """Resolve an event name before asking a question about event statistics."""
    with SessionLocal() as session:
        resolution = resolve_event_name(session, name)
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
    ).model_dump_json()
