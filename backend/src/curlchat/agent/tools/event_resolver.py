"""Event-resolver tool boundary for agent orchestration."""

from __future__ import annotations

from sqlalchemy.orm import Session

from curlchat.repositories.events import EventRepository
from curlchat.services.event_resolver import EventResolution, EventResolver


def resolve_event_name(session: Session, name: str) -> EventResolution:
    """Resolve one user-provided event name through the application service."""
    return EventResolver(EventRepository(session)).resolve(name)
