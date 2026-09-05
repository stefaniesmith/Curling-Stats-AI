"""Create the initial archive-faithful CurlChat analytics schema.

Revision ID: 0001_initial_analytics_schema
Revises:
Create Date: 2026-09-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial_analytics_schema"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def _statistic_columns() -> list[sa.Column[object]]:
    """Return the archive's five quantity/percentage statistic pairs."""
    columns: list[sa.Column[object]] = []
    for name, label in (
        ("inturn", "inturn"),
        ("outturn", "outturn"),
        ("draw", "draw"),
        ("takeout", "takeout"),
        ("shots", "all-shots"),
    ):
        columns.extend(
            (
                sa.Column(
                    f"{name}_total",
                    sa.Integer(),
                    nullable=True,
                    comment=f"Archive {label} quantity.",
                ),
                sa.Column(
                    f"{name}_percent",
                    sa.SmallInteger(),
                    nullable=True,
                    comment=f"Archive {label} percentage.",
                ),
            )
        )
    return columns


def _statistic_constraints() -> list[sa.CheckConstraint]:
    """Return validation checks for the archive's statistic pairs."""
    constraints: list[sa.CheckConstraint] = []
    for name in ("inturn", "outturn", "draw", "takeout", "shots"):
        constraints.extend(
            (
                sa.CheckConstraint(
                    f"{name}_total IS NULL OR {name}_total >= 0",
                    name=f"ck_player_event_statistics_{name}_total",
                ),
                sa.CheckConstraint(
                    f"{name}_percent IS NULL OR {name}_percent BETWEEN 0 AND 100",
                    name=f"ck_player_event_statistics_{name}_percent",
                ),
            )
        )
    return constraints


def upgrade() -> None:
    op.create_table(
        "players",
        sa.Column("id", sa.Integer(), primary_key=True, comment="Surrogate primary key."),
        sa.Column(
            "display_name",
            sa.String(length=255),
            nullable=False,
            comment="Archive player name in display order.",
        ),
        sa.Column(
            "sortable_name",
            sa.String(length=255),
            nullable=False,
            comment="Archive player name in surname-first sort order.",
        ),
        sa.Column(
            "normalized_name",
            sa.String(length=255),
            nullable=False,
            comment="Normalized player name used for deterministic lookup.",
        ),
        sa.Column(
            "source_slug",
            sa.String(length=255),
            nullable=True,
            comment="Source player-file slug when available.",
        ),
        sa.UniqueConstraint("normalized_name", name="uq_players_normalized_name"),
        comment="Canonical player records from the Curling Canada statistics archive.",
    )
    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), primary_key=True, comment="Surrogate primary key."),
        sa.Column(
            "display_name",
            sa.String(length=255),
            nullable=False,
            comment="Archive event name displayed to users.",
        ),
        sa.Column(
            "source_slug",
            sa.String(length=255),
            nullable=False,
            comment="Stable source identifier for this archive event.",
        ),
        sa.Column(
            "first_event_year",
            sa.SmallInteger(),
            nullable=True,
            comment="Earliest imported year for this event.",
        ),
        sa.Column(
            "last_event_year",
            sa.SmallInteger(),
            nullable=True,
            comment="Latest imported year for this event.",
        ),
        sa.Column(
            "has_shot_statistics",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="Whether imported records for this event include shot statistics.",
        ),
        sa.CheckConstraint(
            "first_event_year IS NULL OR last_event_year IS NULL OR first_event_year <= last_event_year",
            name="ck_events_year_range",
        ),
        sa.UniqueConstraint("source_slug", name="uq_events_source_slug"),
        comment="Competitions represented in the Curling Canada statistics archive.",
    )
    op.create_table(
        "player_aliases",
        sa.Column("id", sa.Integer(), primary_key=True, comment="Surrogate primary key."),
        sa.Column(
            "player_id",
            sa.Integer(),
            sa.ForeignKey("players.id", ondelete="CASCADE"),
            nullable=False,
            comment="Canonical player targeted by the archive aka redirect.",
        ),
        sa.Column(
            "alias_name",
            sa.String(length=255),
            nullable=False,
            comment="Archive aka name in surname-first sort order.",
        ),
        sa.Column(
            "normalized_name",
            sa.String(length=255),
            nullable=False,
            comment="Normalized archive aka name used for lookup.",
        ),
        sa.UniqueConstraint(
            "player_id", "normalized_name", name="uq_player_aliases_player_normalized_name"
        ),
        comment="Archive aka names that resolve to canonical player records.",
    )
    op.create_index("ix_player_aliases_normalized_name", "player_aliases", ["normalized_name"])
    op.create_table(
        "player_event_statistics",
        sa.Column("id", sa.Integer(), primary_key=True, comment="Surrogate primary key."),
        sa.Column(
            "player_id",
            sa.Integer(),
            sa.ForeignKey("players.id"),
            nullable=False,
            comment="Player represented by this archive record.",
        ),
        sa.Column(
            "event_id",
            sa.Integer(),
            sa.ForeignKey("events.id"),
            nullable=False,
            comment="Event represented by this archive record.",
        ),
        sa.Column("event_year", sa.SmallInteger(), nullable=False, comment="Archive event year."),
        sa.Column(
            "team",
            sa.String(length=100),
            nullable=True,
            comment="Archive team code for this event year.",
        ),
        sa.Column(
            "position",
            sa.String(length=50),
            nullable=True,
            comment="Archive player position for this event year.",
        ),
        sa.Column(
            "alternate",
            sa.Boolean(),
            nullable=True,
            comment="Whether the archive marks the player as an alternate.",
        ),
        sa.Column("games", sa.Integer(), nullable=True, comment="Archive games-played value."),
        sa.Column("wins", sa.Integer(), nullable=True, comment="Archive wins value."),
        sa.Column("losses", sa.Integer(), nullable=True, comment="Archive losses value."),
        *_statistic_columns(),
        sa.CheckConstraint(
            "event_year BETWEEN 1800 AND 2500", name="ck_player_event_statistics_event_year"
        ),
        sa.CheckConstraint("games IS NULL OR games >= 0", name="ck_player_event_statistics_games"),
        sa.CheckConstraint("wins IS NULL OR wins >= 0", name="ck_player_event_statistics_wins"),
        sa.CheckConstraint(
            "losses IS NULL OR losses >= 0", name="ck_player_event_statistics_losses"
        ),
        *_statistic_constraints(),
        sa.UniqueConstraint(
            "player_id",
            "event_id",
            "event_year",
            name="uq_player_event_statistics_player_event_year",
        ),
        comment="Archive yearly player statistics; career totals are calculated from these rows.",
    )
    op.create_index(
        "ix_player_event_statistics_event_year",
        "player_event_statistics",
        ["event_id", "event_year"],
    )


def downgrade() -> None:
    op.drop_index("ix_player_event_statistics_event_year", table_name="player_event_statistics")
    op.drop_table("player_event_statistics")
    op.drop_index("ix_player_aliases_normalized_name", table_name="player_aliases")
    op.drop_table("player_aliases")
    op.drop_table("events")
    op.drop_table("players")
