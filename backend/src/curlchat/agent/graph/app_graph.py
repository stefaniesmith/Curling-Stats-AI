"""Initial LangGraph workflow for CurlChat analytics questions."""

from __future__ import annotations

from contextlib import nullcontext
from typing import Any
from uuid import UUID

from langchain_openai import ChatOpenAI
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.prebuilt import create_react_agent
from openai import OpenAIError
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.engine import make_url

from curlchat.agent.tools.analytics_query import query_analytics
from curlchat.agent.tools.event_resolver import resolve_event
from curlchat.agent.tools.player_resolver import resolve_player
from curlchat.agent.tools.visualization import create_visualization
from curlchat.db.session import Settings, get_settings
from curlchat.services.visualization_service import VisualizationArtifact

SYSTEM_PROMPT = """You are CurlChat, a careful assistant for Curling Canada player statistics.

Use the available tools to answer questions from the imported statistics archive.

Archive event vocabulary: Brier; Canadian Women's; Canada Cup (Men); Canada
Cup (Women); Hearts; Macdonald Brier; Trials (Men); and Trials (Women). These
are the only event families available in the imported archive.
Use the listed canonical name when calling an event or analytics tool. The
archive calls the Tournament of Hearts "Hearts"; interpret "Scotties" and
"Tournament of Hearts" as Hearts. If a user asks which events are available,
answer from this list. Do not claim that an unavailable event has statistics.
When a question refers to a player, resolve that player first. If resolution is
ambiguous or not found, explain the issue and ask the user to clarify; do not
choose a player yourself. When the user requests statistics, run an analytics
query after resolving every player and named event. Pass successful resolved
player pairs to resolve_event when they are available. If event resolution is
ambiguous or not found, explain the issue and ask the user to clarify; do not
choose an event yourself. Give query_analytics the request and resolved player
and event identity pairs (display_name with player_id or event_id); never
generate, request, or expose SQL yourself. Do not invent IDs from years or
event names. Years remain part of the analytical request, not the event name
passed to resolve_event. Do not infer personal attributes; only use successful
resolver results and source statistics. After a successful analytics result,
use create_visualization when a table, concise summary, or chart would
materially improve the answer. Pass the successful result unchanged inside its
request object. Select bar for category comparisons, line for trends over
years, and dot for small discrete comparisons. Use a long data_mapping for
row-based results or a wide data_mapping to choose stat columns as categories.
Supply a series column inside the mapping for grouped bars or multiple lines
when the result has a comparison dimension such as player name. Do not request
a visualization if it would not add clarity. Base factual answers only on
successful tool results. Do not expose database credentials or internal
implementation details.
"""


class AgentConfigurationError(RuntimeError):
    """The application cannot invoke an LLM with its current configuration."""

class AgentInvocationError(RuntimeError):
    """The configured model provider could not complete an agent request."""


class AgentResponse(BaseModel):
    """Final text and renderable artifacts from one agent invocation."""

    message: str
    artifacts: tuple[VisualizationArtifact, ...] = Field(default_factory=tuple)


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
    graph_arguments: dict[str, Any] = {
        "model": model,
        "tools": [resolve_player, resolve_event, query_analytics, create_visualization],
        "prompt": SYSTEM_PROMPT,
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
        artifacts=_visualization_artifacts(messages),
    )


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
