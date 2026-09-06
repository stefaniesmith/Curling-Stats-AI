"""Read-only access to event identities used by the Event Resolver."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from curlchat.core.names import normalize_name
from curlchat.db.models import Event, PlayerEventStatistics


@dataclass(frozen=True)
class EventNameRecord:
    """One event name and source slug available for deterministic matching."""

    event_id: int
    display_name: str
    normalized_name: str
    normalized_source_slug: str


class EventRepository:
    """Read-only access to the small imported event catalog."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_name_records(self) -> list[EventNameRecord]:
        """Return stable event identities with normalized matching values."""
        return [
            EventNameRecord(
                event_id=event.id,
                display_name=event.display_name,
                normalized_name=normalize_name(event.display_name),
                normalized_source_slug=normalize_name(event.source_slug),
            )
            for event in self._session.scalars(select(Event).order_by(Event.id))
        ]

    def event_ids_with_statistics_for_players(
        self, event_ids: tuple[int, ...], player_ids: tuple[int, ...]
    ) -> set[int]:
        """Return candidate events containing statistics for every supplied player."""
        if not event_ids or not player_ids:
            return set()
        return set(
            self._session.scalars(
                select(PlayerEventStatistics.event_id)
                .where(
                    PlayerEventStatistics.event_id.in_(event_ids),
                    PlayerEventStatistics.player_id.in_(player_ids),
                )
                .group_by(PlayerEventStatistics.event_id)
                .having(func.count(distinct(PlayerEventStatistics.player_id)) == len(player_ids))
            )
        )
