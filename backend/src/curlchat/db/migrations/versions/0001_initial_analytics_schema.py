"""Create the initial CurlChat analytics schema.

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


def upgrade() -> None:
    op.create_table(
        "players",
        sa.Column("id", sa.Integer(), primary_key=True, comment="Surrogate primary key."),
        sa.Column(
            "display_name",
            sa.String(length=255),
            nullable=False,
            comment="Player name displayed to users.",
        ),
        sa.Column(
            "sortable_name",
            sa.String(length=255),
            nullable=False,
            comment="Player name formatted for deterministic sorting.",
        ),
        sa.Column(
            "normalized_name",
            sa.String(length=255),
            nullable=False,
            comment="Normalized canonical name used for identity matching.",
        ),
        sa.Column(
            "source_slug",
            sa.String(length=255),
            nullable=True,
            comment="Original player slug from the source archive, when available.",
        ),
        sa.UniqueConstraint("normalized_name", name="uq_players_normalized_name"),
        comment="Canonical Curling Canada player identities.",
    )
    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), primary_key=True, comment="Surrogate primary key."),
        sa.Column(
            "display_name",
            sa.String(length=255),
            nullable=False,
            comment="Competition name displayed to users.",
        ),
        sa.Column(
            "source_slug",
            sa.String(length=255),
            nullable=False,
            comment="Unique event identifier from the source archive.",
        ),
        sa.Column(
            "first_event_year",
            sa.SmallInteger(),
            nullable=True,
            comment="Earliest event year available in the source archive.",
        ),
        sa.Column(
            "last_event_year",
            sa.SmallInteger(),
            nullable=True,
            comment="Latest event year available in the source archive.",
        ),
        sa.Column(
            "has_shot_statistics",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="Whether this event provides shot statistics.",
        ),
        sa.CheckConstraint(
            "first_event_year IS NULL OR last_event_year IS NULL OR first_event_year <= last_event_year",
            name="ck_events_year_range",
        ),
        sa.UniqueConstraint("source_slug", name="uq_events_source_slug"),
        comment="Supported Curling Canada competition archive collections.",
    )
    op.create_table(
        "player_aliases",
        sa.Column("id", sa.Integer(), primary_key=True, comment="Surrogate primary key."),
        sa.Column(
            "player_id",
            sa.Integer(),
            sa.ForeignKey("players.id", ondelete="CASCADE"),
            nullable=False,
            comment="Canonical player represented by this alias.",
        ),
        sa.Column(
            "alias_name",
            sa.String(length=255),
            nullable=False,
            comment="Alias exactly as found in the archive.",
        ),
        sa.Column(
            "normalized_name",
            sa.String(length=255),
            nullable=False,
            comment="Normalized alias used for deterministic lookup.",
        ),
        sa.UniqueConstraint(
            "player_id", "normalized_name", name="uq_player_aliases_player_normalized_name"
        ),
        comment="Historical and alternate names that resolve to canonical players.",
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
            comment="Player whose performance is recorded.",
        ),
        sa.Column(
            "event_id",
            sa.Integer(),
            sa.ForeignKey("events.id"),
            nullable=False,
            comment="Competition in which the performance occurred.",
        ),
        sa.Column(
            "event_year", sa.SmallInteger(), nullable=False, comment="Year of the competition."
        ),
        sa.Column(
            "team_name",
            sa.String(length=255),
            nullable=True,
            comment="Team name shown in the archive for this event year.",
        ),
        sa.Column(
            "province",
            sa.String(length=100),
            nullable=True,
            comment="Province or territory represented in this event year.",
        ),
        sa.Column(
            "position",
            sa.String(length=50),
            nullable=True,
            comment="Curling position played in this event year.",
        ),
        sa.Column("games_played", sa.Integer(), nullable=True, comment="Number of games played."),
        sa.Column("wins", sa.Integer(), nullable=True, comment="Number of games won."),
        sa.Column("losses", sa.Integer(), nullable=True, comment="Number of games lost."),
        sa.Column("draw_made", sa.Integer(), nullable=True, comment="Successful draw shots."),
        sa.Column("draw_attempted", sa.Integer(), nullable=True, comment="Attempted draw shots."),
        sa.Column(
            "draw_percent",
            sa.Numeric(precision=5, scale=2),
            nullable=True,
            comment="Draw-shot percentage from 0 through 100.",
        ),
        sa.Column("takeout_made", sa.Integer(), nullable=True, comment="Successful takeout shots."),
        sa.Column(
            "takeout_attempted", sa.Integer(), nullable=True, comment="Attempted takeout shots."
        ),
        sa.Column(
            "takeout_percent",
            sa.Numeric(precision=5, scale=2),
            nullable=True,
            comment="Takeout-shot percentage from 0 through 100.",
        ),
        sa.Column(
            "total_made", sa.Integer(), nullable=True, comment="Successful shots of all types."
        ),
        sa.Column(
            "total_attempted", sa.Integer(), nullable=True, comment="Attempted shots of all types."
        ),
        sa.Column(
            "total_percent",
            sa.Numeric(precision=5, scale=2),
            nullable=True,
            comment="Overall shot percentage from 0 through 100.",
        ),
        sa.CheckConstraint(
            "event_year BETWEEN 1800 AND 2500", name="ck_player_event_statistics_event_year"
        ),
        sa.CheckConstraint(
            "games_played IS NULL OR games_played >= 0",
            name="ck_player_event_statistics_games_played",
        ),
        sa.CheckConstraint("wins IS NULL OR wins >= 0", name="ck_player_event_statistics_wins"),
        sa.CheckConstraint(
            "losses IS NULL OR losses >= 0", name="ck_player_event_statistics_losses"
        ),
        sa.CheckConstraint(
            "draw_made IS NULL OR draw_made >= 0", name="ck_player_event_statistics_draw_made"
        ),
        sa.CheckConstraint(
            "draw_attempted IS NULL OR draw_attempted >= 0",
            name="ck_player_event_statistics_draw_attempted",
        ),
        sa.CheckConstraint(
            "takeout_made IS NULL OR takeout_made >= 0",
            name="ck_player_event_statistics_takeout_made",
        ),
        sa.CheckConstraint(
            "takeout_attempted IS NULL OR takeout_attempted >= 0",
            name="ck_player_event_statistics_takeout_attempted",
        ),
        sa.CheckConstraint(
            "total_made IS NULL OR total_made >= 0", name="ck_player_event_statistics_total_made"
        ),
        sa.CheckConstraint(
            "total_attempted IS NULL OR total_attempted >= 0",
            name="ck_player_event_statistics_total_attempted",
        ),
        sa.CheckConstraint(
            "draw_percent IS NULL OR draw_percent BETWEEN 0 AND 100",
            name="ck_player_event_statistics_draw_percent",
        ),
        sa.CheckConstraint(
            "takeout_percent IS NULL OR takeout_percent BETWEEN 0 AND 100",
            name="ck_player_event_statistics_takeout_percent",
        ),
        sa.CheckConstraint(
            "total_percent IS NULL OR total_percent BETWEEN 0 AND 100",
            name="ck_player_event_statistics_total_percent",
        ),
        sa.UniqueConstraint(
            "player_id",
            "event_id",
            "event_year",
            name="uq_player_event_statistics_player_event_year",
        ),
        comment="Yearly player performance records for supported Curling Canada events.",
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
