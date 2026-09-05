"""ORM models for the read-oriented Curling Canada analytics schema."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from curlchat.db.session import Base


class Player(Base):
    """A canonical athlete identity from the Curling Canada archive."""

    __tablename__ = "players"
    __table_args__ = (
        UniqueConstraint("normalized_name", name="uq_players_normalized_name"),
        {"comment": "Canonical Curling Canada player identities."},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, comment="Surrogate primary key.")
    display_name: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="Player name displayed to users."
    )
    sortable_name: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="Player name formatted for deterministic sorting."
    )
    normalized_name: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="Normalized canonical name used for identity matching."
    )
    source_slug: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Original player slug from the source archive, when available.",
    )

    aliases: Mapped[list[PlayerAlias]] = relationship(
        back_populates="player", cascade="all, delete-orphan"
    )
    event_statistics: Mapped[list[PlayerEventStatistics]] = relationship(back_populates="player")


class PlayerAlias(Base):
    """A historical or alternate name belonging to one canonical player."""

    __tablename__ = "player_aliases"
    __table_args__ = (
        UniqueConstraint(
            "player_id", "normalized_name", name="uq_player_aliases_player_normalized_name"
        ),
        Index("ix_player_aliases_normalized_name", "normalized_name"),
        {"comment": "Historical and alternate names that resolve to canonical players."},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, comment="Surrogate primary key.")
    player_id: Mapped[int] = mapped_column(
        ForeignKey("players.id", ondelete="CASCADE"),
        nullable=False,
        comment="Canonical player represented by this alias.",
    )
    alias_name: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="Alias exactly as found in the archive."
    )
    normalized_name: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="Normalized alias used for deterministic lookup."
    )

    player: Mapped[Player] = relationship(back_populates="aliases")


class Event(Base):
    """A supported Curling Canada competition archive collection."""

    __tablename__ = "events"
    __table_args__ = (
        UniqueConstraint("source_slug", name="uq_events_source_slug"),
        CheckConstraint(
            "first_event_year IS NULL OR last_event_year IS NULL OR first_event_year <= last_event_year",
            name="ck_events_year_range",
        ),
        {"comment": "Supported Curling Canada competition archive collections."},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, comment="Surrogate primary key.")
    display_name: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="Competition name displayed to users."
    )
    source_slug: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="Unique event identifier from the source archive."
    )
    first_event_year: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="Earliest event year available in the source archive."
    )
    last_event_year: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="Latest event year available in the source archive."
    )
    has_shot_statistics: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="Whether this event provides shot statistics.",
    )

    player_statistics: Mapped[list[PlayerEventStatistics]] = relationship(back_populates="event")


class PlayerEventStatistics(Base):
    """One player's yearly performance in one supported event."""

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
        CheckConstraint(
            "games_played IS NULL OR games_played >= 0",
            name="ck_player_event_statistics_games_played",
        ),
        CheckConstraint("wins IS NULL OR wins >= 0", name="ck_player_event_statistics_wins"),
        CheckConstraint("losses IS NULL OR losses >= 0", name="ck_player_event_statistics_losses"),
        CheckConstraint(
            "draw_made IS NULL OR draw_made >= 0", name="ck_player_event_statistics_draw_made"
        ),
        CheckConstraint(
            "draw_attempted IS NULL OR draw_attempted >= 0",
            name="ck_player_event_statistics_draw_attempted",
        ),
        CheckConstraint(
            "takeout_made IS NULL OR takeout_made >= 0",
            name="ck_player_event_statistics_takeout_made",
        ),
        CheckConstraint(
            "takeout_attempted IS NULL OR takeout_attempted >= 0",
            name="ck_player_event_statistics_takeout_attempted",
        ),
        CheckConstraint(
            "total_made IS NULL OR total_made >= 0", name="ck_player_event_statistics_total_made"
        ),
        CheckConstraint(
            "total_attempted IS NULL OR total_attempted >= 0",
            name="ck_player_event_statistics_total_attempted",
        ),
        CheckConstraint(
            "draw_percent IS NULL OR draw_percent BETWEEN 0 AND 100",
            name="ck_player_event_statistics_draw_percent",
        ),
        CheckConstraint(
            "takeout_percent IS NULL OR takeout_percent BETWEEN 0 AND 100",
            name="ck_player_event_statistics_takeout_percent",
        ),
        CheckConstraint(
            "total_percent IS NULL OR total_percent BETWEEN 0 AND 100",
            name="ck_player_event_statistics_total_percent",
        ),
        Index("ix_player_event_statistics_event_year", "event_id", "event_year"),
        {"comment": "Yearly player performance records for supported Curling Canada events."},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, comment="Surrogate primary key.")
    player_id: Mapped[int] = mapped_column(
        ForeignKey("players.id"), nullable=False, comment="Player whose performance is recorded."
    )
    event_id: Mapped[int] = mapped_column(
        ForeignKey("events.id"),
        nullable=False,
        comment="Competition in which the performance occurred.",
    )
    event_year: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, comment="Year of the competition."
    )
    team_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="Team name shown in the archive for this event year."
    )
    province: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="Province or territory represented in this event year."
    )
    position: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="Curling position played in this event year."
    )
    games_played: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Number of games played."
    )
    wins: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="Number of games won.")
    losses: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Number of games lost."
    )
    draw_made: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Successful draw shots."
    )
    draw_attempted: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Attempted draw shots."
    )
    draw_percent: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True, comment="Draw-shot percentage from 0 through 100."
    )
    takeout_made: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Successful takeout shots."
    )
    takeout_attempted: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Attempted takeout shots."
    )
    takeout_percent: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True, comment="Takeout-shot percentage from 0 through 100."
    )
    total_made: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Successful shots of all types."
    )
    total_attempted: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Attempted shots of all types."
    )
    total_percent: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True, comment="Overall shot percentage from 0 through 100."
    )

    player: Mapped[Player] = relationship(back_populates="event_statistics")
    event: Mapped[Event] = relationship(back_populates="player_statistics")
