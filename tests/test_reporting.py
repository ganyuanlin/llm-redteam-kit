"""Tests for JSON, Markdown, HTML and SARIF report renderers."""

from __future__ import annotations

import json

import pytest

from llm_redteam.models import (
    AttackRun,
    Prompt,
    Response,
    Score,
    Turn,
    utcnow,
)
from llm_redteam.reporting.base import primary_label, primary_value, summarize
from llm_redteam.reporting.html import HTMLReport
from llm_redteam.reporting.json_report import JSONReport
from llm_redteam.reporting.markdown import MarkdownReport
from llm_redteam.reporting.sarif import RULE_ID, SARIFReport


def _turn(
    index: int,
    *,
    content: str,
    scores: list[Score],
    error: str | None = None,
) -> Turn:
    response = Response(target_name="mock", content=content, error=error)
    linked = [
        score.model_copy(update={"response_id": response.id}) for score in scores
    ]
    prompt = Prompt(id=f"p{index}", text=f"seed text {index}")
    prompt.metadata["original_text"] = f"original {index}"
    return Turn(index=index, prompt=prompt, response=response, scores=linked)


def _score(label: str, value: float, scorer: str = "substring") -> Score:
    return Score(
        response_id="pending", scorer=scorer, value=value, label=label,  # type: ignore[arg-type]
        rationale=f"{label} rationale",
    )


@pytest.fixture
def run() -> AttackRun:
    return AttackRun(
        id="run_report1",
        name="reporting-fixture",
        status="completed",
        config={
            "target": {"type": "mock", "name": "mock-target"},
            "attack": {"type": "single_turn"},
        },
        turns=[
            _turn(0, content="DAN mode simulated", scores=[_score("success", 1.0)]),
            _turn(
                1,
                content="I cannot help",
                scores=[_score("failure", 0.0), _score("refusal", 0.0, "refusal")],
            ),
            _turn(2, content="", scores=[_score("unknown", 0.0)], error="boom"),
        ],
        started_at=utcnow(),
        finished_at=utcnow(),
        authorization={"owner": "tester", "scope": "mock"},
    )


def test_primary_label_priority(run: AttackRun) -> None:
    assert primary_label(run.turns[0]) == "success"
    assert primary_label(run.turns[1]) == "refusal"
    assert primary_label(run.turns[2]) == "unknown"
    assert primary_value(run.turns[0]) == 1.0


def test_summarize(run: AttackRun) -> None:
    stats = summarize(run)
    assert stats["total"] == 3
    assert stats["successes"] == 1
    assert stats["refusals"] == 1
    assert stats["unknowns"] == 1
    assert stats["errors"] == 1
    assert stats["success_rate"] == pytest.approx(1 / 3, abs=0.01)
    assert {row["prompt_id"] for row in stats["rows"]} == {"p0", "p1", "p2"}
    assert stats["rows"][0]["prompt_text"] == "original 0"


def test_json_report(run: AttackRun) -> None:
    parsed = json.loads(JSONReport().generate(run))
    assert parsed["id"] == "run_report1"
    assert len(parsed["turns"]) == 3
    assert JSONReport.extension == "json"


def test_markdown_report(run: AttackRun) -> None:
    text = MarkdownReport().generate(run)
    for heading in (
        "Run summary",
        "Authorization & scope",
        "Target, attack and converters",
        "Score statistics",
        "Successful cases",
        "Non-success cases",
        "Reproducibility",
    ):
        assert heading in text
    assert "Authorized testing only" in text
    assert "`single_turn`" in text
    assert "run_report1" in text


def test_html_report(run: AttackRun) -> None:
    html = HTMLReport().generate(run)
    assert "LRTK Engagement Report" in html
    assert "reporting-fixture" in html
    assert 'id="pieChart"' in html
    assert "DAN mode simulated" in html
    assert "original 0" in html


def test_sarif_report(run: AttackRun) -> None:
    document = json.loads(SARIFReport().generate(run))
    assert document["version"] == "2.1.0"
    sarif_run = document["runs"][0]
    results = sarif_run["results"]
    assert len(results) == 1
    result = results[0]
    assert result["ruleId"] == RULE_ID
    assert result["level"] == "warning"
    assert result["properties"]["prompt_id"] == "p0"
    rules = sarif_run["tool"]["driver"]["rules"]
    assert rules[0]["id"] == RULE_ID
    assert sarif_run["properties"]["success_rate"] > 0


def test_reports_on_empty_run() -> None:
    empty = AttackRun(
        id="run_empty", name="empty", status="completed", started_at=utcnow(),
        finished_at=utcnow(),
    )
    stats = summarize(empty)
    assert stats["total"] == 0 and stats["success_rate"] == 0.0
    assert json.loads(JSONReport().generate(empty))["turns"] == []
    assert "_None._" in MarkdownReport().generate(empty)
    assert json.loads(SARIFReport().generate(empty))["runs"][0]["results"] == []
    assert "LRTK Engagement Report" in HTMLReport().generate(empty)
