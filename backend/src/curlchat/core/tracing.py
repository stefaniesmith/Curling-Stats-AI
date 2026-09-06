"""Optional, vendor-neutral tracing configuration for CurlChat."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from phoenix.otel import register

from curlchat.db.session import Settings

logger = logging.getLogger(__name__)


def configure_tracing(app: FastAPI, settings: Settings) -> None:
    """Export FastAPI and LangGraph traces to Phoenix when explicitly enabled."""
    if not settings.phoenix_tracing_enabled:
        return
    try:
        tracer_provider = register(
            project_name=settings.phoenix_project_name,
            endpoint=settings.phoenix_collector_endpoint,
            protocol="http/protobuf",
            auto_instrument=True,
            batch=True,
        )
        FastAPIInstrumentor.instrument_app(
            app,
            tracer_provider=tracer_provider,
            excluded_urls="/health",
        )
    except Exception:
        logger.exception("Phoenix tracing could not be configured; continuing without tracing.")
