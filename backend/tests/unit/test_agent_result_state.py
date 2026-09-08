"""State-backed handoff tests for analytics and visualization tools."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Annotated, Any, TypedDict

from langchain_core.messages import AIMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from curlchat.agent.tools import analytics_query
from curlchat.agent.tools.analytics_query import query_analytics
from curlchat.agent.tools.visualization import create_visualization
from curlchat.services.stats_service import AnalyticsQueryResult, AnalyticsQueryStatus


def _tool_call(name: str, arguments: dict[str, object]) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{"name": name, "args": arguments, "id": "tool-call", "type": "tool_call"}],
    )


class _TestState(TypedDict):
    messages: Annotated[list[Any], add_messages]
    latest_analytics_result: dict[str, object] | None


def _run_tool(tool: object, state: _TestState) -> _TestState:
    graph = StateGraph(_TestState)
    graph.add_node("tools", ToolNode([tool]))  # type: ignore[list-item]
    graph.add_edge(START, "tools")
    graph.add_edge("tools", END)
    return graph.compile().invoke(state)


def test_successful_query_updates_the_latest_analytics_result(
    monkeypatch,
) -> None:
    expected = AnalyticsQueryResult(
        status=AnalyticsQueryStatus.SUCCESS,
        columns=("draw_percentage",),
        rows=({"draw_percentage": Decimal("95.0")},),
    )
    monkeypatch.setattr(analytics_query, "run_analytics_query", lambda *_: expected)

    update = _run_tool(
        query_analytics,
        {"messages": [_tool_call("query_analytics", {"request": "Top draw percentage"})]}
    )

    assert update["latest_analytics_result"] == {
        "columns": ("draw_percentage",),
        "rows": ({"draw_percentage": Decimal("95.0")},),
    }
    assert json.loads(update["messages"][-1].content)["rows"] == [{"draw_percentage": "95.0"}]


def test_visualization_reads_typed_latest_result_from_state() -> None:
    update = _run_tool(
        create_visualization,
        {
            "messages": [
                _tool_call(
                    "create_visualization",
                    {
                        "spec": {
                            "type": "chart",
                            "chart_type": "bar",
                            "data_mapping": {
                                "format": "long",
                                "x_column": "display_name",
                                "y_column": "draw_percentage",
                            },
                        }
                    },
                )
            ],
            "latest_analytics_result": {
                "columns": ("display_name", "draw_percentage"),
                "rows": (
                    {"display_name": "Ben Hebert", "draw_percentage": Decimal("95.0")},
                ),
            },
        }
    )

    payload = json.loads(update["messages"][-1].content)["payload"]
    assert payload["points"] == [{"x": "Ben Hebert", "y": 95.0}]
