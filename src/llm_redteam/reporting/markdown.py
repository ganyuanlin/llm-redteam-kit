"""Markdown report renderer."""

from __future__ import annotations

import json
from typing import Any

from llm_redteam.models import AttackRun
from llm_redteam.registry import register_reporter
from llm_redteam.reporting.base import Reporter, summarize

_COMPLIANCE_BANNER = (
    "> **Authorized testing only.** This artifact was produced by LLM Red "
    "Team Kit for a security assessment conducted under explicit written "
    "authorization. Handle according to your engagement rules."
)


def _cell(text: str, width: int = 80) -> str:
    collapsed = " ".join(str(text).split())
    if len(collapsed) > width:
        return collapsed[: width - 1] + "…"
    return collapsed.replace("|", "\\|")


def _case_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "_None._\n"
    lines = [
        "| # | Prompt ID | Label | Score | Sent prompt | Response |",
        "|---|-----------|-------|-------|-------------|----------|",
    ]
    for row in rows:
        lines.append(
            "| {index} | {prompt_id} | {label} | {value:.2f} | {sent} | {resp} |".format(
                index=row["index"],
                prompt_id=row["prompt_id"],
                label=row["label"],
                value=row["value"],
                sent=_cell(row["sent_text"]),
                resp=_cell(row.get("error") or row["response_text"]),
            )
        )
    return "\n".join(lines) + "\n"


@register_reporter("markdown")
class MarkdownReport(Reporter):
    """Render a human-readable Markdown engagement report."""

    name = "markdown"
    extension = "md"

    def generate(self, run: AttackRun) -> str:
        stats = summarize(run)
        config = run.config or {}
        target = config.get("target", {})
        attack = config.get("attack", {})
        authorization = run.authorization or {}

        parts: list[str] = [
            f"# LRTK Report — {run.name}",
            "",
            _COMPLIANCE_BANNER,
            "",
            "## Run summary",
            "",
            "| Field | Value |",
            "|-------|-------|",
            f"| Run ID | `{run.id}` |",
            f"| Status | `{run.status}` |",
            f"| Started | {stats['started_at']} |",
            f"| Finished | {stats['finished_at'] or '-'} |",
            f"| Duration (ms) | {stats['duration_ms']} |",
            f"| Total turns | {stats['total']} |",
            f"| Success rate | {stats['success_rate']:.1%} |",
            f"| Avg. score | {stats['avg_score']:.2f} |",
            f"| Errors | {stats['errors']} |",
            "",
            "## Authorization & scope",
            "",
            "| Field | Value |",
            "|-------|-------|",
            f"| Owner | {authorization.get('owner', '_not recorded_')} |",
            f"| Scope | {authorization.get('scope', '_not recorded_')} |",
            f"| Contact | {authorization.get('contact', '_not recorded_')} |",
            f"| Authorization ref | "
            f"{authorization.get('reference', '_not recorded_')} |",
            "",
            "## Target, attack and converters",
            "",
            f"- **Target type:** `{target.get('type', '-')}`",
            f"- **Target name:** `{target.get('name', '-')}`",
            f"- **Model:** `{target.get('model', '-')}`",
            f"- **Attack strategy:** `{attack.get('type', '-')}`",
            f"- **Converter chain:** "
            f"{' -> '.join(stats['converter_chain']) or '_none_'}",
            f"- **Scorers:** {', '.join(f'`{s}`' for s in stats['scorers']) or '_none_'}",
            "",
            "## Score statistics",
            "",
            "| success | failure | refusal | unknown |",
            "|---------|---------|---------|---------|",
            f"| {stats['successes']} | {stats['failures']} | "
            f"{stats['refusals']} | {stats['unknowns']} |",
            "",
            "## Successful cases",
            "",
            _case_table([row for row in stats["rows"] if row["label"] == "success"]),
            "## Non-success cases",
            "",
            _case_table([row for row in stats["rows"] if row["label"] != "success"]),
            "## Reproducibility",
            "",
            "Re-run this engagement with:",
            "",
            "```bash",
            "lrtk run --config <engagement-config.yaml>",
            "```",
            "",
            "Resolved configuration snapshot:",
            "",
            "```json",
            json.dumps(config, indent=2, ensure_ascii=False, sort_keys=True),
            "```",
        ]
        return "\n".join(parts)
