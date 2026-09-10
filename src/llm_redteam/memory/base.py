"""Abstract persistence backend for attack runs."""

from __future__ import annotations

from abc import ABC, abstractmethod

from llm_redteam.models import AttackRun


class Memory(ABC):
    """Store and retrieve complete :class:`AttackRun` records."""

    @abstractmethod
    async def save_run(self, run: AttackRun) -> None:
        """Insert or update ``run`` keyed by ``run.id``."""

    @abstractmethod
    async def get_run(self, run_id: str) -> AttackRun | None:
        """Return one run or ``None`` when it does not exist."""

    @abstractmethod
    async def list_runs(self) -> list[AttackRun]:
        """Return all persisted runs, newest first."""

    async def close(self) -> None:
        """Release backend resources. Default implementation is a no-op."""
