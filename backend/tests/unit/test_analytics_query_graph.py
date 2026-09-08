from pydantic import SecretStr
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from curlchat.agent.graph import analytics_query_graph
from curlchat.agent.graph.analytics_query_graph import (
    AnalyticsQueryWorkflow,
    GeneratedAnalyticsQuery,
    OpenAISqlGenerator,
    RepairContext,
    SqlGenerator,
    analytics_schema_description,
    sql_generation_prompt,
)
from curlchat.core.identities import ResolvedEventIdentity, ResolvedPlayerIdentity
from curlchat.db.models import Player
from curlchat.db.session import Base, Settings
from curlchat.repositories.analytics import AnalyticsRepository
from curlchat.services.stats_service import AnalyticsQueryStatus, StatsService


class StaticGenerator:
    def __init__(self, result: GeneratedAnalyticsQuery) -> None:
        self.result = result
        self.calls: list[
            tuple[
                str,
                tuple[ResolvedPlayerIdentity, ...],
                tuple[ResolvedEventIdentity, ...],
                RepairContext | None,
            ]
        ] = []

    def generate(
        self,
        request: str,
        resolved_players: tuple[ResolvedPlayerIdentity, ...],
        resolved_events: tuple[ResolvedEventIdentity, ...],
        repair_context: RepairContext | None = None,
    ) -> GeneratedAnalyticsQuery:
        self.calls.append((request, resolved_players, resolved_events, repair_context))
        return self.result


class SequenceGenerator:
    def __init__(self, results: list[GeneratedAnalyticsQuery]) -> None:
        self._results = results
        self.calls: list[
            tuple[
                str,
                tuple[ResolvedPlayerIdentity, ...],
                tuple[ResolvedEventIdentity, ...],
                RepairContext | None,
            ]
        ] = []

    def generate(
        self,
        request: str,
        resolved_players: tuple[ResolvedPlayerIdentity, ...],
        resolved_events: tuple[ResolvedEventIdentity, ...],
        repair_context: RepairContext | None = None,
    ) -> GeneratedAnalyticsQuery:
        self.calls.append((request, resolved_players, resolved_events, repair_context))
        return self._results.pop(0)


def _workflow(generator: SqlGenerator) -> AnalyticsQueryWorkflow:
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
    return AnalyticsQueryWorkflow(StatsService(AnalyticsRepository(session)), generator)


def test_generates_then_executes_a_query_with_resolved_player_identity() -> None:
    generator = StaticGenerator(
        GeneratedAnalyticsQuery(
            supported=True,
            sql="SELECT display_name FROM players WHERE id = :player_id",
            parameters={"player_id": 1},
        )
    )
    workflow = _workflow(generator)

    player = ResolvedPlayerIdentity(display_name="Brad Gushue", player_id=1)

    result = workflow.query("Show Brad Gushue", resolved_players=(player,))

    assert generator.calls == [("Show Brad Gushue", (player,), (), None)]
    assert result.status is AnalyticsQueryStatus.SUCCESS
    assert result.rows == ({"display_name": "Brad Gushue"},)


def test_preserves_each_resolved_player_name_and_id_for_comparisons() -> None:
    generator = StaticGenerator(GeneratedAnalyticsQuery(supported=False, reason="Not needed."))
    workflow = _workflow(generator)
    players = (
        ResolvedPlayerIdentity(display_name="Jennifer Jones", player_id=14),
        ResolvedPlayerIdentity(display_name="Rachel Homan", player_id=29),
    )

    workflow.query("Which years did Jennifer Jones have a better record?", resolved_players=players)

    assert generator.calls == [
        ("Which years did Jennifer Jones have a better record?", players, (), None)
    ]


def test_preserves_each_resolved_event_name_and_id() -> None:
    generator = StaticGenerator(GeneratedAnalyticsQuery(supported=False, reason="Not needed."))
    workflow = _workflow(generator)
    event = ResolvedEventIdentity(display_name="Brier", event_id=2)

    workflow.query("Show Brier statistics", resolved_events=(event,))

    assert generator.calls == [("Show Brier statistics", (), (event,), None)]


def test_retries_once_after_execution_failure_with_query_and_database_context() -> None:
    generator = SequenceGenerator(
        [
            GeneratedAnalyticsQuery(
                supported=True,
                sql="SELECT missing_column FROM players WHERE id = :player_id",
                parameters={"player_id": 1},
            ),
            GeneratedAnalyticsQuery(
                supported=True,
                sql="SELECT display_name FROM players WHERE id = :player_id",
                parameters={"player_id": 1},
            ),
        ]
    )
    workflow = _workflow(generator)
    player = ResolvedPlayerIdentity(display_name="Brad Gushue", player_id=1)

    result = workflow.query("Show Brad Gushue", resolved_players=(player,))

    assert result.status is AnalyticsQueryStatus.SUCCESS
    assert result.rows == ({"display_name": "Brad Gushue"},)
    assert generator.calls[0] == ("Show Brad Gushue", (player,), (), None)
    assert generator.calls[1][:3] == ("Show Brad Gushue", (player,), ())
    assert generator.calls[1][3] == RepairContext(
        previous_sql="SELECT missing_column FROM players WHERE id = :player_id",
        previous_parameters={"player_id": 1},
        database_error="no such column: missing_column",
    )


