"""Abstract scorer producing normalized :class:`Score` objects."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from llm_redteam.models import Prompt, Response, Score, ScoreLabel


class Scorer(ABC):
    """Base class for synchronous-looking but async-capable scorers."""

    name: ClassVar[str] = "scorer"

    def __init__(self, **options: Any) -> None:
        self.options = dict(options)

    @abstractmethod
    async def score(self, prompt: Prompt, response: Response) -> Score:
        """Evaluate ``response`` (given its ``prompt``) and return a Score."""

    def build_score(
        self,
        response_id: str,
        value: float,
        label: ScoreLabel,
        rationale: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Score:
        """Construct a :class:`Score` attributed to this scorer."""
        return Score(
            response_id=response_id,
            scorer=self.name,
            value=max(0.0, min(1.0, float(value))),
            label=label,
            rationale=rationale,
            metadata=metadata or {},
        )
