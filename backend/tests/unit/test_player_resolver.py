from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from curlchat.agent.tools.player_resolver import resolve_player_name
from curlchat.core.names import normalize_name
from curlchat.db.models import Player, PlayerAlias
from curlchat.db.session import Base
from curlchat.services.player_resolver import PlayerResolutionStatus


def _player(display_name: str, sortable_name: str) -> Player:
    return Player(
        display_name=display_name,
        sortable_name=sortable_name,
        normalized_name=normalize_name(sortable_name),
    )


def _session_with_players() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = Session(engine)

    brad_gushue = _player("Brad Gushue", "Gushue, Brad")
    rachel_brown = _player("Rachel Brown", "Brown, Rachel")
    rachelle_brown = _player("Rachelle Brown", "Brown, Rachelle")
    session.add_all([brad_gushue, rachel_brown, rachelle_brown])
    session.flush()
    session.add(
        PlayerAlias(
            player_id=brad_gushue.id,
            alias_name="Gushue, Bradley",
            normalized_name=normalize_name("Gushue, Bradley"),
        )
    )
    session.commit()
    return session


def test_resolves_canonical_name_in_display_or_sortable_order() -> None:
    with _session_with_players() as session:
        display_resolution = resolve_player_name(session, "Brad Gushue")
        sortable_resolution = resolve_player_name(session, "  Gushue, Brad ")

    assert display_resolution.status is PlayerResolutionStatus.MATCHED
    assert display_resolution.player is not None
    assert display_resolution.player.canonical_name == "Brad Gushue"
    assert display_resolution.player.confidence == 1.0
    assert not display_resolution.player.matched_alias
    assert sortable_resolution.status is PlayerResolutionStatus.MATCHED
    assert sortable_resolution.matches == display_resolution.matches


def test_resolves_an_archive_alias_to_its_canonical_player() -> None:
    with _session_with_players() as session:
        resolution = resolve_player_name(session, "Gushue, Bradley")

    assert resolution.status is PlayerResolutionStatus.MATCHED
    assert resolution.player is not None
    assert resolution.player.canonical_name == "Brad Gushue"
    assert resolution.player.matched_alias


def test_returns_ambiguous_when_an_alias_identifies_multiple_players() -> None:
    with _session_with_players() as session:
        players = session.query(Player).filter(Player.display_name.like("%Brown")).all()
        session.add_all(
            [
                PlayerAlias(
                    player_id=player.id,
                    alias_name="Pidherny, Rachel",
                    normalized_name=normalize_name("Pidherny, Rachel"),
                )
                for player in players
            ]
        )
        session.commit()

        resolution = resolve_player_name(session, "Rachel Pidherny")

    assert resolution.status is PlayerResolutionStatus.AMBIGUOUS
    assert {match.canonical_name for match in resolution.matches} == {
        "Rachel Brown",
        "Rachelle Brown",
    }


def test_resolves_a_clear_fuzzy_match_with_confidence() -> None:
    with _session_with_players() as session:
        resolution = resolve_player_name(session, "Brad Gushuee")

    assert resolution.status is PlayerResolutionStatus.MATCHED
    assert resolution.player is not None
    assert resolution.player.canonical_name == "Brad Gushue"
    assert 0.84 <= resolution.player.confidence < 1.0


def test_returns_not_found_for_an_unrelated_name() -> None:
    with _session_with_players() as session:
        resolution = resolve_player_name(session, "Ada Lovelace")

    assert resolution.status is PlayerResolutionStatus.NOT_FOUND
    assert resolution.matches == ()
