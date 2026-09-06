"""Create/update the local least-privilege role used by the application runtime."""

from curlchat.db.roles import provision_application_role
from curlchat.db.session import admin_engine, get_settings


def main() -> None:
    settings = get_settings()
    with admin_engine.begin() as connection:
        role = provision_application_role(connection, settings.database_url)
    print(
        f"Provisioned read-only runtime role {role.username!r} "
        f"for database {role.database_name!r}."
    )


if __name__ == "__main__":
    main()
