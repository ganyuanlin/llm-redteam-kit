"""ROT13 letter-substitution converter."""

from __future__ import annotations

import codecs

from llm_redteam.converters.base import Converter
from llm_redteam.registry import register_converter


@register_converter("rot13")
class ROT13Converter(Converter):
    """Apply the self-inverse ROT13 cipher to ASCII letters."""

    name = "rot13"

    def transform(self, text: str) -> str:
        return codecs.encode(text, "rot_13")
