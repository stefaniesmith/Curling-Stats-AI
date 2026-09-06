"""Visualization boundary and LangChain tool."""

from __future__ import annotations

from typing import Annotated

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from curlchat.services.visualization_service import (
    VisualizationRequest,
    VisualizationRequestError,
    VisualizationService,
)


class VisualizationToolError(BaseModel):
    """A recoverable reason an artifact could not be constructed."""

    error: str


@tool
def create_visualization(
    request: Annotated[
        VisualizationRequest,
        Field(
            description=(
                "One successful analytics result plus a typed table, summary, or chart specification. "
                "Pass result rows unchanged."
            )
        ),
    ],
) -> str:
    """Create one frontend artifact from a successful analytics result; never query the database."""
    try:
        artifact = VisualizationService().create(request)
    except VisualizationRequestError as error:
        return VisualizationToolError(error=str(error)).model_dump_json()
    return artifact.model_dump_json()
