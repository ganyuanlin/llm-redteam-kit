"""JSON reporter: the complete AttackRun serialized verbatim."""

from __future__ import annotations

from llm_redteam.models import AttackRun
from llm_redteam.registry import register_reporter
from llm_redteam.reporting.base import Reporter


@register_reporter("json")
class JSONReport(Reporter):
    """Serialize the full run as indented JSON."""

    name = "json"
    extension = "json"

    def generate(self, run: AttackRun) -> str:
        return run.model_dump_json(indent=2)
