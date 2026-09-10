"""Abstract attack strategy with shared execution helpers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from llm_redteam.exceptions import TargetError
from llm_redteam.models import (
    AttackContext,
    AttackRun,
    Message,
    Prompt,
    Response,
    Score,
    utcnow,
)
from llm_redteam.scorers.base import Scorer
from llm_redteam.targets.base import Target


class Attack(ABC):
    """Base class for single- and multi-turn attack strategies."""

    name: ClassVar[str] = "attack"

    def __init__(self, **options: Any) -> None:
        self.options = dict(options)

    @abstractmethod
    async def run(
        self,
        target: Target,
        prompts: list[Prompt],
        context: AttackContext,
    ) -> AttackRun:
        """Execute the strategy and return the completed :class:`AttackRun`."""

    def start_run(
        self,
        name: str,
        context: AttackContext,
        config: dict[str, Any] | None = None,
    ) -> AttackRun:
        """Create a run already marked ``running`` with the context id."""
        return AttackRun(
            id=context.run_id,
            name=name,
            status="running",
            config=config or {},
            authorization=context.metadata.get("authorization"),
        )

    @staticmethod
    def finish(run: AttackRun, *, failed: bool = False) -> AttackRun:
        """Stamp the run with completion time and final status."""
        run.status = "failed" if failed else "completed"
        run.finished_at = utcnow()
        return run

    @staticmethod
    async def evaluate(
        target: Target,
        scorers: list[Scorer],
        prompt: Prompt,
        messages: list[Message],
    ) -> tuple[Response, list[Score]]:
        """Send ``messages`` to ``target`` and score the resulting response.

        Target failures become an error-bearing :class:`Response` instead of
        aborting the whole run; scorer failures degrade to ``unknown``.
        """
        try:
            response = await target.send(messages)
        except TargetError as exc:
            response = Response(
                target_name=target.name,
                content="",
                error=str(exc),
            )
        scores: list[Score] = []
        for scorer in scorers:
            try:
                scores.append(await scorer.score(prompt, response))
            except Exception as exc:  # one bad scorer must not kill the run
                scores.append(
                    Score(
                        response_id=response.id,
                        scorer=scorer.name,
                        value=0.0,
                        label="unknown",
                        rationale=f"Scorer raised {type(exc).__name__}: {exc}",
                    )
                )
        return response, scores

    @staticmethod
    def is_success(scores: list[Score]) -> bool:
        """Return ``True`` when at least one scorer labels success."""
        return any(score.label == "success" for score in scores)
