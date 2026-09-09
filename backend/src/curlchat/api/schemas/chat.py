"""Strict HTTP response contracts for chat and renderable artifacts."""

from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator, model_validator


class ApiModel(BaseModel):
    """Reject unexpected fields at the browser-facing API boundary."""

    model_config = ConfigDict(extra="forbid")


class MarkdownPayload(ApiModel):
    content: str


class MarkdownBlock(ApiModel):
    type: Literal["markdown"]
    payload: MarkdownPayload


class TablePayload(ApiModel):
    columns: list[str]
    column_labels: dict[str, str]
    rows: list[dict[str, Any]]
    title: str | None

    @model_validator(mode="after")
    def includes_labels_for_all_columns(self) -> "TablePayload":
        if any(column not in self.column_labels for column in self.columns):
            raise ValueError("column_labels must include every table column.")
        return self


class TableBlock(ApiModel):
    type: Literal["table"]
    payload: TablePayload


class SummaryPayload(ApiModel):
    label: str
    value: float
    source_column: str
    aggregation: Literal["average", "maximum", "minimum", "sum"]
    title: str | None


class SummaryBlock(ApiModel):
    type: Literal["summary"]
    payload: SummaryPayload


class ChartPoint(ApiModel):
    x: str | float | int
    y: float


class ChartSeries(ApiModel):
    name: str
    points: list[ChartPoint]


class ChartPayload(ApiModel):
    chart_type: Literal["bar", "line", "dot"]
    x_column: str
    y_column: str
    x_label: str
    y_label: str
    title: str | None
    points: list[ChartPoint] | None = None
    series_column: str | None = None
    series: list[ChartSeries] | None = None
    bar_mode: Literal["group"] | None = None
    value_columns: list[str] | None = None

    @model_validator(mode="after")
    def includes_exactly_one_data_shape(self) -> "ChartPayload":
        if (self.points is None) == (self.series is None):
            raise ValueError("A chart must provide points or series, but not both.")
        return self


class ChartBlock(ApiModel):
    type: Literal["chart"]
    payload: ChartPayload


ResponseBlock = Annotated[
    MarkdownBlock | TableBlock | SummaryBlock | ChartBlock,
    Field(discriminator="type"),
]
ArtifactBlock = Annotated[TableBlock | SummaryBlock | ChartBlock, Field(discriminator="type")]

_artifact_adapter = TypeAdapter(ArtifactBlock)


def markdown_block(content: str) -> MarkdownBlock:
    """Create the always-present Markdown block for an assistant response."""
    return MarkdownBlock(type="markdown", payload=MarkdownPayload(content=content))


def artifact_block(value: object) -> ArtifactBlock:
    """Validate a service-produced artifact before it reaches HTTP or SSE clients."""
    return _artifact_adapter.validate_python(value)


class ChatRequest(ApiModel):
    message: str = Field(max_length=2_000)
    conversation_id: UUID | None = None

    @field_validator("message")
    @classmethod
    def requires_non_blank_message(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message must not be blank.")
        return value


class ChatResponse(ApiModel):
    conversation_id: UUID
    message: str
    blocks: list[ResponseBlock] = Field(default_factory=list)
