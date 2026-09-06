"""Player-resolver tool boundary for future agent orchestration."""

from __future__ import annotations

from sqlalchemy.orm import Session

from curlchat.repositories.players import PlayerRepository
from curlchat.services.player_resolver import PlayerResolution, PlayerResolver


def resolve_player_name(session: Session, name: str) -> PlayerResolution:
    """Resolve one user-provided name through the application service."""
    return PlayerResolver(PlayerRepository(session)).resolve(name)
