import json
from decimal import Decimal

import pytest

from curlchat.agent.tools.visualization import create_visualization_from_result
from curlchat.services.visualization_service import (
    AnalyticsResultData,
    ChartType,
    ChartVisualizationSpec,
    LongChartDataMapping,
    SummaryAggregation,
    SummaryVisualizationSpec,
    TableVisualizationSpec,
    VisualizationRequest,
    VisualizationRequestError,
    VisualizationService,
    VisualizationType,
    WideChartDataMapping,
)


def test_creates_a_table_artifact() -> None:
    artifact = VisualizationService().create(
        VisualizationRequest(
            result=AnalyticsResultData(
                columns=("display_name", "wins"),
                rows=({"display_name": "Brad Jacobs", "wins": 6},),
            ),
            spec=TableVisualizationSpec(type="table", title="Canada Cup results"),
        )
    )

    assert artifact.type is VisualizationType.TABLE
    assert artifact.payload == {
        "columns": ("display_name", "wins"),
        "rows": ({"display_name": "Brad Jacobs", "wins": 6},),
        "title": "Canada Cup results",
    }


def test_creates_a_line_chart_artifact() -> None:
    artifact = VisualizationService().create(
        VisualizationRequest(
            result=AnalyticsResultData(
                columns=("event_year", "wins"),
                rows=({"event_year": 2023, "wins": 6}, {"event_year": 2024, "wins": 8}),
            ),
            spec=ChartVisualizationSpec(
                type="chart",
                chart_type=ChartType.LINE,
                data_mapping=LongChartDataMapping(
                    format="long", x_column="event_year", y_column="wins"
                ),
            ),
        )
    )

    assert artifact.type is VisualizationType.CHART
    assert artifact.payload["chart_type"] is ChartType.LINE
    assert artifact.payload["points"] == ({"x": 2023, "y": 6}, {"x": 2024, "y": 8})


def test_creates_grouped_bar_series() -> None:
    artifact = VisualizationService().create(
        VisualizationRequest(
            result=AnalyticsResultData(
                columns=("event_year", "display_name", "wins"),
                rows=(
                    {"event_year": 2023, "display_name": "Rachel Homan", "wins": 6},
                    {"event_year": 2023, "display_name": "Jennifer Jones", "wins": 5},
                    {"event_year": 2024, "display_name": "Rachel Homan", "wins": 8},
                    {"event_year": 2024, "display_name": "Jennifer Jones", "wins": 7},
                ),
            ),
            spec=ChartVisualizationSpec(
                type="chart",
                chart_type=ChartType.BAR,
                data_mapping=LongChartDataMapping(
                    format="long",
                    x_column="event_year",
                    y_column="wins",
                    series_column="display_name",
                ),
            ),
        )
    )

    assert artifact.payload["bar_mode"] == "group"
    assert artifact.payload["series"] == (
        {
            "name": "Rachel Homan",
            "points": ({"x": 2023, "y": 6}, {"x": 2024, "y": 8}),
        },
        {
            "name": "Jennifer Jones",
            "points": ({"x": 2023, "y": 5}, {"x": 2024, "y": 7}),
        },
    )


def test_creates_multiple_line_series_without_bar_mode() -> None:
    artifact = VisualizationService().create(
        VisualizationRequest(
            result=AnalyticsResultData(
                columns=("event_year", "display_name", "wins"),
                rows=(
                    {"event_year": 2023, "display_name": "Rachel Homan", "wins": 6},
                    {"event_year": 2023, "display_name": "Jennifer Jones", "wins": 5},
                ),
            ),
            spec=ChartVisualizationSpec(
                type="chart",
                chart_type=ChartType.LINE,
                data_mapping=LongChartDataMapping(
                    format="long",
                    x_column="event_year",
                    y_column="wins",
                    series_column="display_name",
                ),
            ),
        )
    )

    assert "bar_mode" not in artifact.payload
    assert len(artifact.payload["series"]) == 2


