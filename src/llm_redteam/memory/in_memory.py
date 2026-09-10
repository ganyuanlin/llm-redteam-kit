"""In-process dictionary memory backend (default for tests and the API)."""

from __future__ import annotations

import asyncio

from llm_redteam.memory.base import Memory
from llm_redteam.models import AttackRun
from llm_redteam.registry import register_memory


@register_memory("in_memory")
class InMemoryMemory(Memory):
    """Keep runs in a dictionary guarded by an asyncio lock."""

    def __init__(self) -> None:
        self._runs: dict[str, AttackRun] = {}
        self._lock = asyncio.Lock()

    async def save_run(self, run: AttackRun) -> None:
        async with self._lock:
            self._runs[run.id] = run.model_copy(deep=True)

    async def get_run(self, run_id: str) -> AttackRun | None:
        run = self._runs.get(run_id)
        return run.model_copy(deep=True) if run is not None else None

    async def list_runs(self) -> list[AttackRun]:
        runs = [run.model_copy(deep=True) for run in self._runs.values()]
        return sorted(runs, key=lambda item: item.started_at, reverse=True)
