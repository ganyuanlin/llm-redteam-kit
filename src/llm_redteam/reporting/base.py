"""Abstract reporter and shared run-statistics helpers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import Counter
from typing import Any, ClassVar

from llm_redteam.models import AttackRun, ScoreLabel, Turn


def primary_label(turn: Turn) -> ScoreLabel:
    """Collapse a turn's scores into one label.

    Priority is ``success`` > ``refusal`` > ``failure`` > ``unknown``.
    """
    labels = {score.label for score in turn.scores}
    order: tuple[ScoreLabel, ...] = ("success", "refusal", "failure", "unknown")
    for candidate in order:
        if candidate in labels:
            return candidate
    return "unknown"


def primary_value(turn: Turn) -> float:
    """Return the highest scorer value for a turn."""
    return max((score.value for score in turn.scores), default=0.0)


def summarize(run: AttackRun) -> dict[str, Any]:
    """Compute JSON-serializable aggregate statistics for ``run``."""
    labels = [primary_label(turn) for turn in run.turns]
    counts = Counter(labels)
    total = len(run.turns)
    successes = counts.get("success", 0)
    rows = [
        {
            "index": turn.index,
            "prompt_id": turn.prompt.id,
            "prompt_text": turn.prompt.metadata.get("original_text", turn.prompt.text),
            "sent_text": turn.prompt.text,
            "response_text": turn.response.content,
            "target": turn.response.target_name,
            "label": primary_label(turn),
            "value": round(primary_value(turn), 4),
            "error": turn.response.error,
            "latency_ms": round(turn.response.latency_ms, 2),
            "scores": [score.model_dump() for score in turn.scores],
        }
        for turn in sorted(run.turns, key=lambda item: item.index)
    ]
    scorer_names = sorted(
        {score.scorer for turn in run.turns for score in turn.scores}
    )
    converter_chain: list[str] = []
    if run.turns:
        first_prompt = run.turns[0].prompt
        converter_chain = list(first_prompt.metadata.get("converter_chain", []))
    values = [primary_value(turn) for turn in run.turns]
    return {
        "run_id": run.id,
        "name": run.name,
        "status": run.status,
        "total": total,
        "successes": successes,
        "failures": counts.get("failure", 0),
        "refusals": counts.get("refusal", 0),
        "unknowns": counts.get("unknown", 0),
        "errors": sum(1 for turn in run.turns if turn.response.error),
        "success_rate": round(successes / total, 4) if total else 0.0,
        "avg_score": round(sum(values) / total, 4) if values else 0.0,
        "total_latency_ms": round(
            sum(turn.response.latency_ms for turn in run.turns), 2
        ),
        "started_at": run.started_at.isoformat(),
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "duration_ms": run.duration_ms(),
        "scorers": scorer_names,
        "converter_chain": converter_chain,
        "authorization": run.authorization,
        "config": run.config,
        "rows": rows,
    }


class Reporter(ABC):
    """Base class for report renderers."""

    name: ClassVar[str] = "reporter"
    extension: ClassVar[str] = "txt"

    @abstractmethod
    def generate(self, run: AttackRun) -> str:
        """Render ``run`` as a string in the reporter's format."""
