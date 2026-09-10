"""SARIF 2.1.0 report for CI/CD security-gate ingestion."""

from __future__ import annotations

import json
from typing import Any

from llm_redteam.models import AttackRun
from llm_redteam.registry import register_reporter
from llm_redteam.reporting.base import Reporter, summarize

#: SARIF rule emitted for every turn judged a successful bypass.
RULE_ID = "LRTK001"
RULE_DESCRIPTION = (
    "Potential jailbreak or prompt-injection success: the target produced a "
    "response that at least one scorer judged as a policy bypass."
)


@register_reporter("sarif")
class SARIFReport(Reporter):
    """Render findings as a SARIF 2.1.0 JSON document."""

    name = "sarif"
    extension = "sarif"

    @staticmethod
    def _tool_version() -> str:
        try:
            from llm_redteam import __version__
        except (ImportError, AttributeError):  # pragma: no cover - defensive
            return "0.0.0"
        return __version__

    def generate(self, run: AttackRun) -> str:
        stats = summarize(run)
        results: list[dict[str, Any]] = []
        for row in stats["rows"]:
            if row["label"] != "success":
                continue
            results.append(
                {
                    "ruleId": RULE_ID,
                    "level": "warning",
                    "message": {
                        "text": (
                            f"Potential jailbreak success for prompt "
                            f"{row['prompt_id']} (score={row['value']:.2f})"
                        )
                    },
                    "locations": [],
                    "properties": {
                        "run_id": run.id,
                        "prompt_id": row["prompt_id"],
                        "turn_index": row["index"],
                        "sent_prompt": row["sent_text"],
                        "original_prompt": row["prompt_text"],
                        "response_excerpt": row["response_text"][:500],
                        "scores": row["scores"],
                    },
                }
            )
        document = {
            "$schema": (
                "https://json.schemastore.org/sarif-2.1.0-rtm.6.json"
            ),
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": "llm-redteam-kit",
                            "version": self._tool_version(),
                            "informationUri": (
                                "https://github.com/ganyuanlin/llm-redteam-kit"
                            ),
                            "rules": [
                                {
                                    "id": RULE_ID,
                                    "name": "PotentialJailbreakSuccess",
                                    "shortDescription": {
                                        "text": "Potential jailbreak success"
                                    },
                                    "fullDescription": {"text": RULE_DESCRIPTION},
                                    "defaultConfiguration": {"level": "warning"},
                                }
                            ],
                        }
                    },
                    "results": results,
                    "properties": {
                        "run_id": run.id,
                        "run_name": run.name,
                        "success_rate": stats["success_rate"],
                        "total_turns": stats["total"],
                        "authorization": run.authorization,
                    },
                }
            ],
        }
        return json.dumps(document, indent=2, ensure_ascii=False)
