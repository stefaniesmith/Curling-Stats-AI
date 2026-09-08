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


@dataclass(frozen=True)
class CompetitionCatalogRecord:
    """Imported competition metadata suitable for deterministic prompt context."""

    display_name: str
    first_event_year: int | None
    last_event_year: int | None
    has_shot_statistics: bool


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

    def list_competition_catalog_records(self) -> list[CompetitionCatalogRecord]:
        """Return competition coverage metadata without exposing internal event IDs."""
        return [
            CompetitionCatalogRecord(
                display_name=event.display_name,
                first_event_year=event.first_event_year,
                last_event_year=event.last_event_year,
                has_shot_statistics=event.has_shot_statistics,
            )
            for event in self._session.scalars(select(Event).order_by(Event.display_name))
        ]

    def display_names_by_id(self, event_ids: tuple[int, ...]) -> dict[int, str]:
        """Return canonical display names for the supplied event IDs."""
        if not event_ids:
            return {}
        return dict(
            self._session.execute(
                select(Event.id, Event.display_name).where(Event.id.in_(event_ids))
            ).all()
        )

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
