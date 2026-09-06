"""Provisioning for the least-privilege runtime database role."""

from __future__ import annotations

from dataclasses import dataclass

from psycopg import sql
from sqlalchemy import Connection
from sqlalchemy.engine import make_url

_ANALYTICS_TABLES = ("players", "player_aliases", "events", "player_event_statistics")


@dataclass(frozen=True)
class ApplicationRole:
    """Role details derived from the runtime database URL."""

    database_name: str
    username: str
    password: str


def application_role_from_url(database_url: str) -> ApplicationRole:
    """Extract required runtime role details from a SQLAlchemy database URL."""
    url = make_url(database_url)
    if not url.database or not url.username or url.password is None:
        raise ValueError("DATABASE_URL must contain a database name, username, and password.")
    return ApplicationRole(database_name=url.database, username=url.username, password=url.password)


def provision_application_role(connection: Connection, database_url: str) -> ApplicationRole:
    """Create or update a runtime role with read-only analytics access."""
    application_role = application_role_from_url(database_url)
    dbapi_connection = connection.connection.driver_connection
    with dbapi_connection.cursor() as cursor:
        cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (application_role.username,))
        if cursor.fetchone() is None:
            cursor.execute(
                sql.SQL(
                    "CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB "
                    "NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS"
                ).format(
                    sql.Identifier(application_role.username), sql.Literal(application_role.password)
                )
            )
        else:
            cursor.execute(
                sql.SQL(
                    "ALTER ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB "
                    "NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS"
                ).format(
                    sql.Identifier(application_role.username), sql.Literal(application_role.password)
                )
            )
        cursor.execute(
            sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                sql.Identifier(application_role.database_name), sql.Identifier(application_role.username)
            )
        )
        cursor.execute(
            sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(
                sql.Identifier(application_role.username)
            )
        )
        cursor.execute(
            sql.SQL("GRANT SELECT ON TABLE {} TO {}").format(
                sql.SQL(", ").join(
                    sql.SQL("public.{}").format(sql.Identifier(table)) for table in _ANALYTICS_TABLES
                ),
                sql.Identifier(application_role.username),
            )
        )
    return application_role