def test_returns_execution_failure_after_one_unsuccessful_repair_attempt() -> None:
    generator = SequenceGenerator(
        [
            GeneratedAnalyticsQuery(
                supported=True,
                sql="SELECT missing_column FROM players",
            ),
            GeneratedAnalyticsQuery(
                supported=True,
                sql="SELECT still_missing FROM players",
            ),
        ]
    )
    workflow = _workflow(generator)

    result = workflow.query("Show player names")

    assert result.status is AnalyticsQueryStatus.EXECUTION_FAILURE
    assert result.message == "The analytics query could not be completed after a repair attempt."
    assert len(generator.calls) == 2


def test_returns_unsupported_without_executing_sql() -> None:
    workflow = _workflow(
        StaticGenerator(GeneratedAnalyticsQuery(supported=False, reason="Province is unavailable."))
    )

    result = workflow.query("Show province")

    assert result.status is AnalyticsQueryStatus.UNSUPPORTED
    assert result.message == "Province is unavailable."


def test_returns_execution_failure_when_a_supported_result_has_no_sql() -> None:
    workflow = _workflow(StaticGenerator(GeneratedAnalyticsQuery(supported=True)))

    result = workflow.query("Show Brad Gushue")

    assert result.status is AnalyticsQueryStatus.EXECUTION_FAILURE
    assert result.message == "The analytics query could not be generated."


def test_sql_generation_context_is_derived_from_live_database_metadata() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    description = analytics_schema_description(engine)

    assert "players\n- id: INTEGER; NOT NULL; PRIMARY KEY" in description
    assert "- display_name: VARCHAR(255); NOT NULL" in description
    assert "- player_id: INTEGER; NOT NULL; REFERENCES players.id" in description
    assert "- shots_percent: SMALLINT; NULL" in description
    assert "CHECK: shots_percent IS NULL OR shots_percent BETWEEN 0 AND 100" in description


def test_sql_generation_prompt_requires_named_bind_parameters() -> None:
    prompt = sql_generation_prompt("players: id")

    assert "SQLAlchemy-style named bound parameters" in prompt
    assert "positional placeholders such as `$1`" in prompt
    assert "authoritative `display_name`/ID pairs" in prompt
    assert "event ID identifies a competition across its imported history" in prompt
    assert "pes.event_year = :event_year" in prompt
    assert "Never omit, broaden, or silently reinterpret an explicit temporal constraint" in prompt.replace(
        "\n", " "
    )
    assert "Event Resolver intentionally ignores year tokens" in prompt
    assert "ORDER BY metric DESC NULLS LAST" in prompt
    assert "`NULL` means the archive does not provide that value" in prompt
    assert "alternate IS NOT TRUE" in prompt.replace("\n", " ")
    assert "position-specific comparisons" in prompt
    assert "one player stint" in prompt
    assert "combine eligible stints by player" in prompt
    assert "volume-weighted percentage" in prompt
    assert "unweighted average across stints" in prompt
    assert "SUM(metric_total * metric_percent)::numeric / NULLIF(SUM(metric_total), 0)" in prompt
    assert "SUM(draw_total * draw_percent)::numeric / NULLIF(SUM(draw_total), 0)" in prompt
    assert "Do not divide a total by itself" in prompt.replace("\n", " ")
    assert "`draw_percentage`, not `weighted_draw_percent`" in prompt
    assert "must not appear in result column names" in prompt.replace("\n", " ")
    assert "players: id" in prompt


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

    monkeypatch.setattr(analytics_query_graph, "ChatOpenAI", fake_chat_model)

    OpenAISqlGenerator(
        Settings(
            openai_api_key=SecretStr("test-key"),
            openai_model="test-model",
            openai_sql_max_completion_tokens=2000,
        ),
        "test schema",
    )

    assert captured["structured_output"] == {"method": "function_calling"}
    assert captured["model"] == {
        "model": "test-model",
        "api_key": "test-key",
        "temperature": 0,
        "max_completion_tokens": 2000,
    }


def test_sql_generator_adds_reasoning_effort_for_gpt_5_models(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeModel:
        def with_structured_output(self, schema: object, **kwargs: object) -> object:
            return object()

    monkeypatch.setattr(
        analytics_query_graph,
        "ChatOpenAI",
        lambda **kwargs: captured.update(kwargs) or FakeModel(),
    )

    OpenAISqlGenerator(
        Settings(
            openai_api_key=SecretStr("test-key"),
            openai_model="gpt-5-mini",
            openai_sql_reasoning_effort="minimal",
        ),
        "test schema",
    )

    assert captured["reasoning_effort"] == "minimal"
