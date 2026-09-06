"""Deterministic importer for Curling Canada's player statistics archive."""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from curlchat.core.names import normalize_name
from curlchat.db.models import Event, Player, PlayerAlias, PlayerEventStatistics

STATISTIC_FIELDS = (
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
)

logger = logging.getLogger(__name__)


class ArchiveImportError(ValueError):
    """Raised when archive source data cannot be mapped deterministically."""


@dataclass(frozen=True)
class ArchiveYear:
    """A source yearly record after YAML key normalization."""

    event: str
    year: int
    values: dict[str, object | None]


@dataclass(frozen=True)
class ArchivePlayer:
    """A canonical source player and their yearly archive records."""

    display_name: str
    sortable_name: str
    source_slug: str
    years: tuple[ArchiveYear, ...]


@dataclass(frozen=True)
class ArchiveAlias:
    """An archive ``aka`` record pointing at a canonical sortable name."""

    sortable_name: str
    target_sortable_name: str


@dataclass(frozen=True)
class ConflictingArchiveAlias:
    """An alias name that points to more than one archive target."""

    sortable_name: str
    target_sortable_names: tuple[str, ...]


@dataclass(frozen=True)
class ArchiveDataset:
    """Parsed canonical players and redirects from an archive checkout."""

    players: tuple[ArchivePlayer, ...]
    aliases: tuple[ArchiveAlias, ...]
    conflicting_aliases: tuple[ConflictingArchiveAlias, ...]
    source_file_count: int


@dataclass(frozen=True)
class ImportReport:
    """Counts written by one idempotent archive import."""

    source_files: int
    players: int
    aliases: int
    events: int
    yearly_statistics: int
    skipped_aliases: int


def event_slug(event_name: str) -> str:
    """Create a stable event key from the archive event name."""
    return "-".join(normalize_name(event_name).split())


def load_archive(source_root: Path) -> ArchiveDataset:
    """Load canonical player files and ``aka`` redirects from an archive checkout.

    The numeric values in career ``totals`` blocks and yearly ``team: Totals``
    rows are intentionally ignored. The one event name in each career totals
    block canonically identifies that document's yearly source records.
    """
    player_root = source_root / "src" / "data" / "players"
    if not player_root.is_dir():
        raise ArchiveImportError(f"Archive player directory does not exist: {player_root}")

    canonical_documents: dict[str, list[tuple[dict[str, Any], Path]]] = defaultdict(list)
    alias_targets: dict[str, set[str]] = defaultdict(set)
    source_files = sorted(player_root.glob("*/*.md"))
    if not source_files:
        raise ArchiveImportError(f"No player files found under {player_root}")

    for path in source_files:
        document = _load_document(path)
        sortable_name = _required_string(document, "name-sort", path)
        aka_target = document.get("aka")
        if aka_target is not None:
            target_name = _required_string(document, "aka", path)
            alias_targets[sortable_name].add(target_name)
            continue
        canonical_documents[sortable_name].append((document, path))

    players = tuple(
        _merge_player_documents(sortable_name, documents)
        for sortable_name, documents in sorted(canonical_documents.items())
    )
    canonical_names = {player.sortable_name for player in players}
    unresolved_aliases = sorted(
        {target for targets in alias_targets.values() for target in targets} - canonical_names
    )
    if unresolved_aliases:
        rendered = ", ".join(repr(name) for name in unresolved_aliases)
        raise ArchiveImportError(f"Archive aka targets without a canonical player: {rendered}")

    aliases: list[ArchiveAlias] = []
    conflicting_aliases: list[ConflictingArchiveAlias] = []
    for alias_name, targets in sorted(alias_targets.items()):
        if len(targets) == 1:
            aliases.append(ArchiveAlias(alias_name, next(iter(targets))))
        else:
            conflicting_aliases.append(ConflictingArchiveAlias(alias_name, tuple(sorted(targets))))

    return ArchiveDataset(
        players=players,
        aliases=tuple(aliases),
        conflicting_aliases=tuple(conflicting_aliases),
        source_file_count=len(source_files),
    )


