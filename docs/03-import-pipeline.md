# 03 - Import Pipeline

## Overview

CurlChat imports the Curling Canada Stats Archive into PostgreSQL so that player
statistics can be queried consistently and efficiently. The importer is a
deterministic, repeatable transformation from the archive's Jekyll Markdown
files to CurlChat's analytics tables.

The application does not query the Markdown files at chat time. Parsing source
files for every question would make joins, rankings, aggregations, and player
identity resolution unnecessarily difficult. PostgreSQL is instead the
application's analytical source of truth after a successful import.

The importer is intentionally separate from the runtime application. It uses
the owner connection to write data; the running application uses a read-only
connection to query it.

---

## Source Data

The archive stores player records beneath:

```text
src/data/players/<event-collection>/<player-slug>.md
```

Each event collection, such as `hearts`, `brier`, or an Olympic Trials
collection, contains one Markdown file for a player. The file's YAML front
matter contains player metadata and a `years` list of yearly records. Typical
source fields include:

* `name` and `name-sort`
* an optional `aka` redirect
* a `years` list containing event, year, team, position, win/loss, and shot
  statistics
* a source-provided career `totals` block

The importer reads only the YAML front matter. Markdown body content is not an
analytics input.

---

## Import Workflow

```text
Markdown Files
        ↓
Parse YAML Front Matter
        ↓
Resolve Canonical Players and Aliases
        ↓
Normalize Events
        ↓
Extract Yearly Player Stints
        ↓
Load PostgreSQL
```

The command accepts the root of a local archive checkout:

```bash
uv run python -m curlchat.ingest.cli --source /path/to/curling-canada-stats-archive
```

The command runs the import in one database transaction. A validation failure
therefore prevents a partial import from being committed.

For a fresh local database, apply the schema migration and provision the
read-only application role before importing:

```bash
uv run alembic upgrade head
uv run python scripts/provision_app_role.py
uv run python -m curlchat.ingest.cli --source /path/to/curling-canada-stats-archive
```

---

## Player Import

### Canonical players

A file without `aka` is a canonical player source record. The importer creates
or updates one `players` record using:

* the display name from `name`
* the surname-first archive name from `name-sort`
* the source filename stem as `source_slug`
* a normalized name for deterministic lookup

Name normalization makes display-order and surname-first names comparable and
also ignores case, punctuation, spacing, and diacritics. This avoids duplicate
canonical records caused only by formatting differences in the source.

Canonical source records with the same archive `name-sort` are merged. Exact
duplicate player stints collapse to one source record; conflicting records for
the same player stint stop the import so the source issue can be investigated.

### Historical aliases

An `aka` file is an archive redirect, not a second player with independent
statistics. The importer resolves it to its canonical target and stores its
surname-first source name in `player_aliases`. This supports historical names,
maiden names, and spelling changes—for example, Suzanne Gaudet resolving to
Suzanne Birt—without duplicating statistics.

Every `aka` target must exist as a canonical source player. If one source alias
points to more than one canonical target, the importer skips just that alias,
logs a warning, and continues importing canonical players and statistics. It
does not guess which identity is correct.

---

## Event Import

Each canonical player document contains exactly one `totals[].event` value.
The importer uses that event name as the canonical event family for every
yearly record in that document. For example, a document whose career totals
name `Canadian Women's` maps its historical `Diamond D` and `CLCA` yearly rows
to the `Canadian Women's` event. The yearly source event value is validated but
is not stored as a separate event identity.

The importer derives a stable event slug from this canonical event name and
upserts the corresponding `events` record. It also derives the first and last
available years and whether any imported record contains all-shot quantities.

---

## Statistics Import

Each source yearly record becomes a `player_event_statistics` row at this
grain:

```text
one player + one event + one event year + one team code + one position
```

This is a player stint, not an annual aggregate. A player may legitimately
have more than one stint in the same event year when the archive reports more
than one team or position. The importer preserves those source records as-is.

For every stint, it loads the source team, position, alternate designation,
games, wins, losses, and the available inturn, outturn, draw, takeout, and
all-shot quantities and percentages. Missing historical shot statistics stay
`NULL`; they are not converted to zero or estimated.

---

## Data Normalization Decisions

### Totals are not imported

The archive publishes precomputed career totals and may include yearly rows
whose team is `Totals`. CurlChat intentionally skips both numeric aggregates.
It uses only the `event` name from a career totals block as source metadata for
the canonical yearly event family.

Aggregates are derived dynamically from imported player stints using SQL. This
keeps one source of truth for yearly and career calculations, avoids storing
redundant summary rows, and allows filters such as event, year, team, or
position to be applied consistently.

### Source records are preserved

The importer normalizes identity and table structure, but it does not correct
historical source statistics. A source record that places a player on multiple
teams in one year is imported as separate stints when it satisfies the table
grain. The application can therefore report what the archive contains without
embedding unsupported corrections in the data pipeline.

---

## Idempotency and Validation

The importer may be run repeatedly against the same archive checkout. It
upserts:

* players by normalized identity
* events by stable source slug
* aliases by canonical player and normalized alias name
* statistics by player, event, year, team code, and position

On a repeat run, existing records are refreshed rather than duplicated.

Before data is loaded, the importer validates the archive shape and required
fields. It rejects missing player directories, malformed front matter,
non-mapping YAML, missing names, invalid yearly values, unresolved `aka`
targets, and conflicting records with the same stint identity. It reports
ambiguous aliases as warnings and omits only those alias records.

The command prints a summary of imported source files, players, aliases,
events, yearly records, and skipped conflicting aliases.

---

## Summary

The import pipeline turns the archive's distributed Jekyll player records into
a normalized PostgreSQL dataset designed for analysis. Canonical player
identities, historical aliases, canonical event families, and source-level
player stints become reliable relational data while archive totals remain
derived at query time. PostgreSQL is therefore the single analytical source of
truth for CurlChat.
