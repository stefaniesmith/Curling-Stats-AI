from types import SimpleNamespace
from uuid import uuid4

import pytest
from openai import OpenAIError
from pydantic import SecretStr

from curlchat.agent.graph import app_graph
from curlchat.db.session import Settings


def test_build_graph_requires_an_api_key() -> None:
    settings = Settings(openai_api_key=None)

    with pytest.raises(app_graph.AgentConfigurationError, match="OPENAI_API_KEY"):
        app_graph.build_graph(settings)


def test_build_graph_configures_model_and_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_model(**kwargs: object) -> object:
        captured["model"] = kwargs
        return "model"

    def fake_graph(**kwargs: object) -> object:
        captured["graph"] = kwargs
        return "graph"

    monkeypatch.setattr(app_graph, "ChatOpenAI", fake_model)
    monkeypatch.setattr(app_graph, "create_react_agent", fake_graph)

    graph = app_graph.build_graph(
        Settings(openai_api_key=SecretStr("test-key"), openai_model="test-model")
    )

    assert graph == "graph"
    assert captured["model"] == {
        "model": "test-model",
        "api_key": "test-key",
        "temperature": 0,
        "max_completion_tokens": 800,
    }
    assert captured["graph"] == {
        "model": "model",
        "tools": [
            app_graph.resolve_player,
            app_graph.resolve_event,
            app_graph.query_analytics,
            app_graph.create_visualization,
        ],
        "prompt": app_graph.SYSTEM_PROMPT,
    }
    query_schema = app_graph.query_analytics.args_schema.model_json_schema()
    resolver_schema = app_graph.resolve_player.args_schema.model_json_schema()
    event_resolver_schema = app_graph.resolve_event.args_schema.model_json_schema()
    visualization_schema = app_graph.create_visualization.args_schema.model_json_schema()
    assert "sql" not in query_schema["properties"]
    assert set(query_schema["properties"]) == {"request", "resolved_players", "resolved_events"}
    assert "display_name" in str(query_schema)
    assert "player_id" in str(query_schema)
    assert "event_id" in str(query_schema)
    assert resolver_schema["properties"]["name"]["description"] == (
        "The player name exactly as the user expressed it, including an alias or misspelling."
    )
    assert query_schema["properties"]["request"]["description"] == (
        "The user's analytical question in natural language, never SQL."
    )
    assert "Successful Player Resolver results only" in query_schema["properties"]["resolved_players"][
        "description"
    ]
    assert set(event_resolver_schema["properties"]) == {"name", "resolved_players"}
    assert event_resolver_schema["properties"]["name"]["description"] == (
        "The event name exactly as the user expressed it, including shorthand. Omit years."
    )
    assert "disambiguate otherwise matching events" in event_resolver_schema["properties"][
        "resolved_players"
    ]["description"]
    assert "Successful Event Resolver results only" in query_schema["properties"]["resolved_events"][
        "description"
    ]
    assert "never generate, request, or expose SQL" in app_graph.SYSTEM_PROMPT.replace("\n", " ")
    assert "Canada Cup (Men)" in app_graph.SYSTEM_PROMPT
    assert "Tournament of Hearts \"Hearts\"" in app_graph.SYSTEM_PROMPT
    assert "Scotties" in app_graph.SYSTEM_PROMPT
    assert set(visualization_schema["properties"]) == {"request"}
    assert visualization_schema["properties"]["request"]["description"] == (
        "One successful analytics result plus a typed table, summary, or chart specification. "
        "Pass result rows unchanged."
    )


