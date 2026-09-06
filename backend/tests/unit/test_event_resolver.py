from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from curlchat.agent.tools.event_resolver import resolve_event_name
from curlchat.core.identities import ResolvedPlayerIdentity
from curlchat.db.models import Event, Player, PlayerEventStatistics
from curlchat.db.session import Base
from curlchat.services.event_resolver import EventResolutionStatus


def _session_with_events() -> tuple[Session, Player]:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = Session(engine)
    events = [
        Event(display_name="Macdonald Brier", source_slug="macdonald-brier"),
        Event(display_name="Brier", source_slug="brier"),
        Event(display_name="Hearts", source_slug="hearts"),
        Event(display_name="Canada Cup (Men)", source_slug="canada-cup-men"),
        Event(display_name="Canada Cup (Women)", source_slug="canada-cup-women"),
        Event(display_name="Trials (Men)", source_slug="trials-men"),
        Event(display_name="Trials (Women)", source_slug="trials-women"),
    ]
    brad_jacobs = Player(
        display_name="Brad Jacobs",
        sortable_name="Jacobs, Brad",
        normalized_name="brad jacobs",
    )
    session.add_all([*events, brad_jacobs])
    session.flush()
    session.add(
        PlayerEventStatistics(
            player_id=brad_jacobs.id,
            event_id=events[3].id,
            event_year=2023,
            team="ON",
            position="Skip",
            games=8,
            wins=5,
            losses=3,
        )
    )
    session.commit()
    return session, brad_jacobs


def test_exact_event_name_beats_a_broader_shorthand_match() -> None:
    session, brad_jacobs = _session_with_events()
    with session:
        resolution = resolve_event_name(session, "Brier")

    assert resolution.status is EventResolutionStatus.MATCHED
    assert resolution.event is not None
    assert resolution.event.display_name == "Brier"
    assert resolution.event.confidence == 1.0


def test_ignores_a_year_in_an_event_phrase() -> None:
    session, brad_jacobs = _session_with_events()
    with session:
        resolution = resolve_event_name(session, "2023 Brier")

    assert resolution.status is EventResolutionStatus.MATCHED
    assert resolution.event is not None
    assert resolution.event.display_name == "Brier"


def test_returns_ambiguous_for_a_shorthand_that_matches_mens_and_womens_events() -> None:
    session, brad_jacobs = _session_with_events()
    with session:
        resolution = resolve_event_name(session, "Canada Cup")

    assert resolution.status is EventResolutionStatus.AMBIGUOUS
    assert {match.display_name for match in resolution.matches} == {
        "Canada Cup (Men)",
        "Canada Cup (Women)",
    }


def test_uses_resolved_player_statistics_to_disambiguate_an_event() -> None:
    session, brad_jacobs = _session_with_events()
    with session:
        resolution = resolve_event_name(
            session,
            "Canada Cup",
            resolved_players=(
                ResolvedPlayerIdentity(display_name="Brad Jacobs", player_id=brad_jacobs.id),
            ),
        )

    assert resolution.status is EventResolutionStatus.MATCHED
    assert resolution.event is not None
    assert resolution.event.display_name == "Canada Cup (Men)"


def test_resolves_a_clear_fuzzy_event_match() -> None:
    session, brad_jacobs = _session_with_events()
    with session:
        resolution = resolve_event_name(session, "Herts")

    assert resolution.status is EventResolutionStatus.MATCHED
    assert resolution.event is not None
    assert resolution.event.display_name == "Hearts"
    assert 0.84 <= resolution.event.confidence < 1.0


def test_returns_not_found_for_an_unrelated_event() -> None:
    session, brad_jacobs = _session_with_events()
    with session:
        resolution = resolve_event_name(session, "Scotties Tournament of Hearts")

    assert resolution.status is EventResolutionStatus.NOT_FOUND
    assert resolution.matches == ()
