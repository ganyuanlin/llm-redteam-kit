"""FastAPI application exposing orchestration and reporting over HTTP."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from llm_redteam import __version__
from llm_redteam.config import build_prompts
from llm_redteam.exceptions import LRTKError, RegistryError
from llm_redteam.memory.in_memory import InMemoryMemory
from llm_redteam.orchestrator import Orchestrator
from llm_redteam.registry import list_components, load_plugins


class RunCreate(BaseModel):
    """Request body for ``POST /runs``: an engagement config plus prompts."""

    config: dict[str, Any] = Field(
        ..., description="Engagement configuration, same schema as the YAML file."
    )
    prompts: list[dict[str, Any]] | None = Field(
        default=None, description="Optional prompt overrides (id/text/metadata)."
    )


def create_app() -> FastAPI:
    """Build and return the LRTK FastAPI application."""
    load_plugins()
    app = FastAPI(
        title="LLM Red Team Kit",
        version=__version__,
        description=(
            "Authorized LLM red-teaming orchestration API. Use only against "
            "targets for which you have written authorization."
        ),
    )
    app.state.memory = InMemoryMemory()

    @app.get("/health")
    async def health() -> dict[str, str]:
        """Liveness probe."""
        return {"status": "ok", "service": "llm-redteam-kit", "version": __version__}

    @app.get("/plugins")
    async def plugins() -> dict[str, list[str]]:
        """List registered components grouped by kind."""
        return list_components()

    @app.post("/runs", status_code=201)
    async def create_run(body: RunCreate) -> dict[str, Any]:
        """Execute an engagement and persist it into the API memory store."""
        prompts_override = (
            build_prompts(body.prompts) if body.prompts is not None else None
        )
        try:
            orchestrator = await Orchestrator.create(
                body.config, prompts_override=prompts_override
            )
            try:
                run = await orchestrator.execute()
            finally:
                await orchestrator.close()
        except (LRTKError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        await app.state.memory.save_run(run)
        return run.model_dump(mode="json")

    @app.get("/runs")
    async def list_runs() -> list[dict[str, Any]]:
        """List runs known to this API instance (newest first)."""
        runs = await app.state.memory.list_runs()
        return [run.model_dump(mode="json") for run in runs]

    @app.get("/runs/{run_id}")
    async def get_run(run_id: str) -> dict[str, Any]:
        """Fetch one run by identifier."""
        run = await app.state.memory.get_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail=f"Run {run_id!r} not found")
        return run.model_dump(mode="json")

    @app.get("/runs/{run_id}/report")
    async def get_report(
        run_id: str,
        format: str = Query("json", pattern="^(json|markdown|html|sarif)$"),
    ) -> dict[str, str]:
        """Render a run in the requested report format."""
        run = await app.state.memory.get_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail=f"Run {run_id!r} not found")
        try:
            content = Orchestrator.render_report(run, format)
        except RegistryError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"run_id": run_id, "format": format, "report": content}

    return app


app = create_app()
