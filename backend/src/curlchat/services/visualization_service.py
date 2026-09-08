"""Deterministic creation of frontend-ready analytics visualization artifacts."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from numbers import Real
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field


class VisualizationType(StrEnum):
    """The frontend artifact categories supported by CurlChat."""

    TABLE = "table"
    SUMMARY = "summary"
    CHART = "chart"


class ChartType(StrEnum):
    """The chart renderers initially supported by the frontend."""

    BAR = "bar"
    LINE = "line"
    DOT = "dot"


class SummaryAggregation(StrEnum):
    """Deterministic aggregate values available to a summary card."""

    AVERAGE = "average"
    MAXIMUM = "maximum"
    MINIMUM = "minimum"
    SUM = "sum"


class AnalyticsResultData(BaseModel):
    """The successful analytics result from which an artifact is created."""

    columns: tuple[str, ...] = Field(description="Columns returned by the Analytics Query Tool.")
    rows: tuple[dict[str, Any], ...] = Field(
        description="Rows from the same successful Analytics Query Tool result."
    )


class TableVisualizationSpec(BaseModel):
    """A table preserves an analytics result without selecting fields."""

    type: Literal[VisualizationType.TABLE] = Field(
        description="Create a table artifact from all supplied columns and rows."
    )
    title: str | None = Field(default=None, description="Optional concise, user-facing table title.")


class SummaryVisualizationSpec(BaseModel):
    """A summary deterministically aggregates one numeric result column."""

    type: Literal[VisualizationType.SUMMARY] = Field(
        description="Create one summary statistic artifact."
    )
    value_column: str = Field(description="Numeric result column to summarize.")
    aggregation: SummaryAggregation = Field(
        description="Aggregate to calculate: average, maximum, minimum, or sum."
    )
    title: str | None = Field(default=None, description="Optional concise, user-facing summary title.")


class LongChartDataMapping(BaseModel):
    """Map one result row per plotted point, optionally into named series."""

    format: Literal["long"] = Field(description="Use existing result rows as chart points.")
    x_column: str = Field(description="Result column to use as the x-axis.")
    y_column: str = Field(description="Numeric result column to use as the y-axis.")
    series_column: str | None = Field(
        default=None,
        description=(
            "Optional result column that creates one named series per value, for grouped bars or "
            "multiple lines."
        ),
    )


class WideChartDataMapping(BaseModel):
    """Map selected numeric result columns into x-axis categories."""

    format: Literal["wide"] = Field(
        description="Turn selected result columns into chart categories for each source row."
    )
    value_columns: tuple[str, ...] = Field(
        min_length=1,
        description="Numeric result columns to include as categories, in display order.",
    )
    series_column: str | None = Field(
        default=None,
        description=(
            "Required when multiple result rows should become named series, such as one series per "
            "player."
        ),
    )


ChartDataMapping = Annotated[
    LongChartDataMapping | WideChartDataMapping,
    Field(discriminator="format"),
]


class ChartVisualizationSpec(BaseModel):
    """A chart selects validated axes and an optional comparison dimension."""

    type: Literal[VisualizationType.CHART] = Field(description="Create a chart artifact.")
    chart_type: ChartType = Field(description="Renderer: bar, line, or dot.")
    data_mapping: ChartDataMapping = Field(
        description="Typed mapping from the query result to chart points or series."
    )
    title: str | None = Field(default=None, description="Optional concise, user-facing chart title.")


VisualizationSpec = Annotated[
    TableVisualizationSpec | SummaryVisualizationSpec | ChartVisualizationSpec,
    Field(discriminator="type"),
]


class VisualizationRequest(BaseModel):
    """One successful result and exactly one typed visualization specification."""

    result: AnalyticsResultData = Field(
        description="A successful Analytics Query Tool result. Do not invent or alter its rows."
    )
    spec: VisualizationSpec = Field(description="The frontend artifact to create from the result.")


class VisualizationArtifact(BaseModel):
    """One renderable artifact returned to the agent and frontend."""

    type: VisualizationType
    payload: dict[str, Any]


class VisualizationService:
    """Build safe, deterministic artifacts from already-retrieved analytics rows."""

    def create(self, request: VisualizationRequest) -> VisualizationArtifact:
        """Create exactly one artifact or reject an incompatible specification."""
        return self.create_from_result(request.result, request.spec)

    def create_from_result(
        self, result: AnalyticsResultData, spec: VisualizationSpec
    ) -> VisualizationArtifact:
        """Create exactly one artifact from a trusted result and typed specification."""
        if isinstance(spec, TableVisualizationSpec):
            return VisualizationArtifact(
                type=VisualizationType.TABLE,
                payload={
                    "columns": result.columns,
                    "column_labels": {
                        column: self._display_label(column) for column in result.columns
                    },
                    "rows": result.rows,
                    "title": spec.title,
                },
            )
        if isinstance(spec, ChartVisualizationSpec):
            return self._chart(result, spec)
        return self._summary(result, spec)

    def _chart(
        self, result: AnalyticsResultData, spec: ChartVisualizationSpec
    ) -> VisualizationArtifact:
        if isinstance(spec.data_mapping, LongChartDataMapping):
            return self._long_chart(result, spec, spec.data_mapping)
        return self._wide_chart(result, spec, spec.data_mapping)

    def _long_chart(
        self,
        result: AnalyticsResultData,
        spec: ChartVisualizationSpec,
        mapping: LongChartDataMapping,
    ) -> VisualizationArtifact:
        self._require_column(mapping.x_column, result.columns)
        self._require_column(mapping.y_column, result.columns)
        if mapping.series_column is not None:
            self._require_column(mapping.series_column, result.columns)
        points = self._long_points(result, mapping)
        if not points:
            raise VisualizationRequestError("The selected chart columns contain no plottable rows.")
        if not all(self._is_number(point["y"]) for point in points):
            raise VisualizationRequestError("A chart y_column must contain numeric values.")
        payload: dict[str, Any] = {
            "chart_type": spec.chart_type,
            "x_column": mapping.x_column,
            "y_column": mapping.y_column,
            "x_label": self._display_label(mapping.x_column),
            "y_label": self._display_label(mapping.y_column),
            "title": spec.title,
        }
        if mapping.series_column is None:
            payload["points"] = points
        else:
            payload["series_column"] = mapping.series_column
            payload["series"] = self._series(points)
            if spec.chart_type is ChartType.BAR:
                payload["bar_mode"] = "group"
        return VisualizationArtifact(type=VisualizationType.CHART, payload=payload)

    def _wide_chart(
        self,
        result: AnalyticsResultData,
        spec: ChartVisualizationSpec,
        mapping: WideChartDataMapping,
    ) -> VisualizationArtifact:
        for column in mapping.value_columns:
            self._require_column(column, result.columns)
        if mapping.series_column is not None:
            self._require_column(mapping.series_column, result.columns)
        if len(result.rows) > 1 and mapping.series_column is None:
            raise VisualizationRequestError(
                "A wide chart with multiple result rows requires a series_column."
            )
        points = self._wide_points(result, mapping)
        if not points:
            raise VisualizationRequestError("The selected chart columns contain no plottable values.")
        if not all(self._is_number(point["y"]) for point in points):
            raise VisualizationRequestError("Wide chart value_columns must contain numeric values.")
        payload: dict[str, Any] = {
            "chart_type": spec.chart_type,
            "x_column": "statistic",
            "y_column": "value",
            "x_label": "Statistic",
            "y_label": "Value",
            "value_columns": mapping.value_columns,
            "title": spec.title,
        }
        if mapping.series_column is None:
            payload["points"] = points
        else:
            payload["series_column"] = mapping.series_column
            payload["series"] = self._series(points)
            if spec.chart_type is ChartType.BAR:
                payload["bar_mode"] = "group"
        return VisualizationArtifact(type=VisualizationType.CHART, payload=payload)

    def _summary(
        self, result: AnalyticsResultData, spec: SummaryVisualizationSpec
    ) -> VisualizationArtifact:
        self._require_column(spec.value_column, result.columns)
        values = tuple(
            row[spec.value_column]
            for row in result.rows
            if row.get(spec.value_column) is not None
        )
        if not values:
            raise VisualizationRequestError("The selected summary column contains no values.")
        if not all(self._is_number(value) for value in values):
            raise VisualizationRequestError("A summary value_column must contain numeric values.")
        numeric_values = tuple(float(value) for value in values)
        value = {
            SummaryAggregation.AVERAGE: sum(numeric_values) / len(numeric_values),
            SummaryAggregation.MAXIMUM: max(numeric_values),
            SummaryAggregation.MINIMUM: min(numeric_values),
            SummaryAggregation.SUM: sum(numeric_values),
        }[spec.aggregation]
        return VisualizationArtifact(
            type=VisualizationType.SUMMARY,
            payload={
                "label": f"{spec.aggregation.value.title()} {self._display_label(spec.value_column)}",
                "value": value,
                "source_column": spec.value_column,
                "aggregation": spec.aggregation,
                "title": spec.title,
            },
        )

    @classmethod
    def _long_points(
        cls,
        result: AnalyticsResultData, mapping: LongChartDataMapping
    ) -> tuple[dict[str, Any], ...]:
        return tuple(
            {
                "x": row[mapping.x_column],
                "y": cls._json_number(row[mapping.y_column]),
                **({"series": row[mapping.series_column]} if mapping.series_column else {}),
            }
            for row in result.rows
            if row.get(mapping.x_column) is not None and row.get(mapping.y_column) is not None
        )

    @classmethod
    def _wide_points(
        cls,
        result: AnalyticsResultData, mapping: WideChartDataMapping
    ) -> tuple[dict[str, Any], ...]:
        return tuple(
            {
                "x": cls._display_label(column),
                "y": cls._json_number(row[column]),
                **({"series": row[mapping.series_column]} if mapping.series_column else {}),
            }
            for row in result.rows
            for column in mapping.value_columns
            if row.get(column) is not None
        )

    @staticmethod
    def _series(points: tuple[dict[str, Any], ...]) -> tuple[dict[str, Any], ...]:
        series_by_name: dict[str, list[dict[str, Any]]] = {}
        for point in points:
            name = str(point["series"])
            series_by_name.setdefault(name, []).append({"x": point["x"], "y": point["y"]})
        return tuple(
            {"name": name, "points": tuple(series_points)}
            for name, series_points in series_by_name.items()
        )

    @staticmethod
    def _require_column(column: str, columns: tuple[str, ...]) -> None:
        if column not in columns:
            raise VisualizationRequestError(f"Unknown analytics result column: {column}.")

    @staticmethod
    def _is_number(value: object) -> bool:
        return isinstance(value, (Real, Decimal)) and not isinstance(value, bool)

    @staticmethod
    def _json_number(value: object) -> object:
        """Convert database Decimal values into JSON number values for chart payloads."""
        return float(value) if isinstance(value, Decimal) else value

    @staticmethod
    def _display_label(column: str) -> str:
        return column.removesuffix("_percent").replace("_", " ").title()


class VisualizationRequestError(ValueError):
    """A requested artifact cannot be created from the supplied analytics result."""
