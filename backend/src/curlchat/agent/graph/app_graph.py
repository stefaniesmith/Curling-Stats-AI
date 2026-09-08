"""Initial LangGraph workflow for CurlChat analytics questions."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import nullcontext
from typing import Annotated, Any, Literal, TypedDict
from uuid import UUID

from langchain_openai import ChatOpenAI
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph.message import add_messages
from langgraph.managed import RemainingSteps
from langgraph.prebuilt import create_react_agent
from openai import OpenAIError
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.engine import make_url

from curlchat.agent.prompts.prompt_loader import main_agent_system_prompt
from curlchat.agent.tools.analytics_query import query_analytics
from curlchat.agent.tools.event_resolver import resolve_event
from curlchat.agent.tools.player_resolver import resolve_player
from curlchat.agent.tools.visualization import create_visualization
from curlchat.db.session import SessionLocal, Settings, get_settings
from curlchat.repositories.events import EventRepository
from curlchat.services.competition_catalog import CompetitionCatalog
from curlchat.services.visualization_service import VisualizationArtifact


class AgentConfigurationError(RuntimeError):
    """The application cannot invoke an LLM with its current configuration."""

class AgentInvocationError(RuntimeError):
    """The configured model provider could not complete an agent request."""


class LatestAnalyticsResult(TypedDict):
    """The serializable, typed data retained after a successful analytics query."""

    columns: tuple[str, ...]
    rows: tuple[dict[str, Any], ...]


class CurlChatAgentState(TypedDict):
    """Persisted conversation and the last successful typed analytics result."""

    messages: Annotated[list[Any], add_messages]
    remaining_steps: RemainingSteps
    latest_analytics_result: LatestAnalyticsResult | None


class AgentResponse(BaseModel):
    """Final text and renderable artifacts from one agent invocation."""

    message: str
    artifacts: tuple[VisualizationArtifact, ...] = Field(default_factory=tuple)


class AgentStreamEvent(BaseModel):
    """One renderable event emitted while a graph turn is in progress."""

    type: Literal["status", "markdown_delta", "artifact", "complete"]
    payload: dict[str, Any] = Field(default_factory=dict)


class ConversationHistoryMessage(BaseModel):
    """One frontend-safe message reconstructed from persisted LangGraph state."""

    role: Literal["user", "assistant"]
    content: str
    artifacts: tuple[VisualizationArtifact, ...] = Field(default_factory=tuple)


def competition_catalog_prompt() -> str:
    """Render imported competition coverage for the main-agent system prompt."""
    with SessionLocal() as session:
        return CompetitionCatalog(EventRepository(session)).render_prompt_table()


def build_graph(
    settings: Settings | None = None, checkpointer: BaseCheckpointSaver | None = None
) -> Any:
    """Build the tool-using graph without contacting the model provider."""
    configured_settings = settings or get_settings()
    if configured_settings.openai_api_key is None:
        raise AgentConfigurationError("OPENAI_API_KEY is not configured.")
    model = ChatOpenAI(
        model=configured_settings.openai_model,
        api_key=configured_settings.openai_api_key.get_secret_value(),
        temperature=0,
        max_completion_tokens=800,
    )
    system_prompt = main_agent_system_prompt(competition_catalog_prompt())
    graph_arguments: dict[str, Any] = {
        "model": model,
        "tools": [resolve_player, resolve_event, query_analytics, create_visualization],
        "prompt": system_prompt,
        "state_schema": CurlChatAgentState,
    }
    if checkpointer is not None:
        graph_arguments["checkpointer"] = checkpointer
    return create_react_agent(**graph_arguments)


def respond_to_message(
    message: str, conversation_id: UUID | None = None, settings: Settings | None = None
) -> AgentResponse:
    """Run a message, optionally persisting its history under one conversation ID."""
    configured_settings = settings or get_settings()
    checkpointer_context = (
        PostgresSaver.from_conn_string(_psycopg_url(configured_settings.state_database_url))
        if conversation_id is not None
        else nullcontext(None)
    )
    try:
        with checkpointer_context as checkpointer:
            graph = (
                build_graph(configured_settings, checkpointer=checkpointer)
                if conversation_id is not None
                else build_graph(configured_settings)
            )
            invocation_arguments: dict[str, Any] = {
                "messages": [{"role": "user", "content": message}]
            }
            if conversation_id is not None:
                state = graph.invoke(
                    invocation_arguments,
                    config={"configurable": {"thread_id": str(conversation_id)}},
                )
            else:
                state = graph.invoke(invocation_arguments)
    except OpenAIError as error:
        raise AgentInvocationError("The model provider could not complete the request.") from error
    messages = state["messages"]
    return AgentResponse(
        message=_message_text(messages[-1].content),
        artifacts=_visualization_artifacts(_current_turn_messages(messages)),
    )


def stream_response(
    message: str, conversation_id: UUID, settings: Settings | None = None
) -> Iterator[AgentStreamEvent]:
    """Stream deterministic progress, final prose, and completed visualization artifacts."""
    configured_settings = settings or get_settings()
    try:
        with PostgresSaver.from_conn_string(
            _psycopg_url(configured_settings.state_database_url)
        ) as checkpointer:
            graph = build_graph(configured_settings, checkpointer=checkpointer)
            config = {"configurable": {"thread_id": str(conversation_id)}}
            yield AgentStreamEvent(type="status", payload={"label": "Resolving context…"})
            latest_status = "Resolving context…"
            for data in graph.stream(
                {"messages": [{"role": "user", "content": message}]},
                config=config,
                stream_mode="updates",
                durability="sync",
            ):
                status = _status_from_updates(data)
                if status and status != latest_status:
                    latest_status = status
                    yield AgentStreamEvent(type="status", payload={"label": status})
                for artifact in _artifacts_from_updates(data):
                    yield AgentStreamEvent(
                        type="artifact",
                        payload={"type": artifact.type, "payload": artifact.payload},
                    )
                for text in _final_response_texts_from_updates(data):
                    if latest_status != "Writing answer…":
                        latest_status = "Writing answer…"
                        yield AgentStreamEvent(type="status", payload={"label": latest_status})
                    yield AgentStreamEvent(type="markdown_delta", payload={"delta": text})
    except OpenAIError as error:
        raise AgentInvocationError("The model provider could not complete the request.") from error
    yield AgentStreamEvent(type="complete")


def load_conversation_history(
    conversation_id: UUID, settings: Settings | None = None
) -> tuple[ConversationHistoryMessage, ...]:
    """Load renderable messages from the latest persisted graph state for one conversation."""
    configured_settings = settings or get_settings()
    with PostgresSaver.from_conn_string(
        _psycopg_url(configured_settings.state_database_url)
    ) as checkpointer:
        checkpoint = checkpointer.get_tuple(
            {"configurable": {"thread_id": str(conversation_id)}}
        )
    if checkpoint is None:
        return ()
    messages = checkpoint.checkpoint["channel_values"].get("messages", [])
    return _history_messages(messages)


def _psycopg_url(database_url: str) -> str:
    """Convert SQLAlchemy's psycopg URL form to the driver's connection URL."""
    return make_url(database_url).set(drivername="postgresql").render_as_string(hide_password=False)


def _visualization_artifacts(messages: list[Any]) -> tuple[VisualizationArtifact, ...]:
    """Extract valid Visualization Tool outputs without trusting arbitrary tool content."""
    artifacts: list[VisualizationArtifact] = []
    for message in messages:
        if getattr(message, "name", None) != create_visualization.name:
            continue
        try:
            artifacts.append(VisualizationArtifact.model_validate_json(_message_text(message.content)))
        except (ValidationError, ValueError):
            continue
    return tuple(artifacts)


def _artifacts_from_updates(update: Any) -> tuple[VisualizationArtifact, ...]:
    """Extract artifacts from current-turn ToolNode updates only."""
    if not isinstance(update, dict):
        return ()
    artifacts: list[VisualizationArtifact] = []
    for node_update in update.values():
        if not isinstance(node_update, dict):
            continue
        messages = node_update.get("messages")
        if isinstance(messages, list):
            artifacts.extend(_visualization_artifacts(messages))
    return tuple(artifacts)


def _status_from_updates(update: Any) -> str | None:
    """Map deterministic tool completions to concise, non-persisted UI progress text."""
    tool_names: set[str | None] = set()
    for node_update in _node_updates(update):
        messages = node_update.get("messages", [])
        if isinstance(messages, list):
            for message in messages:
                tool_names.add(getattr(message, "name", None))
                tool_names.update(
                    call.get("name")
                    for call in (_tool_calls(message) or [])
                    if isinstance(call, dict)
                )
    if create_visualization.name in tool_names:
        return "Preparing visualization…"
    if query_analytics.name in tool_names:
        return "Querying statistics…"
    if resolve_player.name in tool_names or resolve_event.name in tool_names:
        return "Resolving context…"
    return None


def _final_response_texts_from_updates(update: Any) -> tuple[str, ...]:
    """Return only completed assistant messages that do not request another tool."""
    texts: list[str] = []
    for node_update in _node_updates(update):
        messages = node_update.get("messages", [])
        if not isinstance(messages, list):
            continue
        for message in messages:
            if _message_type(message) != "ai" or _tool_calls(message):
                continue
            if text := _message_text(_content(message)):
                texts.append(text)
    return tuple(texts)


def _node_updates(update: Any) -> tuple[dict[str, Any], ...]:
    """Return graph node update payloads in their emitted order."""
    if not isinstance(update, dict):
        return ()
    return tuple(node_update for node_update in update.values() if isinstance(node_update, dict))


def _current_turn_messages(messages: list[Any]) -> list[Any]:
    """Return messages after the latest user message in persisted graph state."""
    for index in range(len(messages) - 1, -1, -1):
        message = messages[index]
        message_type = (
            message.get("type") if isinstance(message, dict) else getattr(message, "type", None)
        )
        role = message.get("role") if isinstance(message, dict) else getattr(message, "role", None)
        if message_type == "human" or role == "user":
            return messages[index + 1 :]
    return messages


def _history_messages(messages: list[Any]) -> tuple[ConversationHistoryMessage, ...]:
    """Filter internal tool traffic and associate visualization artifacts with each reply."""
    history: list[ConversationHistoryMessage] = []
    artifacts: list[VisualizationArtifact] = []
    for message in messages:
        message_type = _message_type(message)
        if message_type == "human":
            history.append(ConversationHistoryMessage(role="user", content=_message_text(_content(message))))
            artifacts = []
            continue
        if getattr(message, "name", None) == create_visualization.name:
            try:
                artifacts.append(VisualizationArtifact.model_validate_json(_message_text(_content(message))))
            except (ValidationError, ValueError):
                continue
            continue
        if message_type == "ai" and not _tool_calls(message):
            content = _message_text(_content(message))
            if content:
                history.append(
                    ConversationHistoryMessage(
                        role="assistant", content=content, artifacts=tuple(artifacts)
                    )
                )
                artifacts = []
    return tuple(history)


def _message_type(message: Any) -> Any:
    return message.get("type") if isinstance(message, dict) else getattr(message, "type", None)


def _content(message: Any) -> Any:
    return message.get("content") if isinstance(message, dict) else getattr(message, "content", "")


def _tool_calls(message: Any) -> Any:
    return message.get("tool_calls") if isinstance(message, dict) else getattr(message, "tool_calls", None)


def _message_text(content: Any) -> str:
    """Extract text from the final LangChain message content."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            block["text"]
            for block in content
            if isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str)
        )
    return str(content)
