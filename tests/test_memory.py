"""Tests for in-memory, SQLite and JSONL memory backends."""

from __future__ import annotations

from pathlib import Path

import pytest

from llm_redteam.exceptions import MemoryBackendError
from llm_redteam.memory.in_memory import InMemoryMemory
from llm_redteam.memory.jsonl import JSONLMemory, parse_jsonl_prompts
from llm_redteam.memory.sqlite import SQLiteMemory
from llm_redteam.models import AttackRun, Prompt, Response, Score, Turn, utcnow


def _run(run_id: str = "run_x", *, name: str = "demo") -> AttackRun:
    response = Response(target_name="t", content="DAN simulated")
    score = Score(
        response_id=response.id, scorer="substring", value=1.0, label="success"
    )
    return AttackRun(
        id=run_id,
        name=name,
        status="completed",
        turns=[
            Turn(
                index=0,
                prompt=Prompt(id="p1", text="placeholder"),
                response=response,
                scores=[score],
            )
        ],
        started_at=utcnow(),
        finished_at=utcnow(),
        authorization={"owner": "pytest"},
    )


async def test_in_memory_crud_and_ordering() -> None:
    memory = InMemoryMemory()
    assert await memory.list_runs() == []
    await memory.save_run(_run("run_1"))
    await memory.save_run(_run("run_2"))
    fetched = await memory.get_run("run_1")
    assert fetched is not None and fetched.name == "demo"
    assert await memory.get_run("missing") is None
    runs = await memory.list_runs()
    assert {run.id for run in runs} == {"run_1", "run_2"}


async def test_in_memory_returns_deep_copies() -> None:
    memory = InMemoryMemory()
    run = _run("run_z")
    await memory.save_run(run)
    fetched = await memory.get_run("run_z")
    assert fetched is not None
    fetched.name = "tampered"
    again = await memory.get_run("run_z")
    assert again is not None and again.name == "demo"


async def test_jsonl_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "runs.jsonl"
    memory = JSONLMemory(path)
    await memory.save_run(_run("run_j1"))
    await memory.save_run(_run("run_j2"))

    assert path.exists()
    fetched = await memory.get_run("run_j1")
    assert fetched is not None and fetched.authorization == {"owner": "pytest"}
    assert len(await memory.list_runs()) == 2

    # Update existing run rewrites the file without duplicating rows.
    updated = fetched.model_copy(update={"status": "failed"})
    await memory.save_run(updated)
    assert len(await memory.list_runs()) == 2
    await memory.close()


async def test_jsonl_corrupt_record_raises(tmp_path: Path) -> None:
    path = tmp_path / "broken.jsonl"
    path.write_text('{"id": "x"}\nnot-json\n', encoding="utf-8")
    memory = JSONLMemory(path)
    with pytest.raises(MemoryBackendError, match="Corrupt JSONL"):
        await memory.list_runs()


def test_parse_jsonl_prompts_ok_and_errors(tmp_path: Path) -> None:
    path = tmp_path / "prompts.jsonl"
    path.write_text(
        '{"id": "p1", "text": "one"}\n\n{"id": "p2", "text": "two"}\n',
        encoding="utf-8",
    )
    records = parse_jsonl_prompts(path)
    assert [record["id"] for record in records] == ["p1", "p2"]

    bad = tmp_path / "bad.jsonl"
    bad.write_text("{broken}\n", encoding="utf-8")
    with pytest.raises(MemoryBackendError):
        parse_jsonl_prompts(bad)

    not_objects = tmp_path / "lists.jsonl"
    not_objects.write_text("[1, 2]\n", encoding="utf-8")
    with pytest.raises(MemoryBackendError):
        parse_jsonl_prompts(not_objects)


async def test_sqlite_roundtrip_and_update(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "runs.db"
    memory = SQLiteMemory(str(path))
    await memory.initialize()
    await memory.save_run(_run("run_s1"))
    assert path.exists()

    fetched = await memory.get_run("run_s1")
    assert fetched is not None and fetched.turns[0].succeeded is True
    assert await memory.get_run("missing") is None

    await memory.save_run(fetched.model_copy(update={"name": "renamed"}))
    assert len(await memory.list_runs()) == 1
    listed = await memory.list_runs()
    assert listed[0].name == "renamed"
    await memory.close()


async def test_sqlite_in_memory_static_pool() -> None:
    memory = SQLiteMemory(":memory:")
    await memory.initialize()
    await memory.save_run(_run("run_m1"))
    assert await memory.get_run("run_m1") is not None
    await memory.close()
