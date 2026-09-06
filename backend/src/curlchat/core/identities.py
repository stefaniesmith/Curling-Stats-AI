"""Shared typed identities passed between agent and service boundaries."""

from pydantic import BaseModel, Field


class ResolvedPlayerIdentity(BaseModel):
    """A player selected by the Player Resolver."""

    display_name: str = Field(description="The resolved player's display name.")
    player_id: int = Field(description="The resolved player's database identifier.")


class ResolvedEventIdentity(BaseModel):
    """An event selected by the Event Resolver."""

    display_name: str = Field(description="The resolved event's display name.")
    event_id: int = Field(description="The resolved event's database identifier.")
