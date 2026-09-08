from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from curlchat.agent.tools import analytics_query
from curlchat.core.identities import ResolvedEventIdentity, ResolvedPlayerIdentity
from curlchat.db.models import Event, Player
from curlchat.db.session import Base
from curlchat.services.stats_service import AnalyticsQueryStatus


def test_rejects_a_resolved_event_identity_that_does_not_match_its_id(monkeypatch) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = Session(engine)
    session.add(Event(id=3, display_name="Canadian Women's", source_slug="canadian-womens"))
    session.commit()
    monkeypatch.setattr(analytics_query, "SessionLocal", lambda: session)

    result = analytics_query.run_analytics_query(
        "Compare the players at the Hearts",
        resolved_events=[ResolvedEventIdentity(display_name="Hearts", event_id=3)],
    )

    assert result.status is AnalyticsQueryStatus.UNSUPPORTED
    assert result.message == (
        "Resolved event mismatch: ID 3 is \"Canadian Women's\", not 'Hearts'. "
        "Resolve the event before querying."
    )


def test_rejects_a_resolved_player_identity_that_does_not_match_its_id(monkeypatch) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = Session(engine)
    session.add(Player(id=7, display_name="Rachel Homan", sortable_name="Homan, Rachel", normalized_name="rachel homan"))
    session.commit()
    monkeypatch.setattr(analytics_query, "SessionLocal", lambda: session)

    result = analytics_query.run_analytics_query(
        "Compare the players",
        resolved_players=[ResolvedPlayerIdentity(display_name="Jennifer Jones", player_id=7)],
    )

    assert result.status is AnalyticsQueryStatus.UNSUPPORTED
    assert result.message == (
        "Resolved player mismatch: ID 7 is 'Rachel Homan', not 'Jennifer Jones'. "
        "Resolve the player before querying."
    )
