"""Leetspeak (l33t) substitution converter."""

from __future__ import annotations

from llm_redteam.converters.base import Converter
from llm_redteam.registry import register_converter

DEFAULT_LEET_MAP: dict[str, str] = {
    "a": "4",
    "b": "8",
    "e": "3",
    "g": "9",
    "i": "1",
    "l": "1",
    "o": "0",
    "s": "5",
    "t": "7",
    "z": "2",
}


@register_converter("leetspeak")
class LeetspeakConverter(Converter):
    """Replace lowercase letters with visually similar digits.

    A custom ``mapping`` option may override the default substitution table.
    """

    name = "leetspeak"

    def __init__(self, *, mapping: dict[str, str] | None = None) -> None:
        super().__init__(mapping=mapping)
        self.mapping = {**DEFAULT_LEET_MAP, **(mapping or {})}

    def transform(self, text: str) -> str:
        return "".join(self.mapping.get(char.lower(), char) for char in text)
