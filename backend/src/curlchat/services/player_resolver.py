"""Deterministic player identity resolution."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from difflib import SequenceMatcher
from enum import StrEnum

from curlchat.core.names import normalize_name
from curlchat.repositories.players import PlayerNameRecord, PlayerRepository

_MINIMUM_FUZZY_CONFIDENCE = 0.84
_MINIMUM_CONFIDENCE_GAP = 0.08
_MAX_SUGGESTIONS = 5


class PlayerResolutionStatus(StrEnum):
    """Possible outcomes when resolving a player name."""

    MATCHED = "matched"
    AMBIGUOUS = "ambiguous"
    NOT_FOUND = "not_found"


@dataclass(frozen=True)
class ResolvedPlayer:
    """A canonical player candidate and the confidence of the name match."""

    player_id: int
    canonical_name: str
    confidence: float
    matched_alias: bool


@dataclass(frozen=True)
class PlayerResolution:
    """Structured result returned to the agent's player-resolver tool."""

    query: str
    status: PlayerResolutionStatus
    matches: tuple[ResolvedPlayer, ...]

    @property
    def player(self) -> ResolvedPlayer | None:
        """Return the sole player when resolution is unambiguous."""
        return self.matches[0] if self.status is PlayerResolutionStatus.MATCHED else None


class PlayerResolver:
    """Resolve canonical and archive alias names without accessing statistics."""

    def __init__(self, repository: PlayerRepository) -> None:
        self._repository = repository

    def resolve(self, query: str) -> PlayerResolution:
        """Resolve a user-supplied name, returning ambiguity instead of guessing."""
        normalized_query = normalize_name(query)
        if not normalized_query:
            return PlayerResolution(query=query, status=PlayerResolutionStatus.NOT_FOUND, matches=())

        exact_matches = self._unique_players(
            self._repository.find_by_normalized_name(normalized_query), confidence=1.0
        )
        if len(exact_matches) == 1:
            return PlayerResolution(
                query=query, status=PlayerResolutionStatus.MATCHED, matches=exact_matches
            )
        if exact_matches:
            return PlayerResolution(
                query=query, status=PlayerResolutionStatus.AMBIGUOUS, matches=exact_matches
            )

        suggestions = self._fuzzy_matches(normalized_query)
        if self._is_clear_fuzzy_match(suggestions):
            return PlayerResolution(
                query=query,
                status=PlayerResolutionStatus.MATCHED,
                matches=(suggestions[0],),
            )
        return PlayerResolution(
            query=query,
            status=(PlayerResolutionStatus.AMBIGUOUS if suggestions else PlayerResolutionStatus.NOT_FOUND),
            matches=suggestions,
        )

    def _fuzzy_matches(self, normalized_query: str) -> tuple[ResolvedPlayer, ...]:
        scored_records = [
            (
                SequenceMatcher(None, normalized_query, record.normalized_name).ratio(),
                record,
            )
            for record in self._repository.list_name_records()
        ]
        candidates = [
            (score, record)
            for score, record in scored_records
            if score >= _MINIMUM_FUZZY_CONFIDENCE
        ]
        candidates.sort(key=lambda item: (-item[0], item[1].canonical_name, item[1].player_id))
        return self._unique_players(
            (record for _, record in candidates), scores=(score for score, _ in candidates)
        )[:_MAX_SUGGESTIONS]

    @staticmethod
    def _unique_players(
        records: Iterable[PlayerNameRecord],
        confidence: float | None = None,
        scores: Iterable[float] | None = None,
    ) -> tuple[ResolvedPlayer, ...]:
        """Collapse canonical and alias records that identify the same player."""
        score_iterator = iter(scores) if scores is not None else None
        by_player_id: dict[int, ResolvedPlayer] = {}
        for record in records:
            score = confidence if confidence is not None else next(score_iterator)
            existing = by_player_id.get(record.player_id)
            candidate = ResolvedPlayer(
                player_id=record.player_id,
                canonical_name=record.canonical_name,
                confidence=round(score, 3),
                matched_alias=record.is_alias,
            )
            if existing is None or candidate.confidence > existing.confidence:
                by_player_id[record.player_id] = candidate
        return tuple(
            sorted(by_player_id.values(), key=lambda match: (-match.confidence, match.canonical_name))
        )

    @staticmethod
    def _is_clear_fuzzy_match(matches: tuple[ResolvedPlayer, ...]) -> bool:
        if not matches:
            return False
        if len(matches) == 1:
            return True
        return matches[0].confidence - matches[1].confidence >= _MINIMUM_CONFIDENCE_GAP
