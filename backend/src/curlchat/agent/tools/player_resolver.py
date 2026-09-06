"""Player-resolver boundary and LangChain tool."""

from __future__ import annotations

from typing import Annotated

from langchain_core.tools import tool
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from curlchat.db.session import SessionLocal
from curlchat.repositories.players import PlayerRepository
from curlchat.services.player_resolver import (
    PlayerResolution,
    PlayerResolutionStatus,
    PlayerResolver,
)


class ResolvedPlayerMatch(BaseModel):
    """One player candidate exposed by the Player Resolver tool."""

    player_id: int
    display_name: str
    confidence: float
    matched_alias: bool


class PlayerResolutionToolResult(BaseModel):
    """Structured output returned by the Player Resolver tool."""

    query: str
    status: PlayerResolutionStatus
    matches: tuple[ResolvedPlayerMatch, ...] = Field(default_factory=tuple)


def resolve_player_name(session: Session, name: str) -> PlayerResolution:
    """Resolve one user-provided name through the application service."""
    return PlayerResolver(PlayerRepository(session)).resolve(name)


@tool
def resolve_player(
    name: Annotated[
        str,
        Field(description="The player name exactly as the user expressed it, including an alias or misspelling."),
    ],
) -> str:
    """Resolve a player name before asking a question about that player's statistics."""
    with SessionLocal() as session:
        resolution = resolve_player_name(session, name)
    return PlayerResolutionToolResult(
        query=resolution.query,
        status=resolution.status,
        matches=tuple(
            ResolvedPlayerMatch(
                player_id=match.player_id,
                display_name=match.canonical_name,
                confidence=match.confidence,
                matched_alias=match.matched_alias,
            )
            for match in resolution.matches
        ),
    ).model_dump_json()
