"""Create/update local least-privilege runtime database roles."""

from curlchat.db.roles import provision_application_role, provision_state_role
from curlchat.db.session import admin_engine, get_settings


def main() -> None:
    settings = get_settings()
    with admin_engine.begin() as connection:
        analytics_role = provision_application_role(connection, settings.database_url)
        state_role = provision_state_role(connection, settings.state_database_url)
    print(f"Provisioned read-only analytics role {analytics_role.username!r}.")
    print(f"Provisioned conversation-state role {state_role.username!r}.")


if __name__ == "__main__":
    main()