def import_archive(session: Session, source_root: Path) -> ImportReport:
    """Idempotently upsert one archive checkout into the analytics schema."""
    dataset = load_archive(source_root)
    players_by_sortable_name = _upsert_players(session, dataset.players)
    events_by_name = _upsert_events(session, dataset.players)
    _upsert_aliases(session, dataset.aliases, players_by_sortable_name)
    statistics_count = _upsert_statistics(
        session, dataset.players, players_by_sortable_name, events_by_name
    )
    session.flush()
    for conflict in dataset.conflicting_aliases:
        logger.warning(
            "Skipping conflicting archive aka redirect %r with targets: %s",
            conflict.sortable_name,
            ", ".join(conflict.target_sortable_names),
        )
    return ImportReport(
        source_files=dataset.source_file_count,
        players=len({player.id for player in players_by_sortable_name.values()}),
        aliases=len(dataset.aliases),
        events=len(events_by_name),
        yearly_statistics=statistics_count,
        skipped_aliases=len(dataset.conflicting_aliases),
    )


def _load_document(path: Path) -> dict[str, Any]:
    source = path.read_text(encoding="utf-8")
    front_matter = re.match(
        r"\A---[ \t]*\r?\n(.*?)(?:^---[ \t]*$)", source, re.DOTALL | re.MULTILINE
    )
    if front_matter is None:
        raise ArchiveImportError(f"Expected Jekyll front matter in {path}")
    try:
        document = yaml.safe_load(front_matter.group(1))
    except yaml.YAMLError as error:
        raise ArchiveImportError(f"Invalid YAML front matter in {path}") from error
    if not isinstance(document, dict):
        raise ArchiveImportError(f"Expected a YAML mapping in {path}")
    return document


def _merge_player_documents(
    sortable_name: str, documents: list[tuple[dict[str, Any], Path]]
) -> ArchivePlayer:
    first_document, first_path = documents[0]
    display_name = _required_string(first_document, "name", first_path)
    years_by_identity: dict[tuple[str, int, str, str], ArchiveYear] = {}
    for document, path in documents:
        if _required_string(document, "name", path) != display_name:
            raise ArchiveImportError(f"Conflicting display names for {sortable_name!r}")
        canonical_event = _canonical_event_name(document, path)
        for year in _parse_years(document, path, canonical_event):
            identity = (
                year.event,
                year.year,
                str(year.values["team"]),
                str(year.values["position"]),
            )
            previous = years_by_identity.setdefault(identity, year)
            if previous != year:
                raise ArchiveImportError(
                    f"Conflicting player stints for {sortable_name!r}, {year.event!r}, {year.year}"
                )
    return ArchivePlayer(
        display_name=display_name,
        sortable_name=sortable_name,
        source_slug=first_path.stem,
        years=tuple(years_by_identity[key] for key in sorted(years_by_identity)),
    )


def _canonical_event_name(document: dict[str, Any], path: Path) -> str:
    """Read the document's one canonical event name without using its aggregates."""
    totals = document.get("totals")
    if not isinstance(totals, list) or len(totals) != 1 or not isinstance(totals[0], dict):
        raise ArchiveImportError(f"Expected exactly one totals mapping in {path}")
    return _required_string(totals[0], "event", path)


def _parse_years(
    document: dict[str, Any], path: Path, canonical_event: str
) -> tuple[ArchiveYear, ...]:
    raw_years = document.get("years", [])
    if not isinstance(raw_years, list):
        raise ArchiveImportError(f"Expected a years list in {path}")
    parsed: list[ArchiveYear] = []
    for raw_year in raw_years:
        if not isinstance(raw_year, dict):
            raise ArchiveImportError(f"Expected a yearly mapping in {path}")
        _required_string(raw_year, "event", path)
        year = raw_year.get("year")
        if not isinstance(year, int):
            raise ArchiveImportError(f"Expected an integer year in {path}")
        team = _required_string(raw_year, "team", path)
        if team == "Totals":
            continue
        values: dict[str, object | None] = {
            "team": team,
            "position": _required_string(raw_year, "position", path),
            "alternate": _optional_bool(raw_year.get("alternate"), path),
            "games": _optional_int(raw_year.get("games"), path),
            "wins": _optional_int(raw_year.get("wins"), path),
            "losses": _optional_int(raw_year.get("losses"), path),
        }
        for field in STATISTIC_FIELDS:
            source_field = field.replace("_", "-")
            values[field] = _optional_int(raw_year.get(source_field), path)
        parsed.append(ArchiveYear(event=canonical_event, year=year, values=values))
    return tuple(parsed)


