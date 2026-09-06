# Import pipeline

The importer loads source files from `src/data/players` in a local Curling
Canada archive checkout. It imports source player stints, while deliberately
ignoring the archive's precomputed career `totals` and yearly `team: Totals`
rows. CurlChat derives both yearly and career totals in SQL.

Archive `aka` files are redirects. Their names are loaded as aliases for the
canonical target player, and no duplicate statistics are created.

If the same `aka` source name points to multiple canonical targets, the
importer skips that alias and logs a warning. Canonical players and yearly
statistics continue importing.

Run the idempotent import from the `backend` directory:

```bash
uv run python -m curlchat.ingest.cli --source /path/to/curling-canada-stats-archive
```
