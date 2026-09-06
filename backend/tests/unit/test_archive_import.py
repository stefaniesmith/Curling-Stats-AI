from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from curlchat.db.models import Event, Player, PlayerAlias, PlayerEventStatistics
from curlchat.db.session import Base
from curlchat.ingest.archive import import_archive, load_archive, normalize_name


def _write_archive_file(root: Path, event: str, filename: str, content: str) -> None:
    directory = root / "src" / "data" / "players" / event
    directory.mkdir(parents=True, exist_ok=True)
    (directory / filename).write_text(content, encoding="utf-8")


def _canonical_player_document() -> str:
    return """---
name: Marla Mallett
name-sort: Mallett, Marla
totals:
  - event: Hearts
    games: 999
years:
  - year: 1995
    event: Hearts
    team: BC
    position: Fourth
    alternate: false
    games: 11
    wins: 6
    losses: 5
    inturn-total: 80
    inturn-percent: 74
    outturn-total: 129
    outturn-percent: 80
    draw-total: 99
    draw-percent: 77
    takeout-total: 110
    takeout-percent: 79
    shots-total: 209
    shots-percent: 78
---
"""


def test_load_archive_resolves_aka_redirects_and_ignores_totals(tmp_path: Path) -> None:
    _write_archive_file(tmp_path, "hearts", "mallett-marla.md", _canonical_player_document())
    _write_archive_file(
        tmp_path,
        "hearts",
        "geiger-marla.md",
        "---\nname: Marla Geiger\nname-sort: Geiger, Marla\naka: Mallett, Marla\n---\n",
    )

    dataset = load_archive(tmp_path)

    assert dataset.source_file_count == 2
    assert [player.sortable_name for player in dataset.players] == ["Mallett, Marla"]
    assert dataset.players[0].years[0].values["games"] == 11
    assert [(alias.sortable_name, alias.target_sortable_name) for alias in dataset.aliases] == [
        ("Geiger, Marla", "Mallett, Marla")
    ]


def test_load_archive_discards_yearly_totals_and_retains_player_stints(tmp_path: Path) -> None:
    document = """---
name: Kevin Adams
name-sort: Adams, Kevin
totals:
  - event: Brier
years:
  - year: 1990
    event: Brier
    team: QC
    position: Third
    games: 1
  - year: 1990
    event: Brier
    team: QC
    position: Fourth
    games: 8
  - year: 1990
    event: Brier
    team: Totals
    games: 9
---
"""
    _write_archive_file(tmp_path, "brier", "adams-kevin.md", document)

    dataset = load_archive(tmp_path)

    assert {
        (record.values["team"], record.values["position"]) for record in dataset.players[0].years
    } == {
        ("QC", "Third"),
        ("QC", "Fourth"),
    }


def test_load_archive_uses_totals_event_as_the_yearly_event_family(tmp_path: Path) -> None:
    document = """---
name: Joyce McKee
name-sort: McKee, Joyce
totals:
  - event: Canadian Women's
    games: 57
years:
  - year: 1961
    event: Diamond D
    team: SK
    position: Fourth
    games: 9
  - year: 1969
    event: CLCA
    team: SK
    position: Fourth
    games: 9
---
"""
    _write_archive_file(tmp_path, "canadian-women", "mckee-joyce.md", document)

    dataset = load_archive(tmp_path)

    assert [year.event for year in dataset.players[0].years] == [
        "Canadian Women's",
        "Canadian Women's",
    ]


def test_load_archive_requires_one_totals_event_mapping(tmp_path: Path) -> None:
    document = """---
name: Kevin Adams
name-sort: Adams, Kevin
years: []
---
"""
    _write_archive_file(tmp_path, "brier", "adams-kevin.md", document)

    with pytest.raises(ValueError, match="exactly one totals mapping"):
        load_archive(tmp_path)


def test_import_archive_upserts_yearly_statistics_and_aliases(tmp_path: Path) -> None:
    _write_archive_file(tmp_path, "hearts", "mallett-marla.md", _canonical_player_document())
    _write_archive_file(
        tmp_path,
        "hearts",
        "geiger-marla.md",
        "---\nname: Marla Geiger\nname-sort: Geiger, Marla\naka: Mallett, Marla\n---\n",
    )
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        report = import_archive(session, tmp_path)
        session.commit()
        repeat_report = import_archive(session, tmp_path)
        session.commit()

        player = session.scalar(select(Player))
        alias = session.scalar(select(PlayerAlias))
        event = session.scalar(select(Event))
        statistic = session.scalar(select(PlayerEventStatistics))

    assert report == repeat_report
    assert report.yearly_statistics == 1
    assert player is not None and player.display_name == "Marla Mallett"
    assert alias is not None and alias.alias_name == "Geiger, Marla"
    assert event is not None and event.first_event_year == 1995
    assert statistic is not None and statistic.shots_total == 209
    assert statistic.shots_percent == 78


def test_import_archive_merges_source_names_that_only_differ_by_case(tmp_path: Path) -> None:
    _write_archive_file(
        tmp_path,
        "brier",
        "macdonald-frank.md",
        _canonical_player_document()
        .replace("Marla Mallett", "Frank MacDonald")
        .replace("Mallett, Marla", "MacDonald, Frank"),
    )
    _write_archive_file(
        tmp_path,
        "macdonald-brier",
        "macdonald-frank.md",
        _canonical_player_document()
        .replace("Marla Mallett", "Frank Macdonald")
        .replace("Mallett, Marla", "Macdonald, Frank")
        .replace("1995", "1961"),
    )
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        report = import_archive(session, tmp_path)
        session.commit()
        players = list(session.scalars(select(Player)))

    assert report.players == 1
    assert len(players) == 1


def test_load_archive_skips_conflicting_aliases(tmp_path: Path) -> None:
    _write_archive_file(tmp_path, "hearts", "mallett-marla.md", _canonical_player_document())
    _write_archive_file(
        tmp_path,
        "trials-women",
        "brown-rachel.md",
        _canonical_player_document()
        .replace("Marla Mallett", "Rachel Brown")
        .replace("Mallett, Marla", "Brown, Rachel"),
    )
    _write_archive_file(
        tmp_path,
        "hearts",
        "pidherny-rachel.md",
        "---\nname: Rachel Pidherny\nname-sort: Pidherny, Rachel\naka: Mallett, Marla\n---\n",
    )
    _write_archive_file(
        tmp_path,
        "trials-women",
        "pidherny-rachel.md",
        "---\nname: Rachel Pidherny\nname-sort: Pidherny, Rachel\naka: Brown, Rachel\n---\n",
    )

    dataset = load_archive(tmp_path)

    assert dataset.aliases == ()
    assert dataset.conflicting_aliases[0].sortable_name == "Pidherny, Rachel"
    assert dataset.conflicting_aliases[0].target_sortable_names == (
        "Brown, Rachel",
        "Mallett, Marla",
    )


def test_normalize_name_uses_one_lookup_form_for_display_and_sort_names() -> None:
    assert normalize_name("Mallett, Marla") == "marla mallett"
    assert normalize_name("Marla Mallett") == "marla mallett"
