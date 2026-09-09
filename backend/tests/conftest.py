"""Shared test configuration and lightweight test infrastructure."""

import os

os.environ["PHOENIX_TRACING_ENABLED"] = "false"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

import curlchat.db.models  # noqa: F401
from curlchat.db.session import Base
from curlchat.main import app


@pytest.fixture
def sqlite_engine() -> Engine:
    """Provide a fresh schema for tests that exercise repositories or services."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def sqlite_session(sqlite_engine: Engine) -> Session:
    """Provide a short-lived session backed by the fresh SQLite schema."""
    with Session(sqlite_engine) as session:
        yield session


@pytest.fixture
def api_client() -> TestClient:
    """Create a client per test so application lifespan state cannot leak."""
    with TestClient(app) as client:
        yield client
