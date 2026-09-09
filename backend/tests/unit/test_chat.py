from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from curlchat.agent.graph.app_graph import (
    AgentConfigurationError,
    AgentInvocationError,
    AgentResponse,
    AgentStreamEvent,
)
from curlchat.api.schemas.chat import artifact_block
from curlchat.main import app
from curlchat.services.conversation_service import ConversationMetadata, ConversationNotFoundError
from curlchat.services.visualization_service import VisualizationArtifact, VisualizationType

client = TestClient(app)


class FakeConversationService:
    def __init__(self) -> None:
        self.metadata = ConversationMetadata(
            id=uuid4(),
            title="Test conversation",
            created_at="2026-09-06T00:00:00Z",
            updated_at="2026-09-06T00:00:00Z",
        )
        self.touched: list[object] = []

    def create(self, _: str) -> ConversationMetadata:
        return self.metadata

    def get(self, conversation_id: object) -> ConversationMetadata:
        if conversation_id != self.metadata.id:
            raise ConversationNotFoundError(str(conversation_id))
        return self.metadata

    def touch(self, conversation_id: object) -> ConversationMetadata:
        self.touched.append(conversation_id)
        return self.metadata


def _install_conversation_service(monkeypatch) -> FakeConversationService:
    service = FakeConversationService()
    monkeypatch.setattr("curlchat.api.routes.chat.get_conversation_service", lambda: service)
    return service


def test_chat_returns_an_agent_response(monkeypatch) -> None:
    service = _install_conversation_service(monkeypatch)
    monkeypatch.setattr(
        "curlchat.api.routes.chat.respond_to_message",
        lambda message, conversation_id: AgentResponse(
            message=f"Answer for: {message}",
            artifacts=(
                VisualizationArtifact(
                    type=VisualizationType.TABLE,
                    payload={
                        "columns": ["wins"],
                        "column_labels": {"wins": "Wins"},
                        "rows": [{"wins": 8}],
                        "title": None,
                    },
                ),
            ),
        ),
    )

    response = client.post("/api/chat", json={"message": "Show Tyler Tardi's Brier statistics."})

    assert response.status_code == 200
    assert response.json() == {
        "conversation_id": str(service.metadata.id),
        "message": "Answer for: Show Tyler Tardi's Brier statistics.",
        "blocks": [
            {
                "type": "markdown",
                "payload": {"content": "Answer for: Show Tyler Tardi's Brier statistics."},
            },
            {
                "type": "table",
                "payload": {
                    "columns": ["wins"],
                    "column_labels": {"wins": "Wins"},
                    "rows": [{"wins": 8}],
                    "title": None,
                },
            },
        ],
    }


def test_chat_reports_missing_agent_configuration(monkeypatch) -> None:
    _install_conversation_service(monkeypatch)

    def missing_configuration(_: str, __: object) -> str:
        raise AgentConfigurationError("OPENAI_API_KEY is not configured.")

    monkeypatch.setattr("curlchat.api.routes.chat.respond_to_message", missing_configuration)

    response = client.post("/api/chat", json={"message": "Hello"})

    assert response.status_code == 503
    assert response.json() == {"detail": "The chat service is not configured."}


def test_chat_reports_model_provider_failure(monkeypatch) -> None:
    _install_conversation_service(monkeypatch)

    def unavailable(_: str, __: object) -> str:
        raise AgentInvocationError("The model provider could not complete the request.")

    monkeypatch.setattr("curlchat.api.routes.chat.respond_to_message", unavailable)

    response = client.post("/api/chat", json={"message": "Hello"})

    assert response.status_code == 503
    assert response.json() == {"detail": "The chat service is temporarily unavailable."}


def test_chat_rejects_unknown_conversation(monkeypatch) -> None:
    _install_conversation_service(monkeypatch)

    response = client.post("/api/chat", json={"message": "Hello", "conversation_id": str(uuid4())})

    assert response.status_code == 404
    assert response.json() == {"detail": "The requested conversation does not exist."}


def test_chat_rejects_blank_or_oversized_messages() -> None:
    blank_response = client.post("/api/chat", json={"message": " \n "})
    oversized_response = client.post("/api/chat", json={"message": "x" * 2_001})

    assert blank_response.status_code == 422
    assert oversized_response.status_code == 422


def test_artifact_boundary_rejects_a_table_without_display_labels() -> None:
    with pytest.raises(ValidationError, match="column_labels"):
        artifact_block(
            {
                "type": "table",
                "payload": {"columns": ["wins"], "rows": [{"wins": 8}], "title": None},
            }
        )


def test_streaming_chat_returns_ordered_sse_events(monkeypatch) -> None:
    service = _install_conversation_service(monkeypatch)
    monkeypatch.setattr(
        "curlchat.api.routes.chat.stream_response",
        lambda *_: iter(
            [
                AgentStreamEvent(type="markdown_delta", payload={"delta": "Here "}),
                AgentStreamEvent(
                    type="artifact",
                    payload={
                        "type": "table",
                        "payload": {
                            "columns": ["wins"],
                            "column_labels": {"wins": "Wins"},
                            "rows": [],
                            "title": None,
                        },
                    },
                ),
                AgentStreamEvent(type="complete"),
            ]
        ),
    )

    response = client.post("/api/chat/stream", json={"message": "Show stats"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.text == (
        f'event: message_start\ndata: {{"conversation_id": "{service.metadata.id}"}}\n\n'
        'event: markdown_delta\ndata: {"delta": "Here "}\n\n'
        'event: artifact\ndata: {"type": "table", "payload": {"columns": ["wins"], '
        '"column_labels": {"wins": "Wins"}, "rows": [], "title": null}}\n\n'
        "event: complete\ndata: {}\n\n"
    )
    assert service.touched == [service.metadata.id]


def test_streaming_chat_omits_unused_chart_fields(monkeypatch) -> None:
    _install_conversation_service(monkeypatch)
    monkeypatch.setattr(
        "curlchat.api.routes.chat.stream_response",
        lambda *_: iter(
            [
                AgentStreamEvent(
                    type="artifact",
                    payload={
                        "type": "chart",
                        "payload": {
                            "chart_type": "bar",
                            "x_column": "display_name",
                            "y_column": "wins",
                            "x_label": "Player",
                            "y_label": "Wins",
                            "title": "Brier wins",
                            "points": [{"x": "Taylor", "y": 8}],
                        },
                    },
                ),
                AgentStreamEvent(type="complete"),
            ]
        ),
    )

    response = client.post("/api/chat/stream", json={"message": "Chart Brier wins"})

    assert response.status_code == 200
    assert '"points": [{"x": "Taylor", "y": 8.0}]' in response.text
    assert '"series": null' not in response.text
    assert '"series_column": null' not in response.text
