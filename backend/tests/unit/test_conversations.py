from uuid import uuid4

from fastapi.testclient import TestClient

from curlchat.main import app
from curlchat.services.conversation_service import ConversationMetadata

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
