"""Deterministic resolution of event names from CurlChat's event catalog."""

from __future__ import annotations

from difflib import SequenceMatcher
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from curlchat.core.identities import ResolvedPlayerIdentity
from curlchat.core.names import normalize_name
from curlchat.repositories.events import EventNameRecord, EventRepository

_MINIMUM_FUZZY_CONFIDENCE = 0.84
_MINIMUM_CONFIDENCE_GAP = 0.08
_MAX_SUGGESTIONS = 5


class EventResolutionStatus(StrEnum):
    """Possible outcomes when resolving an event name."""

    MATCHED = "matched"
    AMBIGUOUS = "ambiguous"
    NOT_FOUND = "not_found"


class ResolvedEvent(BaseModel):
    """One canonical event candidate and confidence for the match."""

    model_config = ConfigDict(frozen=True)

    event_id: int
    display_name: str
    confidence: float = Field(ge=0, le=1)


class EventResolution(BaseModel):
    """Structured result returned by the Event Resolver tool."""

    model_config = ConfigDict(frozen=True)

    query: str
    status: EventResolutionStatus
    matches: tuple[ResolvedEvent, ...]

    @property
    def event(self) -> ResolvedEvent | None:
        """Return the sole event when resolution is unambiguous."""
        return self.matches[0] if self.status is EventResolutionStatus.MATCHED else None


class EventResolver:
    """Resolve event names without accessing player statistics."""

    def __init__(self, repository: EventRepository) -> None:
        self._repository = repository

    def resolve(
        self, query: str, resolved_players: tuple[ResolvedPlayerIdentity, ...] = ()
    ) -> EventResolution:
        """Resolve an event name, returning ambiguity rather than guessing."""
        normalized_query = self._without_year_tokens(normalize_name(query))
        if not normalized_query:
            return EventResolution(query=query, status=EventResolutionStatus.NOT_FOUND, matches=())

        records = self._repository.list_name_records()
        exact_matches = self._matches_exactly(records, normalized_query)
        if exact_matches:
            return self._resolution_for(query, exact_matches, resolved_players)

        shorthand_matches = self._matches_shorthand(records, normalized_query)
        if shorthand_matches:
            return self._resolution_for(query, shorthand_matches, resolved_players)

        suggestions = self._fuzzy_matches(records, normalized_query)
        if self._is_clear_fuzzy_match(suggestions):
            return EventResolution(
                query=query,
                status=EventResolutionStatus.MATCHED,
                matches=(suggestions[0],),
            )
        return EventResolution(
            query=query,
            status=(EventResolutionStatus.AMBIGUOUS if suggestions else EventResolutionStatus.NOT_FOUND),
            matches=suggestions,
        )

    @staticmethod
    def _matches_exactly(
        records: list[EventNameRecord], normalized_query: str
    ) -> tuple[ResolvedEvent, ...]:
        return tuple(
            ResolvedEvent(event_id=record.event_id, display_name=record.display_name, confidence=1.0)
            for record in records
            if normalized_query in {record.normalized_name, record.normalized_source_slug}
        )

    @staticmethod
    def _without_year_tokens(normalized_query: str) -> str:
        """Ignore years when an event phrase such as '2023 Brier' is resolved."""
        return " ".join(
            token
            for token in normalized_query.split()
            if not (len(token) == 4 and token.isdecimal())
        )

    @staticmethod
    def _matches_shorthand(
        records: list[EventNameRecord], normalized_query: str
    ) -> tuple[ResolvedEvent, ...]:
        return tuple(
            ResolvedEvent(event_id=record.event_id, display_name=record.display_name, confidence=1.0)
            for record in records
            if normalized_query in record.normalized_name
            or normalized_query in record.normalized_source_slug
        )

    def _fuzzy_matches(
        self, records: list[EventNameRecord], normalized_query: str
    ) -> tuple[ResolvedEvent, ...]:
        scored_records = [
            (
                max(
                    SequenceMatcher(None, normalized_query, record.normalized_name).ratio(),
                    SequenceMatcher(None, normalized_query, record.normalized_source_slug).ratio(),
                ),
                record,
            )
            for record in records
        ]
        candidates = [
            (score, record) for score, record in scored_records if score >= _MINIMUM_FUZZY_CONFIDENCE
        ]
        candidates.sort(key=lambda item: (-item[0], item[1].display_name, item[1].event_id))
        return tuple(
            ResolvedEvent(
                event_id=record.event_id,
                display_name=record.display_name,
                confidence=round(score, 3),
            )
            for score, record in candidates[:_MAX_SUGGESTIONS]
        )

    def _resolution_for(
        self,
        query: str,
        matches: tuple[ResolvedEvent, ...],
        resolved_players: tuple[ResolvedPlayerIdentity, ...],
    ) -> EventResolution:
        narrowed_matches = self._narrow_by_player_statistics(matches, resolved_players)
        return EventResolution(
            query=query,
            status=(
                EventResolutionStatus.MATCHED
                if len(narrowed_matches) == 1
                else EventResolutionStatus.AMBIGUOUS
            ),
            matches=narrowed_matches,
        )

    def _narrow_by_player_statistics(
        self,
        matches: tuple[ResolvedEvent, ...],
        resolved_players: tuple[ResolvedPlayerIdentity, ...],
    ) -> tuple[ResolvedEvent, ...]:
        """Use source statistics to disambiguate an event for resolved players."""
        if len(matches) < 2 or not resolved_players:
            return matches
        matching_event_ids = self._repository.event_ids_with_statistics_for_players(
            tuple(match.event_id for match in matches),
            tuple(player.player_id for player in resolved_players),
        )
        narrowed_matches = tuple(match for match in matches if match.event_id in matching_event_ids)
        return narrowed_matches if len(narrowed_matches) == 1 else matches

    @staticmethod
    def _is_clear_fuzzy_match(matches: tuple[ResolvedEvent, ...]) -> bool:
        if not matches:
            return False
        if len(matches) == 1:
            return True
        return matches[0].confidence - matches[1].confidence >= _MINIMUM_CONFIDENCE_GAP
