from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from curlchat.agent.tools.analytics_query import execute_analytics_query
from curlchat.db.models import Event, Player, PlayerEventStatistics
from curlchat.db.session import Base
from curlchat.repositories.analytics import AnalyticsRepository
from curlchat.services.stats_service import AnalyticsQueryStatus, StatsService


def _session_with_statistics() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = Session(engine)
    player = Player(
        display_name="Brad Gushue",
        sortable_name="Gushue, Brad",
        normalized_name="brad gushue",
    )
    event = Event(display_name="Brier", source_slug="brier")
    session.add_all([player, event])
    session.flush()
    session.add(
        PlayerEventStatistics(
            player_id=player.id,
            event_id=event.id,
            event_year=2024,
            team="NL",
            position="Skip",
            games=12,
            wins=10,
            losses=2,
            shots_total=100,
            shots_percent=88,
        )
    )
    session.commit()
    return session


def test_executes_a_parameterized_read_only_query() -> None:
    with _session_with_statistics() as session:
        result = execute_analytics_query(
            session,
            """
            SELECT p.display_name, s.event_year, s.shots_percent
            FROM players AS p
            JOIN player_event_statistics AS s ON s.player_id = p.id
            WHERE p.id = :player_id
            """,
            {"player_id": 1},
        )

    assert result.status is AnalyticsQueryStatus.SUCCESS
    assert result.columns == ("display_name", "event_year", "shots_percent")
    assert result.rows == (
        {"display_name": "Brad Gushue", "event_year": 2024, "shots_percent": 88},
    )
    assert not result.truncated


def test_rejects_mutating_sql() -> None:
    with _session_with_statistics() as session:
        result = execute_analytics_query(session, "DELETE FROM players")

    assert result.status is AnalyticsQueryStatus.UNSUPPORTED
    assert result.message == "Only read-only SELECT queries are supported."


def test_accepts_one_trailing_semicolon() -> None:
    with _session_with_statistics() as session:
        result = execute_analytics_query(session, "SELECT display_name FROM players;")

    assert result.status is AnalyticsQueryStatus.SUCCESS
    assert result.rows == ({"display_name": "Brad Gushue"},)


def test_rejects_non_analytics_tables() -> None:
    with _session_with_statistics() as session:
        result = execute_analytics_query(session, "SELECT * FROM player_aliases")

    assert result.status is AnalyticsQueryStatus.UNSUPPORTED
    assert result.message is not None
    assert "player_event_statistics" in result.message


def test_returns_a_structured_execution_failure() -> None:
    with _session_with_statistics() as session:
        result = execute_analytics_query(session, "SELECT missing_column FROM players")

    assert result.status is AnalyticsQueryStatus.EXECUTION_FAILURE
    assert result.message == "The analytics query could not be executed."


def test_caps_result_rows() -> None:
    with _session_with_statistics() as session:
        service = StatsService(AnalyticsRepository(session), row_limit=1)
        result = service.execute(
            "SELECT event_year FROM player_event_statistics UNION ALL SELECT event_year FROM player_event_statistics"
        )

    assert result.status is AnalyticsQueryStatus.SUCCESS
    assert result.rows == ({"event_year": 2024},)
    assert result.truncated
