"""Deterministic competition reference rendered for main-agent prompt context."""

from __future__ import annotations

from curlchat.repositories.events import CompetitionCatalogRecord, EventRepository

_ALIASES: dict[str, tuple[str, ...]] = {
    "Canada Cup (Men)": ("Canada Cup (men)", "men's Canada Cup"),
    "Canada Cup (Women)": ("Canada Cup (women)", "women's Canada Cup"),
    "Hearts": ("Scotties", "Tournament of Hearts"),
}


class CompetitionCatalog:
    """Format imported competition coverage without making model-level decisions."""

    def __init__(self, repository: EventRepository) -> None:
        self._repository = repository

    def render_prompt_table(self) -> str:
        """Return a compact Markdown table for the main system prompt."""
        records = self._repository.list_competition_catalog_records()
        if not records:
            return "No competitions have been imported yet."
        rows = [
            "| Competition | Years covered | Shot statistics | Common aliases |",
            "| --- | --- | --- | --- |",
        ]
        rows.extend(self._render_record(record) for record in records)
        return "\n".join(rows)

    @staticmethod
    def _render_record(record: CompetitionCatalogRecord) -> str:
        years = _years_covered(record.first_event_year, record.last_event_year)
        shot_statistics = "Available" if record.has_shot_statistics else "Not available"
        aliases = "; ".join(_ALIASES.get(record.display_name, ())) or "—"
        return f"| {record.display_name} | {years} | {shot_statistics} | {aliases} |"


def _years_covered(first_year: int | None, last_year: int | None) -> str:
    """Render an imported year range without inferring coverage that is not stored."""
    if first_year is None or last_year is None:
        return "Not available"
    return str(first_year) if first_year == last_year else f"{first_year}–{last_year}"
