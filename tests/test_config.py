"""Tests for YAML loading and the component factory functions."""

from __future__ import annotations

from pathlib import Path

import pytest

from llm_redteam.attacks.single_turn import SingleTurnAttack
from llm_redteam.config import (
    Settings,
    build_attack,
    build_converters,
    build_memory,
    build_prompts,
    build_scorers,
    build_target,
    load_prompt_file,
    load_yaml_config,
)
from llm_redteam.converters.rot13 import ROT13Converter
from llm_redteam.exceptions import ConfigError, RegistryError
from llm_redteam.memory.in_memory import InMemoryMemory
from llm_redteam.memory.jsonl import JSONLMemory
from llm_redteam.memory.sqlite import SQLiteMemory
from llm_redteam.scorers.composite import CompositeScorer
from llm_redteam.scorers.llm_judge import LLMJudgeScorer
from llm_redteam.targets.mock import MockTarget


def test_settings_defaults() -> None:
    settings = Settings()
    assert settings.default_timeout == 60.0


def test_load_yaml_config_missing_and_invalid(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not found"):
        load_yaml_config(tmp_path / "nope.yaml")

    bad = tmp_path / "bad.yaml"
    bad.write_text("run: : :\n  - oops", encoding="utf-8")
    with pytest.raises(ConfigError, match="Invalid YAML"):
        load_yaml_config(bad)

    not_mapping = tmp_path / "list.yaml"
    not_mapping.write_text("- a\n- b\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="mapping"):
        load_yaml_config(not_mapping)


def test_build_target() -> None:
    target = build_target({"type": "mock", "name": "t", "extra_ignored": True})
    assert isinstance(target, MockTarget)
    with pytest.raises(ConfigError, match="'type'"):
        build_target({"name": "t"})
    with pytest.raises(RegistryError):
        build_target({"type": "does-not-exist", "name": "t"})


def test_build_converters() -> None:
    chain = build_converters([{"type": "rot13"}, {"type": "reverse"}])
    assert isinstance(chain[0], ROT13Converter) and len(chain) == 2
    with pytest.raises(ConfigError, match="'type'"):
        build_converters([{"nope": 1}])
    with pytest.raises(ConfigError, match="Invalid options"):
        build_converters([{"type": "split", "chunk_size": -2}])


def test_build_scorers_composite_and_judge() -> None:
    scorers = build_scorers(
        [
            {
                "type": "composite",
                "mode": "all",
                "scorers": [
                    {"type": "substring", "success_strings": ["x"]},
                    {"type": "refusal"},
                ],
            },
            {
                "type": "llm_judge",
                "judge": {"type": "mock", "name": "j"},
            },
        ]
    )
    assert isinstance(scorers[0], CompositeScorer)
    assert scorers[0].mode == "all"
    assert isinstance(scorers[1], LLMJudgeScorer)

    with pytest.raises(ConfigError, match="'type'"):
        build_scorers([{}])
    with pytest.raises(ConfigError, match="judge"):
        build_scorers([{"type": "llm_judge"}])
    with pytest.raises(ConfigError, match="Invalid options"):
        build_scorers([{"type": "composite", "mode": "bogus", "scorers": []}])


def test_build_attack() -> None:
    attack = build_attack({"type": "single_turn", "ignored": "prompts?"})
    assert isinstance(attack, SingleTurnAttack)
    with pytest.raises(ConfigError, match="'type'"):
        build_attack({})
    with pytest.raises(ConfigError, match="Invalid options"):
        build_attack({"type": "genetic", "population_size": "big"})


def test_build_prompts_and_file(tmp_path: Path) -> None:
    prompts = build_prompts([{"id": "p", "text": "hi"}])
    assert prompts[0].id == "p"
    with pytest.raises(ConfigError):
        build_prompts([{"id": "p"}])  # missing text

    path = tmp_path / "prompts.jsonl"
    path.write_text('{"id": "q", "text": "question"}\n', encoding="utf-8")
    loaded = load_prompt_file(path)
    assert loaded[0].text == "question"


async def test_build_memory_variants(tmp_path: Path) -> None:
    assert isinstance(await build_memory(None), InMemoryMemory)
    assert isinstance(await build_memory({"type": "in_memory"}), InMemoryMemory)
    sqlite = await build_memory(
        {"type": "sqlite", "path": str(tmp_path / "m.db")}
    )
    assert isinstance(sqlite, SQLiteMemory)
    await sqlite.close()

    jsonl = await build_memory(
        {"type": "jsonl", "path": str(tmp_path / "r.jsonl")}
    )
    assert isinstance(jsonl, JSONLMemory)

    with pytest.raises(ConfigError, match="path"):
        await build_memory({"type": "jsonl"})
    with pytest.raises(RegistryError):
        await build_memory({"type": "unknown-backend"})
