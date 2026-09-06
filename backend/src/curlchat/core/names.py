"""Shared normalization rules for player names."""

from __future__ import annotations

import re
import unicodedata


def normalize_name(name: str) -> str:
    """Normalize display or surname-first names for deterministic lookup."""
    name = name.strip()
    if "," in name:
        surname, given_names = (part.strip() for part in name.split(",", maxsplit=1))
        name = f"{given_names} {surname}"
    decomposed = unicodedata.normalize("NFKD", name)
    without_diacritics = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return " ".join(re.sub(r"[^\w]+", " ", without_diacritics.casefold()).split())
