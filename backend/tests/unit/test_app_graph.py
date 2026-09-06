from types import SimpleNamespace

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
        "tools": [app_graph.resolve_player, app_graph.resolve_event, app_graph.query_analytics],
        "prompt": app_graph.SYSTEM_PROMPT,
    }
    query_schema = app_graph.query_analytics.args_schema.model_json_schema()
    resolver_schema = app_graph.resolve_player.args_schema.model_json_schema()
    event_resolver_schema = app_graph.resolve_event.args_schema.model_json_schema()
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
    assert event_resolver_schema["properties"]["name"]["description"] == (
        "The event name exactly as the user expressed it, including shorthand. Omit years."
    )
    assert "Successful Event Resolver results only" in query_schema["properties"]["resolved_events"][
        "description"
    ]
    assert "never generate, request, or expose SQL" in app_graph.SYSTEM_PROMPT.replace("\n", " ")


def test_respond_to_message_returns_final_text(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeGraph:
        def invoke(self, state: dict[str, object]) -> dict[str, object]:
            assert state == {"messages": [{"role": "user", "content": "Show Brier stats"}]}
            return {"messages": [SimpleNamespace(content="Here are the statistics.")]}

    monkeypatch.setattr(app_graph, "build_graph", lambda settings=None: FakeGraph())

    assert app_graph.respond_to_message("Show Brier stats") == "Here are the statistics."


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
