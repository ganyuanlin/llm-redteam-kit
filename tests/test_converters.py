"""Tests for every built-in prompt converter and chain composition."""

from __future__ import annotations

import base64

import pytest

from llm_redteam.converters.base import (
    CHAIN_METADATA_KEY,
    ORIGINAL_METADATA_KEY,
    ConverterChain,
    apply_chain,
)
from llm_redteam.converters.base64 import Base64Converter
from llm_redteam.converters.delimiter import DelimiterConverter
from llm_redteam.converters.leetspeak import LeetspeakConverter
from llm_redteam.converters.reverse import ReverseConverter
from llm_redteam.converters.roleplay import RolePlayConverter
from llm_redteam.converters.rot13 import ROT13Converter
from llm_redteam.converters.split import SplitConverter
from llm_redteam.converters.unicode_escape import UnicodeEscapeConverter
from llm_redteam.models import Prompt


def _prompt(text: str = "hello") -> Prompt:
    return Prompt(id="p", text=text)


def test_base64_converter() -> None:
    converted = Base64Converter().convert(_prompt("hello"))
    assert converted.text == base64.b64encode(b"hello").decode()
    assert converted.metadata[CHAIN_METADATA_KEY] == ["base64"]
    assert converted.metadata[ORIGINAL_METADATA_KEY] == "hello"


def test_base64_converter_with_instruction() -> None:
    text = Base64Converter(instruction=True).transform("secret-ish placeholder")
    assert text.startswith("The following message is base64-encoded")
    assert "cGxhY2Vob2xkZXI" in text or "c2VjcmV0" in text


def test_rot13_converter() -> None:
    assert ROT13Converter().transform("Hello") == "Uryyb"
    # ROT13 is self-inverse.
    assert ROT13Converter().transform(ROT13Converter().transform("abc")) == "abc"


def test_leetspeak_converter() -> None:
    assert LeetspeakConverter().transform("leet") == "1337"
    custom = LeetspeakConverter(mapping={"h": "#"})
    assert custom.transform("hi") == "#1"


def test_unicode_escape_converter() -> None:
    assert UnicodeEscapeConverter().transform("A") == r"\u0041"
    text = UnicodeEscapeConverter(ascii_only=True).transform("A€")
    assert text == r"A\u20ac"


def test_reverse_converter() -> None:
    assert ReverseConverter().transform("abc") == "cba"


def test_roleplay_converter() -> None:
    converted = RolePlayConverter().convert(_prompt("train me"))
    assert "train me" in converted.text
    assert "authorized" in converted.text.lower()


def test_roleplay_custom_persona_without_placeholder() -> None:
    converted = RolePlayConverter(persona="Static frame").convert(_prompt("Q"))
    assert converted.text.startswith("Static frame")
    assert converted.text.endswith("Q")


def test_delimiter_converter() -> None:
    assert DelimiterConverter().transform("x") == "###\nx\n###"
    assert DelimiterConverter(start="[[", end="]]").transform("x") == "[[\nx\n]]"


def test_split_converter() -> None:
    assert SplitConverter(chunk_size=2, separator="-").transform("hello") == "he-ll-o"
    assert SplitConverter(chunk_size=100).transform("hi") == "hi"


def test_split_converter_rejects_invalid_chunk() -> None:
    with pytest.raises(ValueError, match="chunk_size"):
        SplitConverter(chunk_size=0)


def test_chain_preserves_order_and_metadata() -> None:
    chain = ConverterChain([ROT13Converter(), ReverseConverter()])
    result = chain(_prompt("abc"))
    assert result.metadata[CHAIN_METADATA_KEY] == ["rot13", "reverse"]
    assert result.metadata[ORIGINAL_METADATA_KEY] == "abc"
    assert len(chain) == 2


def test_apply_chain_and_pipe_operator() -> None:
    chained = ROT13Converter() | ReverseConverter()
    result = apply_chain(_prompt("abc"), chained.converters)
    assert result.text == chained(_prompt("abc")).text


def test_pipe_chain_extension() -> None:
    chain = ROT13Converter() | ReverseConverter() | Base64Converter()
    assert len(chain) == 3
    out = chain(_prompt("Data"))
    assert out.metadata[CHAIN_METADATA_KEY] == ["rot13", "reverse", "base64"]
