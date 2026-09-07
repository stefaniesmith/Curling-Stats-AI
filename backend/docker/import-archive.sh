#!/bin/sh
set -eu

uv run --no-sync alembic upgrade head
uv run --no-sync python scripts/provision_app_role.py
exec uv run --no-sync python -m curlchat.ingest.cli --source /archive