def _upsert_players(session: Session, players: tuple[ArchivePlayer, ...]) -> dict[str, Player]:
    players_by_sortable_name: dict[str, Player] = {}
    players_by_normalized_name = {
        player.normalized_name: player for player in session.scalars(select(Player))
    }
    for source_player in players:
        normalized = normalize_name(source_player.sortable_name)
        player = players_by_normalized_name.get(normalized)
        if player is None:
            player = Player(
                display_name=source_player.display_name,
                sortable_name=source_player.sortable_name,
                normalized_name=normalized,
                source_slug=source_player.source_slug,
            )
            session.add(player)
            players_by_normalized_name[normalized] = player
        elif player.sortable_name == source_player.sortable_name:
            player.display_name = source_player.display_name
            player.sortable_name = source_player.sortable_name
            player.source_slug = source_player.source_slug
        players_by_sortable_name[source_player.sortable_name] = player
    session.flush()
    return players_by_sortable_name


def _upsert_events(session: Session, players: tuple[ArchivePlayer, ...]) -> dict[str, Event]:
    years_by_event: dict[str, list[ArchiveYear]] = defaultdict(list)
    for player in players:
        for year in player.years:
            years_by_event[year.event].append(year)

    events_by_name: dict[str, Event] = {}
    for event_name, years in years_by_event.items():
        slug = event_slug(event_name)
        event = session.scalar(select(Event).where(Event.source_slug == slug))
        if event is None:
            event = Event(display_name=event_name, source_slug=slug)
            session.add(event)
        event.display_name = event_name
        event.first_event_year = min(record.year for record in years)
        event.last_event_year = max(record.year for record in years)
        event.has_shot_statistics = any(
            record.values["shots_total"] is not None for record in years
        )
        events_by_name[event_name] = event
    session.flush()
    return events_by_name


def _upsert_aliases(
    session: Session, aliases: tuple[ArchiveAlias, ...], players_by_sortable_name: dict[str, Player]
) -> None:
    for source_alias in aliases:
        player = players_by_sortable_name[source_alias.target_sortable_name]
        normalized = normalize_name(source_alias.sortable_name)
        alias = session.scalar(
            select(PlayerAlias).where(
                PlayerAlias.player_id == player.id,
                PlayerAlias.normalized_name == normalized,
            )
        )
        if alias is None:
            session.add(
                PlayerAlias(
                    player_id=player.id,
                    alias_name=source_alias.sortable_name,
                    normalized_name=normalized,
                )
            )
        else:
            alias.alias_name = source_alias.sortable_name


def _upsert_statistics(
    session: Session,
    players: tuple[ArchivePlayer, ...],
    players_by_sortable_name: dict[str, Player],
    events_by_name: dict[str, Event],
) -> int:
    count = 0
    for source_player in players:
        player = players_by_sortable_name[source_player.sortable_name]
        for source_year in source_player.years:
            event = events_by_name[source_year.event]
            statistic = session.scalar(
                select(PlayerEventStatistics).where(
                    PlayerEventStatistics.player_id == player.id,
                    PlayerEventStatistics.event_id == event.id,
                    PlayerEventStatistics.event_year == source_year.year,
                    PlayerEventStatistics.team == source_year.values["team"],
                    PlayerEventStatistics.position == source_year.values["position"],
                )
            )
            if statistic is None:
                statistic = PlayerEventStatistics(
                    player_id=player.id,
                    event_id=event.id,
                    event_year=source_year.year,
                    team=str(source_year.values["team"]),
                    position=str(source_year.values["position"]),
                )
                session.add(statistic)
            for field, value in source_year.values.items():
                setattr(statistic, field, value)
            count += 1
    return count


def _required_string(document: dict[str, Any], key: str, path: Path) -> str:
    value = document.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ArchiveImportError(f"Expected a non-empty {key!r} string in {path}")
    return value.strip()


def _optional_string(value: object, path: Path) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ArchiveImportError(f"Expected an optional string in {path}")
    return value.strip() or None


def _optional_bool(value: object, path: Path) -> bool | None:
    if value is None or isinstance(value, bool):
        return value
    raise ArchiveImportError(f"Expected an optional boolean in {path}")


def _optional_int(value: object, path: Path) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ArchiveImportError(f"Expected an optional integer in {path}")
    return value
