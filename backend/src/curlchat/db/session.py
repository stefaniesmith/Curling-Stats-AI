from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://curlchat_app:curlchat_app@localhost:5432/curlchat"
    admin_database_url: str = "postgresql+psycopg://curlchat_owner:curlchat@localhost:5432/curlchat"
    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-4.1-mini"
    phoenix_tracing_enabled: bool = False
    phoenix_collector_endpoint: str = "http://localhost:6006/v1/traces"
    phoenix_project_name: str = "curlchat"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


class Base(DeclarativeBase):
    pass


@lru_cache
def get_settings() -> Settings:
    return Settings()


engine = create_engine(get_settings().database_url, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

admin_engine = create_engine(get_settings().admin_database_url, future=True)
AdminSessionLocal = sessionmaker(
    bind=admin_engine, autoflush=False, autocommit=False, expire_on_commit=False
)
