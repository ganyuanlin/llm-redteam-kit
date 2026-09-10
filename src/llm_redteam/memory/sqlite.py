"""Asynchronous SQLite memory backend (SQLAlchemy 2.0 + aiosqlite)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import String, Text, select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.pool import StaticPool

from llm_redteam.exceptions import MemoryBackendError
from llm_redteam.memory.base import Memory
from llm_redteam.models import AttackRun
from llm_redteam.registry import register_memory


class Base(DeclarativeBase):
    """Declarative base for all LRTK tables."""


class RunRecord(Base):
    """Single table storing the full run JSON keyed by run id."""

    __tablename__ = "attack_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    data: Mapped[str] = mapped_column(Text, nullable=False)


@register_memory("sqlite")
class SQLiteMemory(Memory):
    """Persist runs inside an async SQLite database."""

    def __init__(self, path: str = ":memory:") -> None:
        self.path = path
        self._engine: AsyncEngine = self._build_engine(path)
        self._session_factory = async_sessionmaker(
            self._engine, expire_on_commit=False, class_=AsyncSession
        )

    @staticmethod
    def _build_engine(path: str) -> AsyncEngine:
        if path == ":memory:":
            return create_async_engine(
                "sqlite+aiosqlite:///:memory:",
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
            )
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        return create_async_engine(f"sqlite+aiosqlite:///{path}")

    async def initialize(self) -> SQLiteMemory:
        """Create tables if they do not exist yet; return self."""
        async with self._engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        return self

    async def save_run(self, run: AttackRun) -> None:
        try:
            async with self._session_factory() as session:
                await session.merge(
                    RunRecord(id=run.id, data=run.model_dump_json())
                )
                await session.commit()
        except OSError as exc:
            raise MemoryBackendError(f"Failed to persist run {run.id}: {exc}") from exc

    async def get_run(self, run_id: str) -> AttackRun | None:
        async with self._session_factory() as session:
            record = await session.get(RunRecord, run_id)
        if record is None:
            return None
        return AttackRun.model_validate_json(record.data)

    async def list_runs(self) -> list[AttackRun]:
        async with self._session_factory() as session:
            result = await session.execute(select(RunRecord))
            records = list(result.scalars().all())
        runs: list[AttackRun] = []
        record: RunRecord
        for record in records:
            runs.append(AttackRun.model_validate_json(record.data))
        runs.sort(key=lambda item: item.started_at, reverse=True)
        return runs

    async def close(self) -> None:
        await self._engine.dispose()


def build_sqlite_memory(path: str = ":memory:", **_: Any) -> SQLiteMemory:
    """Factory kept for documentation/discovery; orchestrator uses the class."""
    return SQLiteMemory(path)