def test_creates_an_average_summary_artifact() -> None:
    artifact = VisualizationService().create(
        VisualizationRequest(
            result=AnalyticsResultData(
                columns=("shots_percent",), rows=({"shots_percent": 80}, {"shots_percent": 90})
            ),
            spec=SummaryVisualizationSpec(
                type="summary",
                value_column="shots_percent",
                aggregation=SummaryAggregation.AVERAGE,
            ),
        )
    )

    assert artifact.payload["label"] == "Average shots_percent"
    assert artifact.payload["value"] == 85


def test_rejects_a_chart_with_a_non_numeric_y_axis() -> None:
    request = VisualizationRequest(
        result=AnalyticsResultData(
            columns=("event_year", "display_name"),
            rows=({"event_year": 2024, "display_name": "Brad Jacobs"},),
        ),
        spec=ChartVisualizationSpec(
            type="chart",
            chart_type=ChartType.BAR,
            data_mapping=LongChartDataMapping(
                format="long", x_column="event_year", y_column="display_name"
            ),
        ),
    )

    with pytest.raises(VisualizationRequestError, match="numeric"):
        VisualizationService().create(request)


def test_creates_a_bar_chart_from_selected_wide_stat_columns() -> None:
    artifact = VisualizationService().create(
        VisualizationRequest(
            result=AnalyticsResultData(
                columns=("inturn_percent", "outturn_percent", "draw_percent", "shots_percent"),
                rows=(
                    {
                        "inturn_percent": 81,
                        "outturn_percent": 83,
                        "draw_percent": 79,
                        "shots_percent": 82,
                    },
                ),
            ),
            spec=ChartVisualizationSpec(
                type="chart",
                chart_type=ChartType.BAR,
                data_mapping=WideChartDataMapping(
                    format="wide",
                    value_columns=("draw_percent", "outturn_percent", "shots_percent"),
                ),
            ),
        )
    )

    assert artifact.payload["points"] == (
        {"x": "Draw", "y": 79},
        {"x": "Outturn", "y": 83},
        {"x": "Shots", "y": 82},
    )


def test_requires_a_series_column_for_multiple_wide_rows() -> None:
    request = VisualizationRequest(
        result=AnalyticsResultData(
            columns=("draw_percent",),
            rows=({"draw_percent": 80}, {"draw_percent": 90}),
        ),
        spec=ChartVisualizationSpec(
            type="chart",
            chart_type=ChartType.BAR,
            data_mapping=WideChartDataMapping(format="wide", value_columns=("draw_percent",)),
        ),
    )

    with pytest.raises(VisualizationRequestError, match="series_column"):
        VisualizationService().create(request)


def test_tool_creates_an_artifact_from_a_typed_result() -> None:
    result = create_visualization_from_result(
        AnalyticsResultData(
            columns=("display_name", "wins"),
            rows=({"display_name": "Brad Jacobs", "wins": 6},),
        ),
        TableVisualizationSpec(type="table"),
    )

    assert json.loads(result) == {
        "type": "table",
        "payload": {
            "columns": ["display_name", "wins"],
            "rows": [{"display_name": "Brad Jacobs", "wins": 6}],
            "title": None,
        },
    }


def test_chart_converts_database_decimals_to_json_numbers() -> None:
    artifact = VisualizationService().create(
        VisualizationRequest(
            result=AnalyticsResultData(
                columns=("display_name", "draw_percentage"),
                rows=({"display_name": "Ben Hebert", "draw_percentage": Decimal("95.0")},),
            ),
            spec=ChartVisualizationSpec(
                type="chart",
                chart_type=ChartType.BAR,
                data_mapping=LongChartDataMapping(
                    format="long", x_column="display_name", y_column="draw_percentage"
                ),
            ),
        )
    )

    assert artifact.payload["points"] == ({"x": "Ben Hebert", "y": 95.0},)
    assert json.loads(artifact.model_dump_json())["payload"]["points"][0]["y"] == 95.0
