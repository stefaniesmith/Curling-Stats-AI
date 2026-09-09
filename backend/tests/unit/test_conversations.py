from uuid import uuid4

from fastapi.testclient import TestClient

from curlchat.agent.graph.app_graph import ConversationHistoryMessage
from curlchat.main import app
from curlchat.services.conversation_service import ConversationMetadata
from curlchat.services.visualization_service import VisualizationArtifact, VisualizationType

client = TestClient(app)


def test_list_conversations_serializes_service_metadata(monkeypatch) -> None:
    metadata = ConversationMetadata(
        id=uuid4(),
        title="Brad Jacobs Brier statistics",
        created_at="2026-09-06T00:00:00Z",
        updated_at="2026-09-06T12:00:00Z",
    )

    class FakeConversationService:
        def list(self) -> list[ConversationMetadata]:
            return [metadata]

    monkeypatch.setattr(
        "curlchat.api.routes.conversations.get_conversation_service",
        lambda: FakeConversationService(),
    )

    response = client.get("/api/conversations")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": str(metadata.id),
            "title": "Brad Jacobs Brier statistics",
            "created_at": "2026-09-06T00:00:00Z",
            "updated_at": "2026-09-06T12:00:00Z",
        }
    ]


def test_get_conversation_messages_returns_renderable_history(monkeypatch) -> None:
    metadata = ConversationMetadata(
        id=uuid4(),
        title="Brad Jacobs Brier statistics",
        created_at="2026-09-06T00:00:00Z",
        updated_at="2026-09-06T12:00:00Z",
    )

    class FakeConversationService:
        def get(self, conversation_id: object) -> ConversationMetadata:
            assert conversation_id == metadata.id
            return metadata

    monkeypatch.setattr(
        "curlchat.api.routes.conversations.get_conversation_service",
        lambda: FakeConversationService(),
    )
    monkeypatch.setattr(
        "curlchat.api.routes.conversations.load_conversation_history",
        lambda _: (
            ConversationHistoryMessage(role="user", content="Show Brad Jacobs' Brier statistics."),
            ConversationHistoryMessage(
                role="assistant",
                content="Here are the results.",
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
        ),
    )

    response = client.get(f"/api/conversations/{metadata.id}/messages")

    assert response.status_code == 200
    assert response.json() == [
        {"role": "user", "content": "Show Brad Jacobs' Brier statistics.", "blocks": []},
        {
            "role": "assistant",
            "content": "Here are the results.",
            "blocks": [
                {"type": "markdown", "payload": {"content": "Here are the results."}},
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
        },
    ]
