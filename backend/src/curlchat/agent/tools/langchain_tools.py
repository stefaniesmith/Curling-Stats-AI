"""LangChain adapters for CurlChat's deterministic application tools."""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from curlchat.agent.tools.player_resolver import resolve_player_name
from curlchat.db.session import SessionLocal, get_settings
from curlchat.repositories.analytics import AnalyticsRepository
from curlchat.services.analytics_query_service import (
    AnalyticsQueryService,
    OpenAISqlGenerator,
    ResolvedPlayerIdentity,
    analytics_schema_description,
)
from curlchat.services.stats_service import StatsService


@tool
def resolve_player(name: str) -> dict[str, Any]:
    """Resolve a player name before asking a question about that player's statistics."""
    with SessionLocal() as session:
        resolution = resolve_player_name(session, name)
    return {
        "query": resolution.query,
        "status": resolution.status.value,
        "matches": [
            {
                "player_id": match.player_id,
                "display_name": match.canonical_name,
                "confidence": match.confidence,
                "matched_alias": match.matched_alias,
            }
            for match in resolution.matches
        ],
    }


@tool
def query_analytics(
    request: str, resolved_players: list[ResolvedPlayerIdentity] | None = None
) -> dict[str, Any]:
    """Answer an analytical request using resolved player identities; never provide SQL.

    This tool owns SQL generation, validation, and execution internally. Pass
    the user's analytical request and the display-name/ID pairs returned by resolution.
    """
    with SessionLocal() as session:
        stats_service = StatsService(AnalyticsRepository(session))
        service = AnalyticsQueryService(
            stats_service,
            OpenAISqlGenerator(get_settings(), analytics_schema_description(session.get_bind())),
        )
        result = service.query(request, resolved_players or ())
    return {
        "status": result.status.value,
        "columns": result.columns,
        "rows": result.rows,
        "truncated": result.truncated,
        "message": result.message,
    }
