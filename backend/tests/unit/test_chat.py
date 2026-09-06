from fastapi.testclient import TestClient

from curlchat.agent.graph.app_graph import (
    AgentConfigurationError,
    AgentInvocationError,
    AgentResponse,
)
from curlchat.main import app
from curlchat.services.visualization_service import VisualizationArtifact, VisualizationType

client = TestClient(app)


def test_chat_returns_an_agent_response(monkeypatch) -> None:
    monkeypatch.setattr(
        "curlchat.api.routes.chat.respond_to_message",
        lambda message: AgentResponse(
            message=f"Answer for: {message}",
            artifacts=(
                VisualizationArtifact(
                    type=VisualizationType.TABLE,
                    payload={"columns": ["wins"], "rows": [{"wins": 8}]},
                ),
            ),
        ),
    )

    response = client.post("/api/chat", json={"message": "Show Tyler Tardi's Brier statistics."})

    assert response.status_code == 200
    assert response.json() == {
        "conversation_id": None,
        "message": "Answer for: Show Tyler Tardi's Brier statistics.",
        "blocks": [
            {
                "type": "markdown",
                "payload": {"content": "Answer for: Show Tyler Tardi's Brier statistics."},
            },
            {"type": "table", "payload": {"columns": ["wins"], "rows": [{"wins": 8}]}},
        ],
    }


def test_chat_reports_missing_agent_configuration(monkeypatch) -> None:
    def missing_configuration(_: str) -> str:
        raise AgentConfigurationError("OPENAI_API_KEY is not configured.")

    monkeypatch.setattr("curlchat.api.routes.chat.respond_to_message", missing_configuration)

    response = client.post("/api/chat", json={"message": "Hello"})

    assert response.status_code == 503
    assert response.json() == {"detail": "The chat service is not configured."}


def test_chat_reports_model_provider_failure(monkeypatch) -> None:
    def unavailable(_: str) -> str:
        raise AgentInvocationError("The model provider could not complete the request.")

    monkeypatch.setattr("curlchat.api.routes.chat.respond_to_message", unavailable)

    response = client.post("/api/chat", json={"message": "Hello"})

    assert response.status_code == 503
    assert response.json() == {"detail": "The chat service is temporarily unavailable."}
