import pytest

from curlchat.db.roles import application_role_from_url


def test_extracts_runtime_role_details_from_database_url() -> None:
    role = application_role_from_url(
        "postgresql+psycopg://curlchat_app:local_password@localhost:5432/curlchat"
    )

    assert role.database_name == "curlchat"
    assert role.username == "curlchat_app"
    assert role.password == "local_password"


def test_rejects_runtime_url_without_credentials() -> None:
    with pytest.raises(ValueError, match="username"):
        application_role_from_url("postgresql+psycopg://localhost:5432/curlchat")
