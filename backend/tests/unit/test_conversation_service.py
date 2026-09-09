from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from curlchat.services.conversation_service import ConversationNotFoundError, ConversationService


def test_create_normalizes_and_truncates_a_conversation_title(sqlite_session: Session) -> None:
    service = ConversationService(lambda: sqlite_session)

    metadata = service.create("  Show   Brier  results  " + "x" * 120)

    assert metadata.title == ("Show Brier results " + "x" * 120)[:120]
    assert metadata.id


def test_get_raises_for_an_unknown_conversation(sqlite_session: Session) -> None:
    service = ConversationService(lambda: sqlite_session)
    conversation_id = uuid4()

    with pytest.raises(ConversationNotFoundError, match=str(conversation_id)):
        service.get(conversation_id)


def test_list_returns_most_recently_touched_conversation_first(sqlite_session: Session) -> None:
    service = ConversationService(lambda: sqlite_session)
    first = service.create("First conversation")
    second = service.create("Second conversation")
    service.touch(first.id)

    assert [metadata.id for metadata in service.list()] == [first.id, second.id]
