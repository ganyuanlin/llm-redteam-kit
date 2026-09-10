"""High-level orchestration: config -> components -> run -> persistence."""

from __future__ import annotations

import asyncio
import copy
from pathlib import Path
from typing import Any

from llm_redteam.attacks.base import Attack
from llm_redteam.config import (
    Settings,
    build_attack,
    build_converters,
    build_memory,
    build_prompts,
    build_scorers,
    build_target,
    load_yaml_config,
)
from llm_redteam.converters.base import Converter
from llm_redteam.exceptions import ConfigError, LRTKError
from llm_redteam.logging import configure_logging, get_logger
from llm_redteam.memory.base import Memory
from llm_redteam.models import AttackContext, AttackRun, Prompt, new_id
from llm_redteam.registry import reporters
from llm_redteam.scorers.base import Scorer
from llm_redteam.targets.base import Target

DEFAULT_REPORT_FORMATS: tuple[str, ...] = ("json", "markdown", "html")
_LOG = get_logger(__name__)


class Orchestrator:
    """Build and execute one engagement from a validated config mapping."""

    def __init__(self) -> None:
        self.settings = Settings()
        self.config: dict[str, Any] = {}
        self.name = "lrtk-run"
        self.output_dir = Path(self.settings.output_dir)
        self.authorization: dict[str, Any] | None = None
        self.target: Target
        self.attack: Attack
        self.converters: list[Converter] = []
        self.scorers: list[Scorer] = []
        self.memory: Memory
        self.prompts: list[Prompt] = []
        self.formats: list[str] = list(DEFAULT_REPORT_FORMATS)
        self.aux_targets: dict[str, Target] = {}
        self.report_paths: dict[str, Path] = {}

    @classmethod
    async def create(
        cls,
        config: dict[str, Any],
        *,
        prompts_override: list[Prompt] | None = None,
        settings: Settings | None = None,
    ) -> Orchestrator:
        """Validate ``config`` and construct every configured component."""
        orchestrator = cls()
        if settings is not None:
            orchestrator.settings = settings
        configure_logging(orchestrator.settings.log_level)
        if "target" not in config or "attack" not in config:
            raise ConfigError("Config must define 'target' and 'attack' sections")

        orchestrator.config = copy.deepcopy(config)
        run_section = config.get("run") or {}
        attack_section = config["attack"]

        orchestrator.name = str(run_section.get("name", attack_section.get("type", "run")))
        orchestrator.output_dir = Path(
            str(run_section.get("output_dir") or orchestrator.settings.output_dir)
        )
        authorization = run_section.get("authorization")
        if authorization is not None and not isinstance(authorization, dict):
            raise ConfigError("run.authorization must be a mapping")
        orchestrator.authorization = authorization

        orchestrator.target = build_target(config["target"])
        orchestrator.converters = build_converters(config.get("converters"))
        orchestrator.scorers = build_scorers(config.get("scorers"))
        orchestrator.memory = await build_memory(config.get("memory"))
        orchestrator.attack = build_attack(attack_section)

        aux_specs = attack_section.get("targets") or {}
        if not isinstance(aux_specs, dict):
            raise ConfigError("attack.targets must be a mapping of name -> target spec")
        orchestrator.aux_targets = {
            str(name): build_target(spec)
            for name, spec in aux_specs.items()
            if isinstance(spec, dict)
        }

        if prompts_override is not None:
            orchestrator.prompts = list(prompts_override)
        else:
            orchestrator.prompts = build_prompts(attack_section.get("prompts"))
        if not orchestrator.prompts:
            raise ConfigError("At least one prompt is required (inline or --prompt-file)")

        reporting_section = config.get("reporting") or {}
        formats = reporting_section.get("formats") or list(DEFAULT_REPORT_FORMATS)
        orchestrator.formats = [str(fmt) for fmt in formats]
        return orchestrator

    @classmethod
    async def from_yaml(
        cls,
        path: str | Path,
        *,
        prompts_override: list[Prompt] | None = None,
    ) -> Orchestrator:
        """Create an orchestrator from a YAML config file."""
        return await cls.create(
            load_yaml_config(path), prompts_override=prompts_override
        )

    async def execute(self) -> AttackRun:
        """Run the attack, persist the run and write configured reports."""
        run_id = new_id("run_")
        run_section = self.config.get("run") or {}
        attack_section = self.config.get("attack") or {}
        context = AttackContext(
            run_id=run_id,
            converters=self.converters,
            scorers=self.scorers,
            concurrency=int(run_section.get("concurrency", 1)),
            max_turns=int(attack_section.get("max_turns", 5)),
            targets=self.aux_targets,
            metadata={"authorization": self.authorization},
        )
        try:
            run = await self.attack.run(self.target, self.prompts, context)
        except LRTKError:
            raise
        except Exception as exc:
            failed = AttackRun(
                id=run_id,
                name=self.name,
                status="failed",
                config=copy.deepcopy(self.config),
                authorization=self.authorization,
            )
            await self.memory.save_run(failed)
            raise LRTKError(f"Attack execution failed: {exc}") from exc

        run.name = self.name
        run.config = copy.deepcopy(self.config)
        run.authorization = self.authorization
        await self.memory.save_run(run)
        self.report_paths = await self.write_reports(run)
        _LOG.info(
            "Run %s finished: %d turns, reports in %s",
            run.id,
            len(run.turns),
            self.output_dir / run.id,
        )
        return run

    async def write_reports(self, run: AttackRun) -> dict[str, Path]:
        """Render every configured format into ``output_dir/<run_id>/``."""
        run_dir = self.output_dir / run.id
        await asyncio.to_thread(run_dir.mkdir, parents=True, exist_ok=True)
        paths: dict[str, Path] = {}
        for fmt in self.formats:
            reporter_cls = reporters.get(fmt)
            content = reporter_cls().generate(run)
            destination = run_dir / f"report.{reporter_cls.extension}"
            await asyncio.to_thread(
                destination.write_text, content, "utf-8"
            )
            paths[fmt] = destination
        return paths

    @staticmethod
    def render_report(run: AttackRun, fmt: str) -> str:
        """Render ``run`` in a single ad-hoc format without writing files."""
        reporter_cls = reporters.get(fmt)
        return reporter_cls().generate(run)

    async def close(self) -> None:
        """Close memory and target network resources."""
        await self.memory.close()
        await self.target.aclose()
        for aux in self.aux_targets.values():
            await aux.aclose()
