"""Data access for canonical players and their archive aliases."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from curlchat.db.models import Player, PlayerAlias


@dataclass(frozen=True)
class PlayerNameRecord:
    """One canonical or alias name that can identify a player."""

    player_id: int
    canonical_name: str
    normalized_name: str
    is_alias: bool


class PlayerRepository:
    """Read-only access to player identity data."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def find_by_normalized_name(self, normalized_name: str) -> list[PlayerNameRecord]:
        """Return every canonical player matching a canonical name or an alias."""
        return [
            record
            for record in self.list_name_records()
            if record.normalized_name == normalized_name
        ]

    def display_names_by_id(self, player_ids: tuple[int, ...]) -> dict[int, str]:
        """Return canonical display names for the supplied player IDs."""
        if not player_ids:
            return {}
        return dict(
            self._session.execute(
                select(Player.id, Player.display_name).where(Player.id.in_(player_ids))
            ).all()
        )

    def list_name_records(self) -> list[PlayerNameRecord]:
        """Return all canonical and alias names used for resolver matching."""
        canonical_records = [
            PlayerNameRecord(
                player_id=player.id,
                canonical_name=player.display_name,
                normalized_name=player.normalized_name,
                is_alias=False,
            )
            for player in self._session.scalars(select(Player).order_by(Player.id))
        ]
        alias_records = [
            PlayerNameRecord(
                player_id=player.id,
                canonical_name=player.display_name,
                normalized_name=alias.normalized_name,
                is_alias=True,
            )
            for alias, player in self._session.execute(
                select(PlayerAlias, Player)
                .join(Player, PlayerAlias.player_id == Player.id)
                .order_by(PlayerAlias.id)
            )
        ]
        return canonical_records + alias_records
