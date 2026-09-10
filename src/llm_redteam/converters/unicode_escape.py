r"""Unicode ``\uXXXX`` escape converter."""

from __future__ import annotations

from llm_redteam.converters.base import Converter
from llm_redteam.registry import register_converter


@register_converter("unicode_escape")
class UnicodeEscapeConverter(Converter):
    r"""Represent every character as a ``\uXXXX`` escape sequence.

    The result is plain ASCII and reversible through ``json.loads`` of a
    quoted string. With ``ascii_only=True`` only non-ASCII characters are
    escaped.
    """

    name = "unicode_escape"

    def __init__(self, *, ascii_only: bool = False) -> None:
        super().__init__(ascii_only=ascii_only)
        self.ascii_only = ascii_only

    def transform(self, text: str) -> str:
        return "".join(
            char if self.ascii_only and ord(char) < 128 else f"\\u{ord(char):04x}"
            for char in text
        )
