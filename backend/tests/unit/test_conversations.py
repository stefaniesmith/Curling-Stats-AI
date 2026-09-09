from datetime import UTC, datetime

from fastapi.testclient import TestClient

from curlchat.agent.graph.app_graph import ConversationHistoryMessage
from curlchat.services.conversation_service import ConversationMetadata
from curlchat.services.visualization_service import VisualizationType
from tests.factories import ConversationMetadataFactory, VisualizationArtifactFactory


def test_list_conversations_serializes_service_metadata(
    monkeypatch, api_client: TestClient
) -> None:
    metadata = ConversationMetadataFactory.build(
        title="Brad Jacobs Brier statistics",
        created_at=datetime(2026, 9, 6, tzinfo=UTC),
        updated_at=datetime(2026, 9, 6, 12, tzinfo=UTC),
    )

    class FakeConversationService:
        def list(self) -> list[ConversationMetadata]:
            return [metadata]

    monkeypatch.setattr(
        "curlchat.api.routes.conversations.get_conversation_service",
        lambda: FakeConversationService(),
    )

    response = api_client.get("/api/conversations")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": str(metadata.id),
            "title": "Brad Jacobs Brier statistics",
            "created_at": "2026-09-06T00:00:00Z",
            "updated_at": "2026-09-06T12:00:00Z",
        }
    ]


def test_get_conversation_messages_returns_renderable_history(
    monkeypatch, api_client: TestClient
) -> None:
    metadata = ConversationMetadataFactory.build(
        title="Brad Jacobs Brier statistics",
        created_at=datetime(2026, 9, 6, tzinfo=UTC),
        updated_at=datetime(2026, 9, 6, 12, tzinfo=UTC),
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
                    VisualizationArtifactFactory.build(
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

    response = api_client.get(f"/api/conversations/{metadata.id}/messages")

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
