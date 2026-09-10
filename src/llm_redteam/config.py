"""Configuration loading and component factory functions.

A YAML/JSON engagement config is a plain mapping; these functions validate
it and turn each section into registered component instances. API keys only
ever appear as *environment variable names* in configs.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict

from llm_redteam.attacks.base import Attack
from llm_redteam.converters.base import Converter
from llm_redteam.exceptions import ConfigError
from llm_redteam.memory.base import Memory
from llm_redteam.memory.in_memory import InMemoryMemory
from llm_redteam.memory.jsonl import JSONLMemory, parse_jsonl_prompts
from llm_redteam.memory.sqlite import SQLiteMemory
from llm_redteam.models import Prompt, TargetConfig
from llm_redteam.registry import (
    attacks,
)
from llm_redteam.registry import (
    converters as converter_registry,
)
from llm_redteam.registry import (
    memories as memory_registry,
)
from llm_redteam.registry import (
    scorers as scorer_registry,
)
from llm_redteam.registry import (
    targets as target_registry,
)
from llm_redteam.scorers.base import Scorer
from llm_redteam.targets.base import Target


class Settings(BaseSettings):
    """Process-wide settings populated from ``LRTK_*`` environment vars."""

    model_config = SettingsConfigDict(
        env_prefix="LRTK_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    output_dir: str = "./runs"
    log_level: str = "INFO"
    default_timeout: float = 60.0


def load_yaml_config(path: str | Path) -> dict[str, Any]:
    """Load and validate an engagement YAML file into a dict."""
    config_path = Path(path)
    if not config_path.exists():
        raise ConfigError(f"Config file not found: {config_path}")
    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {config_path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"Top-level YAML document in {config_path} must be a mapping")
    return data


def build_target(spec: dict[str, Any]) -> Target:
    """Instantiate the target described by ``spec`` from the registry."""
    if "type" not in spec:
        raise ConfigError("target section requires a 'type' field")
    target_type = str(spec["type"])
    target_cls = target_registry.get(target_type)
    config = TargetConfig.model_validate(spec)
    return target_cls(config)


def build_converters(specs: list[dict[str, Any]] | None) -> list[Converter]:
    """Instantiate an ordered converter chain from config specs."""
    result: list[Converter] = []
    for spec in specs or []:
        converter_type = spec.get("type")
        if not converter_type:
            raise ConfigError("Every converter entry requires a 'type' field")
        converter_cls = converter_registry.get(str(converter_type))
        options = {key: value for key, value in spec.items() if key != "type"}
        try:
            result.append(converter_cls(**options))
        except (TypeError, ValueError) as exc:
            raise ConfigError(
                f"Invalid options for converter {converter_type!r}: {exc}"
            ) from exc
    return result


def build_scorers(specs: list[dict[str, Any]] | None) -> list[Scorer]:
    """Instantiate scorers, recursively supporting composite and llm_judge."""
    result: list[Scorer] = []
    for spec in specs or []:
        scorer_type = spec.get("type")
        if not scorer_type:
            raise ConfigError("Every scorer entry requires a 'type' field")
        scorer_cls = scorer_registry.get(str(scorer_type))
        options = dict(spec)
        options.pop("type", None)
        try:
            if scorer_type == "llm_judge":
                judge_spec = options.pop("judge", None)
                if not isinstance(judge_spec, dict):
                    raise ConfigError("llm_judge scorer requires a 'judge' target spec")
                result.append(scorer_cls(build_target(judge_spec), **options))
            elif scorer_type == "composite":
                members = build_scorers(options.pop("scorers", []))
                result.append(scorer_cls(members, **options))
            else:
                result.append(scorer_cls(**options))
        except (TypeError, ValueError) as exc:
            raise ConfigError(
                f"Invalid options for scorer {scorer_type!r}: {exc}"
            ) from exc
    return result


async def build_memory(spec: dict[str, Any] | None) -> Memory:
    """Instantiate and initialize the configured memory backend."""
    if not spec:
        return InMemoryMemory()
    memory_type = str(spec.get("type", "in_memory"))
    options = {key: value for key, value in spec.items() if key != "type"}
    if memory_type == "sqlite":
        memory = SQLiteMemory(str(options.get("path", ":memory:")))
        await memory.initialize()
        return memory
    if memory_type == "jsonl":
        if "path" not in options:
            raise ConfigError("jsonl memory requires a 'path' option")
        return JSONLMemory(str(options["path"]))
    memory_cls = memory_registry.get(memory_type)
    try:
        instance = memory_cls(**options)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"Invalid options for memory {memory_type!r}: {exc}") from exc
    initialize = getattr(instance, "initialize", None)
    if callable(initialize):
        result = initialize()
        if inspect.isawaitable(result):
            await result
    return instance


def build_attack(spec: dict[str, Any]) -> Attack:
    """Instantiate an attack strategy from its config section."""
    attack_type = spec.get("type")
    if not attack_type:
        raise ConfigError("attack section requires a 'type' field")
    attack_cls = attacks.get(str(attack_type))
    options = {
        key: value
        for key, value in spec.items()
        if key not in {"type", "prompts", "targets"}
    }
    try:
        return attack_cls(**options)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"Invalid options for attack {attack_type!r}: {exc}") from exc


def build_prompts(specs: list[dict[str, Any]] | None) -> list[Prompt]:
    """Validate inline prompt definitions."""
    prompts: list[Prompt] = []
    for spec in specs or []:
        try:
            prompts.append(Prompt.model_validate(spec))
        except ValueError as exc:
            raise ConfigError(f"Invalid prompt entry {spec!r}: {exc}") from exc
    return prompts


def load_prompt_file(path: str | Path) -> list[Prompt]:
    """Load prompts from a JSONL file with ``id`` and ``text`` fields."""
    records = parse_jsonl_prompts(path)
    try:
        return build_prompts(records)
    except ConfigError as exc:
        raise ConfigError(f"Invalid prompt file {path}: {exc}") from exc