def test_build_graph_adds_a_checkpointer_when_supplied(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(app_graph, "ChatOpenAI", lambda **_: "model")
    monkeypatch.setattr(
        app_graph, "create_react_agent", lambda **kwargs: captured.update(kwargs) or "graph"
    )

    checkpointer = object()
    assert (
        app_graph.build_graph(
            Settings(openai_api_key=SecretStr("test-key")), checkpointer=checkpointer  # type: ignore[arg-type]
        )
        == "graph"
    )
    assert captured["checkpointer"] is checkpointer


def test_respond_to_message_returns_final_text(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeGraph:
        def invoke(self, state: dict[str, object]) -> dict[str, object]:
            assert state == {"messages": [{"role": "user", "content": "Show Brier stats"}]}
            return {"messages": [SimpleNamespace(content="Here are the statistics.")]}

    monkeypatch.setattr(app_graph, "build_graph", lambda settings=None: FakeGraph())

    assert app_graph.respond_to_message("Show Brier stats") == app_graph.AgentResponse(
        message="Here are the statistics."
    )


def test_respond_to_message_uses_conversation_id_as_langgraph_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation_id = uuid4()
    captured: dict[str, object] = {}

    class FakeGraph:
        def invoke(self, state: dict[str, object], config: dict[str, object]) -> dict[str, object]:
            captured["state"] = state
            captured["config"] = config
            return {"messages": [SimpleNamespace(content="A persisted response.")]}

    class FakeCheckpointerContext:
        def __enter__(self) -> object:
            return "checkpointer"

        def __exit__(self, *_: object) -> None:
            return None

    monkeypatch.setattr(
        app_graph.PostgresSaver,
        "from_conn_string",
        lambda connection_string: captured.setdefault("connection_string", connection_string)
        and FakeCheckpointerContext(),
    )
    monkeypatch.setattr(
        app_graph,
        "build_graph",
        lambda settings=None, checkpointer=None: captured.setdefault("checkpointer", checkpointer)
        and FakeGraph(),
    )

    response = app_graph.respond_to_message(
        "Remember this", conversation_id, Settings(openai_api_key=SecretStr("test-key"))
    )

    assert response.message == "A persisted response."
    assert captured["checkpointer"] == "checkpointer"
    assert captured["config"] == {"configurable": {"thread_id": str(conversation_id)}}
    assert captured["state"] == {"messages": [{"role": "user", "content": "Remember this"}]}


def test_psycopg_url_removes_sqlalchemy_driver_suffix() -> None:
    assert app_graph._psycopg_url("postgresql+psycopg://state:secret@localhost:5432/curlchat") == (
        "postgresql://state:secret@localhost:5432/curlchat"
    )


def test_respond_to_message_collects_visualization_artifacts(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeGraph:
        def invoke(self, _: dict[str, object]) -> dict[str, object]:
            return {
                "messages": [
                    SimpleNamespace(
                        name="create_visualization",
                        content=(
                            '{"type":"chart","payload":{"chart_type":"bar","points":[]}}'
                        ),
                    ),
                    SimpleNamespace(content="Here is a chart."),
                ]
            }

    monkeypatch.setattr(app_graph, "build_graph", lambda settings=None: FakeGraph())

    response = app_graph.respond_to_message("Compare wins")

    assert response.message == "Here is a chart."
    assert response.artifacts[0].type == "chart"


def test_respond_to_message_omits_artifacts_from_prior_persisted_turns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeGraph:
        def invoke(self, _: dict[str, object], config: dict[str, object]) -> dict[str, object]:
            return {
                "messages": [
                    SimpleNamespace(type="human", content="Show prior results"),
                    SimpleNamespace(
                        name="create_visualization",
                        content='{"type":"chart","payload":{"title":"Old chart"}}',
                    ),
                    SimpleNamespace(type="ai", content="Here is the old chart."),
                    SimpleNamespace(type="human", content="Show current results"),
                    SimpleNamespace(
                        name="create_visualization",
                        content='{"type":"chart","payload":{"title":"New chart"}}',
                    ),
                    SimpleNamespace(type="ai", content="Here is the new chart."),
                ]
            }

    monkeypatch.setattr(app_graph, "build_graph", lambda settings=None, checkpointer=None: FakeGraph())

    response = app_graph.respond_to_message("Show current results", uuid4())

    assert [artifact.payload["title"] for artifact in response.artifacts] == ["New chart"]


def test_message_text_extracts_responses_content_blocks() -> None:
    assert app_graph._message_text(
        [{"type": "text", "text": "First"}, {"type": "text", "text": "Second"}]
    ) == "First\nSecond"


def test_respond_to_message_hides_provider_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    class FailingGraph:
        def invoke(self, _: dict[str, object]) -> None:
            raise OpenAIError("provider details")

    monkeypatch.setattr(app_graph, "build_graph", lambda settings=None: FailingGraph())

    with pytest.raises(app_graph.AgentInvocationError, match="could not complete"):
        app_graph.respond_to_message("Show Brier statistics")
