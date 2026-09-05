"""ORM models for Curling Canada's player statistics archive."""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from curlchat.db.session import Base


class Player(Base):
    """One canonical player record after archive ``aka`` redirects are resolved."""

    __tablename__ = "players"
    __table_args__ = (
        UniqueConstraint("normalized_name", name="uq_players_normalized_name"),
        {"comment": "Canonical player records from the Curling Canada statistics archive."},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, comment="Surrogate primary key.")
    display_name: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="Archive player name in display order."
    )
    sortable_name: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="Archive player name in surname-first sort order."
    )
    normalized_name: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="Normalized player name used for deterministic lookup."
    )
    source_slug: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="Source player-file slug when available."
    )

    aliases: Mapped[list[PlayerAlias]] = relationship(
        back_populates="player", cascade="all, delete-orphan"
    )
    event_statistics: Mapped[list[PlayerEventStatistics]] = relationship(back_populates="player")


class PlayerAlias(Base):
    """An archive ``aka`` source name that redirects to a canonical player."""

    __tablename__ = "player_aliases"
    __table_args__ = (
        UniqueConstraint(
            "player_id", "normalized_name", name="uq_player_aliases_player_normalized_name"
        ),
        Index("ix_player_aliases_normalized_name", "normalized_name"),
        {"comment": "Archive aka names that resolve to canonical player records."},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, comment="Surrogate primary key.")
    player_id: Mapped[int] = mapped_column(
        ForeignKey("players.id", ondelete="CASCADE"),
        nullable=False,
        comment="Canonical player targeted by the archive aka redirect.",
    )
    alias_name: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="Archive aka name in surname-first sort order."
    )
    normalized_name: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="Normalized archive aka name used for lookup."
    )

    player: Mapped[Player] = relationship(back_populates="aliases")


class Event(Base):
    """A supported competition in the Curling Canada archive."""

    __tablename__ = "events"
    __table_args__ = (
        UniqueConstraint("source_slug", name="uq_events_source_slug"),
        CheckConstraint(
            "first_event_year IS NULL OR last_event_year IS NULL OR first_event_year <= last_event_year",
            name="ck_events_year_range",
        ),
        {"comment": "Competitions represented in the Curling Canada statistics archive."},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, comment="Surrogate primary key.")
    display_name: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="Archive event name displayed to users."
    )
    source_slug: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="Stable source identifier for this archive event."
    )
    first_event_year: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="Earliest imported year for this event."
    )
    last_event_year: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="Latest imported year for this event."
    )
    has_shot_statistics: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="Whether imported records for this event include shot statistics.",
    )

    player_statistics: Mapped[list[PlayerEventStatistics]] = relationship(back_populates="event")


class PlayerEventStatistics(Base):
    """One archive player record for an event year; career totals are derived."""

    __tablename__ = "player_event_statistics"
    __table_args__ = (
        UniqueConstraint(
            "player_id",
            "event_id",
            "event_year",
            name="uq_player_event_statistics_player_event_year",
        ),
        CheckConstraint(
            "event_year BETWEEN 1800 AND 2500", name="ck_player_event_statistics_event_year"
        ),
        CheckConstraint("games IS NULL OR games >= 0", name="ck_player_event_statistics_games"),
        CheckConstraint("wins IS NULL OR wins >= 0", name="ck_player_event_statistics_wins"),
        CheckConstraint("losses IS NULL OR losses >= 0", name="ck_player_event_statistics_losses"),
        *(
            CheckConstraint(
                f"{name}_total IS NULL OR {name}_total >= 0",
                name=f"ck_player_event_statistics_{name}_total",
            )
            for name in ("inturn", "outturn", "draw", "takeout", "shots")
        ),
        *(
            CheckConstraint(
                f"{name}_percent IS NULL OR {name}_percent BETWEEN 0 AND 100",
                name=f"ck_player_event_statistics_{name}_percent",
            )
            for name in ("inturn", "outturn", "draw", "takeout", "shots")
        ),
        Index("ix_player_event_statistics_event_year", "event_id", "event_year"),
        {
            "comment": "Archive yearly player statistics; career totals are calculated from these rows."
        },
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, comment="Surrogate primary key.")
    player_id: Mapped[int] = mapped_column(
        ForeignKey("players.id"),
        nullable=False,
        comment="Player represented by this archive record.",
    )
    event_id: Mapped[int] = mapped_column(
        ForeignKey("events.id"), nullable=False, comment="Event represented by this archive record."
    )
    event_year: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, comment="Archive event year."
    )
    team: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="Archive team code for this event year."
    )
    position: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="Archive player position for this event year."
    )
    alternate: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True, comment="Whether the archive marks the player as an alternate."
    )
    games: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Archive games-played value."
    )
    wins: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="Archive wins value.")
    losses: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Archive losses value."
    )
    inturn_total: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Archive inturn quantity."
    )
    inturn_percent: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="Archive inturn percentage."
    )
    outturn_total: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Archive outturn quantity."
    )
    outturn_percent: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="Archive outturn percentage."
    )
    draw_total: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Archive draw quantity."
    )
    draw_percent: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="Archive draw percentage."
    )
    takeout_total: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Archive takeout quantity."
    )
    takeout_percent: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="Archive takeout percentage."
    )
    shots_total: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Archive all-shots quantity."
    )
    shots_percent: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="Archive all-shots percentage."
    )

    player: Mapped[Player] = relationship(back_populates="event_statistics")
    event: Mapped[Event] = relationship(back_populates="player_statistics")
