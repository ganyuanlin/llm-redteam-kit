"""String-reversal converter."""

from __future__ import annotations

from llm_redteam.converters.base import Converter
from llm_redteam.registry import register_converter


@register_converter("reverse")
class ReverseConverter(Converter):
    """Reverse the character order of the prompt (Unicode-safe)."""

    name = "reverse"

    def transform(self, text: str) -> str:
        return text[::-1]
