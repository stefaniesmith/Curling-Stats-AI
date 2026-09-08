"""Load and render packaged Markdown prompt assets."""

from __future__ import annotations

from importlib.resources import files

_COMPETITION_CATALOG_PLACEHOLDER = "{{competition_catalog}}"
_SCHEMA_PLACEHOLDER = "{{schema_description}}"


def main_agent_system_prompt(competition_catalog: str) -> str:
    """Render the tool-orchestrating prompt with imported competition coverage."""
    prompt = _read_prompt("main_agent_system.md")
    if _COMPETITION_CATALOG_PLACEHOLDER not in prompt:
        raise ValueError("The main agent prompt must include the competition catalog placeholder.")
    return prompt.replace(_COMPETITION_CATALOG_PLACEHOLDER, competition_catalog)


def sql_generator_system_prompt(schema_description: str) -> str:
    """Render the SQL generator prompt with live, inspected schema context."""
    prompt = _read_prompt("sql_generator_system.md")
    if _SCHEMA_PLACEHOLDER not in prompt:
        raise ValueError("The SQL generator prompt must include the schema placeholder.")
    return prompt.replace(_SCHEMA_PLACEHOLDER, schema_description)


def _read_prompt(filename: str) -> str:
    """Read a packaged prompt asset and normalize only surrounding whitespace."""
    return files(__package__).joinpath(filename).read_text(encoding="utf-8").strip()
