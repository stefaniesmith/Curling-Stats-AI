# Import pipeline

The first implementation milestone is loading the Curling Canada archive into PostgreSQL.

Planned import stages:

1. raw archive extraction
2. normalization into canonical players, aliases, events, and yearly statistics
3. upsert/load into analytics tables
4. verification queries and tests
