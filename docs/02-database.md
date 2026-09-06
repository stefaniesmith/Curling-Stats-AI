# 02 - Database

## Overview

CurlChat stores its analytics data in PostgreSQL. The database is designed to support fast analytical queries, AI-assisted SQL generation, and future extensibility while remaining easy to understand and maintain.

The schema intentionally models the application's domain rather than mirroring the structure of the Curling Canada Stats Archive. Source data is normalized during import into a small set of well-defined relational tables that represent players, events, and player statistics.

Database schema evolution is managed through SQLAlchemy and Alembic, with PostgreSQL serving as the authoritative source for both the data and its metadata.

---

## Design Principles

The database schema follows several guiding principles:

* Normalize entities such as players and events.
* Store one canonical record for each player.
* Preserve historical names through aliases.
* Store yearly statistics rather than derived aggregates.
* Prefer descriptive table and column names over abbreviations.
* Optimize the schema for both human developers and AI-generated SQL.

These principles help keep the schema simple while providing enough flexibility for future enhancements.

---

## Schema Overview

The analytics database consists of four primary tables.

| Table                     | Purpose                                            |
| ------------------------- | -------------------------------------------------- |
| `players`                 | Canonical player records.                          |
| `player_aliases`          | Alternate names that resolve to canonical players. |
| `events`                  | Supported Curling Canada competitions.             |
| `player_event_statistics` | One row per player stint within an event year.     |

Conversation history and LangGraph persistence are stored separately and are not considered part of the analytics schema.

The application-state tables are:

| Table | Purpose |
| --- | --- |
| `conversations` | Application metadata: one ID, title, and timestamps per conversation. |
| `checkpoint_migrations`, `checkpoints`, `checkpoint_blobs`, `checkpoint_writes` | LangGraph-managed persisted graph state and message history. |

`conversations` deliberately does not contain messages. The shared UUID is the
application conversation ID and the LangGraph `thread_id`, preventing duplicate
message storage. The pinned LangGraph checkpointer package owns the checkpoint
table format; its current tables are created by the conversation migration and
excluded from SQLAlchemy/Alembic autogeneration.

---

## Table Descriptions

### players

Stores one canonical record for every player.

Each player appears only once regardless of how many events or historical names exist in the source archive.

Typical information includes:

* display name
* sortable name
* normalized name
* original source slug

Other tables reference players using the primary key.

---

### player_aliases

Stores alternate names for canonical players.

This includes historical names, maiden names, spelling variations, and other aliases found within the source archive.

Separating aliases from canonical player records provides several benefits:

* every player has a single identity
* statistics are never duplicated
* player resolution remains deterministic
* additional aliases can be added without modifying statistics

The Player Resolver service searches this table before SQL generation so the SQL agent never needs to reason about aliases.

---

### events

Represents the competitions supported by the application.

Events are canonical families derived from each source document's totals metadata.
Examples include:

* Hearts
* Brier
* Canadian Women's
* Canada Cup (Men)
* Canada Cup (Women)
* Trials (Men)
* Trials (Women)

Each event also stores metadata describing the competition, such as the years covered by the archive and whether shot statistics are available.

Historical labels in yearly rows, such as Diamond D and CLCA, map to their
document's canonical event family rather than becoming standalone events.

---

### player_event_statistics

Stores one row per player, event, event year, team, and position.

This is the central analytics table used by nearly every query in the application.

Each row contains:

* player
* event
* event year
* team code
* position
* alternate designation
* games, wins, and losses
* inturn, outturn, draw, takeout, and all-shot quantities
* corresponding shot percentages

The combination of:

* player
* event
* event year
* team code
* position

is unique.

This table intentionally stores player stints rather than aggregate rows.
Yearly and career totals are calculated using SQL when required. The archive's
precomputed career totals and yearly `team: Totals` rows are not imported.

The imported names match the archive's player-record fields: `inturn_total`,
`outturn_total`, `draw_total`, `takeout_total`, and `shots_total`, each paired
with a percentage. The archive's precomputed career totals are deliberately
not stored; they are derived from player stints using total-weighted percentages.

---

## Relationships

The schema has a straightforward relational structure.

```text
players
    │
    ├──< player_aliases
    │
    └──< player_event_statistics >── events
```

This design keeps relationships simple while supporting a wide variety of analytical queries.

---

## Schema Conventions

### Primary Keys

All tables use surrogate integer primary keys.

---

### Foreign Keys

Relationships between tables are enforced through foreign key constraints.

---

### Unique Constraints

Unique constraints prevent duplicate logical records.

Examples include:

* one canonical player per normalized name
* one alias per player/name combination
* one statistics record per player, event, event year, team code, and position

---

### Null Values

Null values represent data that does not exist rather than default values.

For example, early historical events may not contain shot statistics because the source archive does not provide them.

---

### Naming

The schema intentionally favors descriptive names over abbreviations.

Examples include:

* `player_event_statistics`
* `event_year`
* `draw_percent`
* `takeout_percent`

This improves readability and makes SQL generation more reliable.

---

## SQLAlchemy

SQLAlchemy provides the application's object-relational mapping (ORM).

Each database table has a corresponding SQLAlchemy model that defines:

* columns
* relationships
* constraints
* PostgreSQL comments

Application services interact with SQLAlchemy models rather than writing raw SQL directly.

---

## Alembic

Alembic manages all schema evolution.

Every structural database change is implemented through an Alembic migration, providing:

* repeatable deployments
* versioned schema history
* reproducible development environments

The database schema should never be modified manually.

---

## PostgreSQL Comments

Every table and column should include descriptive PostgreSQL comments.

These comments serve multiple purposes:

* database documentation
* developer reference
* AI schema generation

Rather than maintaining a separate description of the schema for the SQL agent, CurlChat generates agent-facing schema documentation directly from PostgreSQL metadata.

This ensures that database documentation and AI context remain synchronized.

---

## SQL Agent Access

The SQL generation agent operates against a restricted subset of the schema.

The agent is expected to query only the analytics tables:

* `players`
* `events`
* `player_event_statistics`

Player aliases are resolved before SQL generation, so the agent never queries `player_aliases`.

Conversation history, LangGraph persistence, and other application tables are not exposed to the SQL agent.

## Runtime Database Roles

`curlchat_owner` owns all tables and runs Alembic migrations. The backend uses
two least-privilege runtime roles provisioned after migration:

* `curlchat_app` has `SELECT` only on analytics tables. The Player Resolver
  uses its alias access internally; the Analytics Query Tool's validator still
  excludes `player_aliases` from generated SQL.
* `curlchat_state` has `SELECT`, `INSERT`, `UPDATE`, and `DELETE` only on
  `conversations` and the LangGraph checkpoint tables.

The roles do not have access to one another's table set. This preserves the
read-only analytics defense-in-depth boundary while allowing conversation state
to persist.

---

## Summary

The CurlChat database is intentionally small, normalized, and optimized for analytical queries.

A clear separation between canonical players, aliases, events, and yearly statistics keeps the schema easy to understand while supporting flexible SQL generation, efficient reporting, and future expansion.
