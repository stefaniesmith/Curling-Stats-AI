"""Initial LangGraph workflow for CurlChat analytics questions."""

from __future__ import annotations

from typing import Any

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from openai import OpenAIError

from curlchat.agent.tools.analytics_query import query_analytics
from curlchat.agent.tools.event_resolver import resolve_event
from curlchat.agent.tools.player_resolver import resolve_player
from curlchat.db.session import Settings, get_settings

SYSTEM_PROMPT = """You are CurlChat, a careful assistant for Curling Canada player statistics.

Use the available tools to answer questions from the imported statistics archive.
When a question refers to a player, resolve that player first. If resolution is
ambiguous or not found, explain the issue and ask the user to clarify; do not
choose a player yourself. When the user requests statistics, run an analytics
query after resolving every player and named event. If event resolution is
ambiguous or not found, explain the issue and ask the user to clarify; do not
choose an event yourself. Give query_analytics the request and resolved player
and event identity pairs (display_name with player_id or event_id); never
generate, request, or expose SQL yourself. Do not invent IDs from years or
event names. Years remain part of the analytical request, not the event name
passed to resolve_event.
Base factual answers only on successful tool results. Do not expose database
credentials or internal implementation details.
"""


class AgentConfigurationError(RuntimeError):
    """The application cannot invoke an LLM with its current configuration."""

class AgentInvocationError(RuntimeError):
    """The configured model provider could not complete an agent request."""



def build_graph(settings: Settings | None = None) -> Any:
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
    return create_react_agent(
        model=model,
        tools=[resolve_player, resolve_event, query_analytics],
        prompt=SYSTEM_PROMPT,
    )


def respond_to_message(message: str, settings: Settings | None = None) -> str:
    """Run one user message through the graph and return its final text response."""
    graph = build_graph(settings)
    try:
        state = graph.invoke({"messages": [{"role": "user", "content": message}]})
    except OpenAIError as error:
        raise AgentInvocationError("The model provider could not complete the request.") from error
    return _message_text(state["messages"][-1].content)


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
