"""Optional, vendor-neutral tracing configuration for CurlChat."""

from __future__ import annotations

import logging

from phoenix.otel import register

from curlchat.db.session import Settings

logger = logging.getLogger(__name__)


def configure_tracing(settings: Settings) -> None:
    """Export LangGraph, LangChain, and model traces to Phoenix when enabled."""
    if not settings.phoenix_tracing_enabled:
        return
    try:
        register(
            project_name=settings.phoenix_project_name,
            endpoint=settings.phoenix_collector_endpoint,
            protocol="http/protobuf",
            auto_instrument=True,
            batch=True,
        )
    except Exception:
        logger.exception("Phoenix tracing could not be configured; continuing without tracing.")
