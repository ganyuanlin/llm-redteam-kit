"""Delimiter-wrapping converter."""

from __future__ import annotations

from llm_redteam.converters.base import Converter
from llm_redteam.registry import register_converter


@register_converter("delimiter")
class DelimiterConverter(Converter):
    """Wrap the prompt between matching delimiter fences.

    Defaults to ``###`` fences; customize with ``start``/``end`` options.
    """

    name = "delimiter"

    def __init__(self, *, start: str = "###", end: str | None = None) -> None:
        super().__init__(start=start, end=end)
        self.start = start
        self.end = start if end is None else end

    def transform(self, text: str) -> str:
        return f"{self.start}\n{text}\n{self.end}"
