"""Splitting converter that breaks text into spaced chunks."""

from __future__ import annotations

from llm_redteam.converters.base import Converter
from llm_redteam.registry import register_converter


@register_converter("split")
class SplitConverter(Converter):
    """Split text into fixed-size chunks joined by a separator.

    Options:

    * ``chunk_size``: characters per chunk (default 3).
    * ``separator``: string inserted between chunks (default single space).
    """

    name = "split"

    def __init__(self, *, chunk_size: int = 3, separator: str = " ") -> None:
        super().__init__(chunk_size=chunk_size, separator=separator)
        if chunk_size < 1:
            raise ValueError("chunk_size must be >= 1")
        self.chunk_size = chunk_size
        self.separator = separator

    def transform(self, text: str) -> str:
        chunks = [
            text[index : index + self.chunk_size]
            for index in range(0, len(text), self.chunk_size)
        ]
        return self.separator.join(chunks)
