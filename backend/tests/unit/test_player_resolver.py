import pytest
from sqlalchemy.orm import Session

from curlchat.agent.tools.player_resolver import resolve_player_name
from curlchat.core.names import normalize_name
from curlchat.db.models import Player, PlayerAlias
from curlchat.services.player_resolver import PlayerResolutionStatus


def _player(display_name: str, sortable_name: str) -> Player:
    return Player(
        display_name=display_name,
        sortable_name=sortable_name,
        normalized_name=normalize_name(sortable_name),
    )


def _add_players(session: Session) -> None:
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


@pytest.mark.parametrize(
    ("name", "matched_alias"),
    [
        ("Brad Gushue", False),
        ("  Gushue, Brad ", False),
        ("Gushue, Bradley", True),
    ],
    ids=["display-name", "sortable-name", "archive-alias"],
)
def test_resolves_exact_canonical_or_alias_names(
    sqlite_session: Session, name: str, matched_alias: bool
) -> None:
    _add_players(sqlite_session)
    resolution = resolve_player_name(sqlite_session, name)

    assert resolution.status is PlayerResolutionStatus.MATCHED
    assert resolution.player is not None
    assert resolution.player.canonical_name == "Brad Gushue"
    assert resolution.player.confidence == 1.0
    assert resolution.player.matched_alias is matched_alias


def test_returns_ambiguous_when_an_alias_identifies_multiple_players(
    sqlite_session: Session,
) -> None:
    _add_players(sqlite_session)
    players = sqlite_session.query(Player).filter(Player.display_name.like("%Brown")).all()
    sqlite_session.add_all(
        [
            PlayerAlias(
                player_id=player.id,
                alias_name="Pidherny, Rachel",
                normalized_name=normalize_name("Pidherny, Rachel"),
            )
            for player in players
        ]
    )
    sqlite_session.commit()

    resolution = resolve_player_name(sqlite_session, "Rachel Pidherny")

    assert resolution.status is PlayerResolutionStatus.AMBIGUOUS
    assert {match.canonical_name for match in resolution.matches} == {
        "Rachel Brown",
        "Rachelle Brown",
    }


def test_resolves_a_clear_fuzzy_match_with_confidence(sqlite_session: Session) -> None:
    _add_players(sqlite_session)
    resolution = resolve_player_name(sqlite_session, "Brad Gushuee")

    assert resolution.status is PlayerResolutionStatus.MATCHED
    assert resolution.player is not None
    assert resolution.player.canonical_name == "Brad Gushue"
    assert 0.84 <= resolution.player.confidence < 1.0


def test_returns_not_found_for_an_unrelated_name(sqlite_session: Session) -> None:
    _add_players(sqlite_session)
    resolution = resolve_player_name(sqlite_session, "Ada Lovelace")

    assert resolution.status is PlayerResolutionStatus.NOT_FOUND
    assert resolution.matches == ()
