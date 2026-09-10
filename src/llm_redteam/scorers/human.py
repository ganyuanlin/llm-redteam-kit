"""Human-in-the-loop scorer.

Verdicts are supplied out of band via :meth:`HumanScorer.provide`. Responses
without a supplied verdict score ``unknown`` and a rationale noting that
review is pending, which keeps fully automated runs green while still
supporting analyst review workflows.
"""

from __future__ import annotations

from dataclasses import dataclass

from llm_redteam.models import Prompt, Response, Score, ScoreLabel
from llm_redteam.registry import register_scorer
from llm_redteam.scorers.base import Scorer


@dataclass(frozen=True)
class HumanVerdict:
    """One analyst-supplied verdict."""

    value: float
    label: ScoreLabel
    rationale: str | None = None


@register_scorer("human")
class HumanScorer(Scorer):
    """Return analyst-provided verdicts, or ``unknown`` while pending."""

    name = "human"

    def __init__(self, reviewer: str = "anonymous") -> None:
        super().__init__(reviewer=reviewer)
        self.reviewer = reviewer
        self._verdicts: dict[str, HumanVerdict] = {}

    def provide(
        self,
        response_id: str,
        value: float,
        label: ScoreLabel,
        rationale: str | None = None,
    ) -> None:
        """Register a human verdict for ``response_id``."""
        self._verdicts[response_id] = HumanVerdict(
            value=max(0.0, min(1.0, float(value))),
            label=label,
            rationale=rationale,
        )

    async def score(self, prompt: Prompt, response: Response) -> Score:
        verdict = self._verdicts.get(response.id)
        if verdict is None:
            return self.build_score(
                response.id,
                0.0,
                "unknown",
                f"Awaiting human review by {self.reviewer}",
                {"reviewer": self.reviewer, "pending": True},
            )
        return self.build_score(
            response.id,
            verdict.value,
            verdict.label,
            verdict.rationale or "Human-reviewed verdict",
            {"reviewer": self.reviewer, "pending": False},
        )
