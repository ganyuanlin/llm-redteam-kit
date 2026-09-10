"""Pydantic v2 data models shared across the whole LRTK pipeline.

The models are intentionally flat and JSON-serializable so that every run can
be persisted to SQLite/JSONL and exported as JSON/SARIF without custom
encoders.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from llm_redteam.converters.base import Converter
    from llm_redteam.scorers.base import Scorer
    from llm_redteam.targets.base import Target

#: Allowed chat-message roles.
Role = Literal["system", "user", "assistant"]

#: Unified score labels understood by every scorer.
ScoreLabel = Literal["success", "failure", "refusal", "unknown"]

#: Lifecycle of an :class:`AttackRun`.
RunStatus = Literal["pending", "running", "completed", "failed"]


def utcnow() -> datetime:
    """Return the current time as a timezone-aware UTC datetime."""
    return datetime.now(UTC)


def new_id(prefix: str) -> str:
    """Generate a short, prefixed, filesystem-safe unique identifier."""
    return f"{prefix}{uuid.uuid4().hex[:12]}"


class Message(BaseModel):
    """A single chat message exchanged with a target model."""

    role: Role
    content: str


class TargetConfig(BaseModel):
    """Declarative configuration for a :class:`~llm_redteam.targets.base.Target`."""

    type: str
    name: str
    model: str | None = None
    base_url: str | None = None
    #: Name of the environment variable holding the API key (never the key
    #: itself). LRTK reads the value lazily and never persists it.
    api_key_env: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    timeout: float = 60.0


class Prompt(BaseModel):
    """An input prompt plus arbitrary provenance metadata."""

    id: str
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class Response(BaseModel):
    """A target model's response, including telemetry and optional error."""

    id: str = Field(default_factory=lambda: new_id("resp_"))
    target_name: str
    content: str
    raw: dict[str, Any] | None = None
    latency_ms: float = 0.0
    usage: dict[str, Any] | None = None
    #: When set, the target call failed; ``content`` is usually empty.
    error: str | None = None

    @property
    def ok(self) -> bool:
        """Return ``True`` when the response was produced without an error."""
        return self.error is None


class Score(BaseModel):
    """The normalized output of a scorer for one response."""

    id: str = Field(default_factory=lambda: new_id("score_"))
    response_id: str
    scorer: str
    #: Confidence/success magnitude in the closed interval ``[0.0, 1.0]``.
    value: float = Field(ge=0.0, le=1.0)
    label: ScoreLabel
    rationale: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Turn(BaseModel):
    """One prompt/response/scoring interaction within a run."""

    index: int
    prompt: Prompt
    response: Response
    scores: list[Score] = Field(default_factory=list)

    @property
    def succeeded(self) -> bool:
        """Return ``True`` when at least one scorer labels the turn success."""
        return any(score.label == "success" for score in self.scores)


class AttackContext(BaseModel):
    """Runtime components and options handed to an attack.

    Concrete component instances are allowed here even though they are not
    plain JSON types; the context itself is never persisted.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    run_id: str
    converters: list[Converter] = Field(default_factory=list)
    scorers: list[Scorer] = Field(default_factory=list)
    concurrency: int = 1
    max_turns: int = 5
    #: Auxiliary targets such as PAIR's attacker/judge models.
    targets: dict[str, Target] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AttackRun(BaseModel):
    """A fully reproducible record of one attack execution."""

    id: str = Field(default_factory=lambda: new_id("run_"))
    name: str
    status: RunStatus = "pending"
    #: Snapshot of the resolved configuration used for reproducibility.
    config: dict[str, Any] = Field(default_factory=dict)
    turns: list[Turn] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=utcnow)
    finished_at: datetime | None = None
    #: Must record owner/scope/contact for an authorized engagement.
    authorization: dict[str, Any] | None = None

    def duration_ms(self) -> float | None:
        """Return the run duration in milliseconds, if finished."""
        if self.finished_at is None:
            return None
        return (self.finished_at - self.started_at).total_seconds() * 1000.0


__all__ = [
    "AttackContext",
    "AttackRun",
    "Message",
    "Prompt",
    "Response",
    "Role",
    "RunStatus",
    "Score",
    "ScoreLabel",
    "TargetConfig",
    "Turn",
    "new_id",
    "utcnow",
]
