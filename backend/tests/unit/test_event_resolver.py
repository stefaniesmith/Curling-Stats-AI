from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from curlchat.agent.tools.event_resolver import resolve_event_name
from curlchat.db.models import Event
from curlchat.db.session import Base
from curlchat.services.event_resolver import EventResolutionStatus


def _session_with_events() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = Session(engine)
    session.add_all(
        [
            Event(display_name="Macdonald Brier", source_slug="macdonald-brier"),
            Event(display_name="Brier", source_slug="brier"),
            Event(display_name="Hearts", source_slug="hearts"),
            Event(display_name="Canada Cup (Men)", source_slug="canada-cup-men"),
            Event(display_name="Canada Cup (Women)", source_slug="canada-cup-women"),
            Event(display_name="Trials (Men)", source_slug="trials-men"),
            Event(display_name="Trials (Women)", source_slug="trials-women"),
        ]
    )
    session.commit()
    return session


def test_exact_event_name_beats_a_broader_shorthand_match() -> None:
    with _session_with_events() as session:
        resolution = resolve_event_name(session, "Brier")

    assert resolution.status is EventResolutionStatus.MATCHED
    assert resolution.event is not None
    assert resolution.event.display_name == "Brier"
    assert resolution.event.confidence == 1.0


def test_ignores_a_year_in_an_event_phrase() -> None:
    with _session_with_events() as session:
        resolution = resolve_event_name(session, "2023 Brier")

    assert resolution.status is EventResolutionStatus.MATCHED
    assert resolution.event is not None
    assert resolution.event.display_name == "Brier"


def test_returns_ambiguous_for_a_shorthand_that_matches_mens_and_womens_events() -> None:
    with _session_with_events() as session:
        resolution = resolve_event_name(session, "Canada Cup")

    assert resolution.status is EventResolutionStatus.AMBIGUOUS
    assert {match.display_name for match in resolution.matches} == {
        "Canada Cup (Men)",
        "Canada Cup (Women)",
    }


def test_resolves_a_clear_fuzzy_event_match() -> None:
    with _session_with_events() as session:
        resolution = resolve_event_name(session, "Herts")

    assert resolution.status is EventResolutionStatus.MATCHED
    assert resolution.event is not None
    assert resolution.event.display_name == "Hearts"
    assert 0.84 <= resolution.event.confidence < 1.0


def test_returns_not_found_for_an_unrelated_event() -> None:
    with _session_with_events() as session:
        resolution = resolve_event_name(session, "Scotties Tournament of Hearts")

    assert resolution.status is EventResolutionStatus.NOT_FOUND
    assert resolution.matches == ()
