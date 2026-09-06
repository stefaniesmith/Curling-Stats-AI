from curlchat.db.models import Event, Player, PlayerAlias, PlayerEventStatistics
from curlchat.db.session import Base


def test_analytics_models_register_the_documented_tables() -> None:
    assert set(Base.metadata.tables) == {
        "players",
        "player_aliases",
        "events",
        "player_event_statistics",
    }


def test_analytics_tables_include_documentation_comments() -> None:
    for model in (Player, PlayerAlias, Event, PlayerEventStatistics):
        assert model.__table__.comment
        assert all(column.comment for column in model.__table__.columns)


def test_statistics_identity_is_unique_per_player_event_and_year() -> None:
    unique_constraints = [
        constraint
        for constraint in PlayerEventStatistics.__table__.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    ]

    assert any(
        tuple(column.name for column in constraint.columns)
        == ("player_id", "event_id", "event_year", "team", "position")
        for constraint in unique_constraints
    )


def test_statistics_match_the_archive_yearly_record_fields() -> None:
    assert set(PlayerEventStatistics.__table__.columns.keys()) >= {
        "event_year",
        "team",
        "position",
        "alternate",
        "games",
        "wins",
        "losses",
        "inturn_total",
        "inturn_percent",
        "outturn_total",
        "outturn_percent",
        "draw_total",
        "draw_percent",
        "takeout_total",
        "takeout_percent",
        "shots_total",
        "shots_percent",
    }
