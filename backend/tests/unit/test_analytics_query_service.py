from pydantic import SecretStr
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from curlchat.db.models import Player
from curlchat.db.session import Base, Settings
from curlchat.repositories.analytics import AnalyticsRepository
from curlchat.services import analytics_query_service
from curlchat.services.analytics_query_service import (
    AnalyticsQueryService,
    GeneratedAnalyticsQuery,
    OpenAISqlGenerator,
    ResolvedPlayerIdentity,
    analytics_schema_description,
    sql_generation_prompt,
)
from curlchat.services.stats_service import AnalyticsQueryStatus, StatsService


class StaticGenerator:
    def __init__(self, result: GeneratedAnalyticsQuery) -> None:
        self.result = result
        self.calls: list[tuple[str, tuple[ResolvedPlayerIdentity, ...], tuple[int, ...]]] = []

    def generate(
        self,
        request: str,
        resolved_players: tuple[ResolvedPlayerIdentity, ...],
        event_ids: tuple[int, ...],
    ) -> GeneratedAnalyticsQuery:
        self.calls.append((request, resolved_players, event_ids))
        return self.result


def _service(generator: StaticGenerator) -> AnalyticsQueryService:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = Session(engine)
    session.add(
        Player(
            display_name="Brad Gushue",
            sortable_name="Gushue, Brad",
            normalized_name="brad gushue",
        )
    )
    session.commit()
    return AnalyticsQueryService(StatsService(AnalyticsRepository(session)), generator)


def test_generates_then_executes_a_query_with_resolved_player_identity() -> None:
    generator = StaticGenerator(
        GeneratedAnalyticsQuery(
            supported=True,
            sql="SELECT display_name FROM players WHERE id = :player_id",
            parameters={"player_id": 1},
        )
    )
    service = _service(generator)

    player = ResolvedPlayerIdentity(display_name="Brad Gushue", player_id=1)

    result = service.query("Show Brad Gushue", resolved_players=(player,))

    assert generator.calls == [("Show Brad Gushue", (player,), ())]
    assert result.status is AnalyticsQueryStatus.SUCCESS
    assert result.rows == ({"display_name": "Brad Gushue"},)


def test_preserves_each_resolved_player_name_and_id_for_comparisons() -> None:
    generator = StaticGenerator(GeneratedAnalyticsQuery(supported=False, reason="Not needed."))
    service = _service(generator)
    players = (
        ResolvedPlayerIdentity(display_name="Jennifer Jones", player_id=14),
        ResolvedPlayerIdentity(display_name="Rachel Homan", player_id=29),
    )

    service.query("Which years did Jennifer Jones have a better record?", resolved_players=players)

    assert generator.calls == [
        ("Which years did Jennifer Jones have a better record?", players, ())
    ]


def test_returns_unsupported_without_executing_sql() -> None:
    service = _service(
        StaticGenerator(GeneratedAnalyticsQuery(supported=False, reason="Province is unavailable."))
    )

    result = service.query("Show province")

    assert result.status is AnalyticsQueryStatus.UNSUPPORTED
    assert result.message == "Province is unavailable."


def test_returns_execution_failure_when_a_supported_result_has_no_sql() -> None:
    service = _service(StaticGenerator(GeneratedAnalyticsQuery(supported=True)))

    result = service.query("Show Brad Gushue")

    assert result.status is AnalyticsQueryStatus.EXECUTION_FAILURE
    assert result.message == "The analytics query could not be generated."


def test_sql_generation_context_is_derived_from_live_database_metadata() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    description = analytics_schema_description(engine)

    assert "players: id, display_name" in description
    assert "player_event_statistics: id, player_id, event_id, event_year" in description


def test_sql_generation_prompt_requires_named_bind_parameters() -> None:
    prompt = sql_generation_prompt("players: id")

    assert "SQLAlchemy-style named bound parameters" in prompt
    assert "positional placeholders such as `$1`" in prompt
    assert "display_name and player_id pair" in prompt


def test_sql_generator_uses_function_calling_structured_output(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeModel:
        def with_structured_output(self, schema: object, **kwargs: object) -> object:
            captured["schema"] = schema
            captured["structured_output"] = kwargs
            return object()

    def fake_chat_model(**kwargs: object) -> FakeModel:
        captured["model"] = kwargs
        return FakeModel()

    monkeypatch.setattr(analytics_query_service, "ChatOpenAI", fake_chat_model)

    OpenAISqlGenerator(Settings(openai_api_key=SecretStr("test-key")), "test schema")

    assert captured["structured_output"] == {"method": "function_calling"}
