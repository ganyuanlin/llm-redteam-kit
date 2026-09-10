"""HTML report renderer backed by a Jinja2 template."""

from __future__ import annotations

from typing import Any

from jinja2 import Environment, PackageLoader, select_autoescape

from llm_redteam.models import AttackRun
from llm_redteam.registry import register_reporter
from llm_redteam.reporting.base import Reporter, summarize

_ENVIRONMENT = Environment(
    loader=PackageLoader("llm_redteam", "templates"),
    autoescape=select_autoescape(("html", "xml")),
    trim_blocks=True,
    lstrip_blocks=True,
)


@register_reporter("html")
class HTMLReport(Reporter):
    """Render a self-contained, interactive HTML engagement report."""

    name = "html"
    extension = "html"

    def __init__(self) -> None:
        self.template = _ENVIRONMENT.get_template("report.html.j2")

    def generate(self, run: AttackRun) -> str:
        stats: dict[str, Any] = summarize(run)
        return self.template.render(stats=stats, run=run)
