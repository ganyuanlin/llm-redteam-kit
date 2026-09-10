"""Abstract prompt converter and chain-composition helpers.

Converters are pure, synchronous and deterministic: one :class:`Prompt` goes
in, one :class:`Prompt` comes out. Conversion history and the original text
are preserved in ``prompt.metadata`` so runs stay reproducible.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any, ClassVar

from llm_redteam.models import Prompt

#: Metadata key holding the ordered list of applied converter names.
CHAIN_METADATA_KEY = "converter_chain"
#: Metadata key holding the prompt text before any conversion happened.
ORIGINAL_METADATA_KEY = "original_text"


class Converter(ABC):
    """Base class for all prompt converters."""

    #: Registry-facing name; subclasses override via the decorator too.
    name: ClassVar[str] = "converter"

    def __init__(self, **options: Any) -> None:
        self.options = dict(options)

    @abstractmethod
    def transform(self, text: str) -> str:
        """Return the transformed representation of ``text``."""

    def convert(self, prompt: Prompt) -> Prompt:
        """Apply :meth:`transform` while preserving provenance metadata."""
        converted = prompt.model_copy(deep=True)
        original = prompt.metadata.get(ORIGINAL_METADATA_KEY, prompt.text)
        chain = list(prompt.metadata.get(CHAIN_METADATA_KEY, []))
        converted.text = self.transform(prompt.text)
        chain.append(self.name)
        converted.metadata[CHAIN_METADATA_KEY] = chain
        converted.metadata[ORIGINAL_METADATA_KEY] = original
        return converted

    def __or__(self, other: Converter) -> ConverterChain:
        return ConverterChain([self, other])


class ConverterChain:
    """An ordered composition of converters, itself callable as one unit."""

    def __init__(self, converters: Sequence[Converter] | None = None) -> None:
        self.converters: list[Converter] = list(converters or [])

    def append(self, converter: Converter) -> ConverterChain:
        """Append ``converter`` and return self for chaining."""
        self.converters.append(converter)
        return self

    def apply(self, prompt: Prompt) -> Prompt:
        """Apply every converter in order and return the final prompt.

        Provenance metadata is always initialized, even for an empty chain,
        so every recorded turn carries ``converter_chain``/``original_text``.
        """
        result = prompt.model_copy(deep=True)
        result.metadata.setdefault(CHAIN_METADATA_KEY, [])
        result.metadata.setdefault(ORIGINAL_METADATA_KEY, result.text)
        for converter in self.converters:
            result = converter.convert(result)
        return result

    def __call__(self, prompt: Prompt) -> Prompt:
        return self.apply(prompt)

    def __or__(self, other: Converter) -> ConverterChain:
        return ConverterChain([*self.converters, other])

    def __len__(self) -> int:
        return len(self.converters)


def apply_chain(prompt: Prompt, converters: Sequence[Converter]) -> Prompt:
    """Apply ``converters`` in sequence to ``prompt``."""
    return ConverterChain(converters).apply(prompt)
