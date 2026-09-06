"""Analytics-query tool boundary for future agent orchestration."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from curlchat.repositories.analytics import AnalyticsRepository
from curlchat.services.stats_service import AnalyticsQueryResult, StatsService


def execute_analytics_query(
    session: Session, sql: str, parameters: dict[str, Any] | None = None
) -> AnalyticsQueryResult:
    """Run one validated read-only analytics query through the application service."""
    return StatsService(AnalyticsRepository(session)).execute(sql, parameters)
