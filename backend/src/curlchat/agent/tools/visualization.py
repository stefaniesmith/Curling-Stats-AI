"""Visualization boundary and LangChain tool."""

from __future__ import annotations

from typing import Annotated, Any

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from pydantic import BaseModel, Field, ValidationError

from curlchat.services.visualization_service import (
    AnalyticsResultData,
    VisualizationRequestError,
    VisualizationService,
    VisualizationSpec,
)


class VisualizationToolError(BaseModel):
    """A recoverable reason an artifact could not be constructed."""

    error: str


def _visualization_validation_error(_: ValidationError) -> str:
    """Return a recoverable tool response when the model omits the spec wrapper."""
    return VisualizationToolError(
        error="Invalid visualization request. Pass the chart, table, or summary object as `spec`."
    ).model_dump_json()


def create_visualization_from_result(
    result: AnalyticsResultData | None, spec: VisualizationSpec
) -> str:
    """Create an artifact from the last successful typed analytics result."""
    if result is None:
        return VisualizationToolError(
            error="No successful analytics result is available to visualize."
        ).model_dump_json()
    try:
        artifact = VisualizationService().create_from_result(result, spec)
    except VisualizationRequestError as error:
        return VisualizationToolError(error=str(error)).model_dump_json()
    return artifact.model_dump_json()


@tool
def create_visualization(
    spec: Annotated[
        VisualizationSpec,
        Field(
            description=(
                "Call only after a successful analytics query. Provide a typed table, summary, or "
                "chart specification for the latest result, using result-column names exactly. Select "
                "columns and mappings only; do not pass, reproduce, or transform result rows."
            )
        ),
    ],
    state: Annotated[dict[str, Any], InjectedState],
) -> str:
    """Create one frontend artifact from a successful analytics result; never query the database."""
    latest_result = state.get("latest_analytics_result")
    result = AnalyticsResultData.model_validate(latest_result) if latest_result is not None else None
    return create_visualization_from_result(result, spec)


create_visualization.handle_validation_error = _visualization_validation_error
