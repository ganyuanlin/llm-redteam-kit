"""JSON Lines file memory backend.

Each run occupies exactly one JSON object per line, keyed by run id. Saving
an existing run rewrites the file; all blocking IO runs in a worker thread
so the event loop is never blocked.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from llm_redteam.exceptions import MemoryBackendError
from llm_redteam.logging import get_logger
from llm_redteam.memory.base import Memory
from llm_redteam.models import AttackRun
from llm_redteam.registry import register_memory

_LOG = get_logger(__name__)


@register_memory("jsonl")
class JSONLMemory(Memory):
    """Persist runs as newline-delimited JSON in a single file."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = asyncio.Lock()

    def _read_all_sync(self) -> dict[str, AttackRun]:
        if not self.path.exists():
            return {}
        runs: dict[str, AttackRun] = {}
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    run = AttackRun.model_validate_json(line)
                except ValueError as exc:
                    raise MemoryBackendError(
                        f"Corrupt JSONL record at {self.path}:{line_number}: {exc}"
                    ) from exc
                runs[run.id] = run
        return runs

    def _write_all_sync(self, runs: dict[str, AttackRun]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            for run in runs.values():
                handle.write(run.model_dump_json())
                handle.write("\n")
        temporary.replace(self.path)

    async def save_run(self, run: AttackRun) -> None:
        async with self._lock:
            runs = await asyncio.to_thread(self._read_all_sync)
            runs[run.id] = run
            await asyncio.to_thread(self._write_all_sync, runs)
            _LOG.info("Persisted run %s to %s", run.id, self.path)

    async def get_run(self, run_id: str) -> AttackRun | None:
        async with self._lock:
            runs = await asyncio.to_thread(self._read_all_sync)
        run = runs.get(run_id)
        return run.model_copy(deep=True) if run is not None else None

    async def list_runs(self) -> list[AttackRun]:
        async with self._lock:
            runs = await asyncio.to_thread(self._read_all_sync)
        ordered = sorted(runs.values(), key=lambda item: item.started_at, reverse=True)
        return [run.model_copy(deep=True) for run in ordered]


def parse_jsonl_prompts(path: str | Path) -> list[dict[str, object]]:
    """Read a JSONL prompt file into a list of plain dictionaries."""
    records: list[dict[str, object]] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise MemoryBackendError(
                    f"Invalid JSON in prompt file {path}:{line_number}: {exc}"
                ) from exc
            if not isinstance(record, dict):
                raise MemoryBackendError(
                    f"Prompt file {path}:{line_number} must contain JSON objects"
                )
            records.append(record)
    return records
