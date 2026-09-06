# Alembic migrations

This directory contains the Alembic environment and schema revisions.

Run migrations from the `backend` directory:

```bash
uv run alembic upgrade head
```

Alembic reads `ADMIN_DATABASE_URL` through `curlchat.db.session.Settings`. The initial
revision creates the four documented analytics tables and their PostgreSQL comments.
