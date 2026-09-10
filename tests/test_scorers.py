"""Tests for substring, regex, refusal, judge, composite and human scorers."""

from __future__ import annotations

import pytest

from llm_redteam.exceptions import TargetError
from llm_redteam.models import Message, Prompt, Response, TargetConfig
from llm_redteam.scorers.composite import CompositeScorer
from llm_redteam.scorers.human import HumanScorer
from llm_redteam.scorers.llm_judge import LLMJudgeScorer, parse_verdict
from llm_redteam.scorers.refusal import RefusalScorer
from llm_redteam.scorers.regex import RegexScorer
from llm_redteam.scorers.substring import SubstringScorer
from llm_redteam.targets.base import Target
from llm_redteam.targets.mock import MockTarget


def _response(content: str, *, error: str | None = None) -> Response:
    return Response(target_name="t", content=content, error=error)


def _prompt() -> Prompt:
    return Prompt(id="p", text="placeholder question")


async def test_substring_scorer_success_failure_unknown() -> None:
    scorer = SubstringScorer(
        success_strings=["DAN"], failure_strings=["I cannot"]
    )
    success = await scorer.score(_prompt(), _response("DAN mode active"))
    assert success.label == "success" and success.value == 1.0
    failure = await scorer.score(_prompt(), _response("I cannot do that"))
    assert failure.label == "failure" and failure.value == 0.0
    unknown = await scorer.score(_prompt(), _response("A neutral answer"))
    assert unknown.label == "unknown"


async def test_substring_scorer_case_sensitive() -> None:
    scorer = SubstringScorer(success_strings=["DAN"], case_sensitive=True)
    assert (await scorer.score(_prompt(), _response("dan lowercase"))).label == "unknown"
    assert (await scorer.score(_prompt(), _response("DAN"))).label == "success"


async def test_regex_scorer() -> None:
    scorer = RegexScorer(
        success_patterns=[r"flag\{[a-z]+\}"],
        failure_patterns=[r"(?i)unable to"],
    )
    success = await scorer.score(_prompt(), _response("token flag{open}"))
    assert success.label == "success"
    assert success.metadata["matched"] == "flag{open}"
    failure = await scorer.score(_prompt(), _response("I am UNABLE TO help"))
    assert failure.label == "failure"
    unknown = await scorer.score(_prompt(), _response("nothing here"))
    assert unknown.label == "unknown"


async def test_refusal_scorer_phrases_and_miss() -> None:
    scorer = RefusalScorer()
    refusal = await scorer.score(_prompt(), _response("I'm sorry, but I can't."))
    assert refusal.label == "refusal" and refusal.value == 0.0
    complied = await scorer.score(_prompt(), _response("Sure, here is info."))
    assert complied.label == "success" and complied.value == 1.0
    errored = await scorer.score(_prompt(), _response("", error="boom"))
    assert errored.label == "unknown"


async def test_refusal_scorer_custom_phrases() -> None:
    scorer = RefusalScorer(phrases=["nope-nope"])
    assert (await scorer.score(_prompt(), _response("NOPE-NOPE"))).label == "refusal"


def test_parse_verdict_variants() -> None:
    verdict = parse_verdict('noise {"value": 0.5, "label": "success", "rationale": "r"} tail')
    assert verdict is not None and verdict["value"] == 0.5 and verdict["label"] == "success"
    assert parse_verdict("not json") is None
    assert parse_verdict('{"value": "x", "label": "success"}') is None
    assert parse_verdict('{"value": 1, "label": "bogus"}') is None
    assert parse_verdict("{bad json}") is None


async def test_llm_judge_scorer_with_mock_judge() -> None:
    judge = MockTarget(
        TargetConfig(
            type="mock",
            name="judge",
            params={"responses": ['{"value": 0.9, "label": "success", "rationale": "bypass"}']},
        )
    )
    scorer = LLMJudgeScorer(judge)
    score = await scorer.score(_prompt(), _response("questionable content"))
    assert score.label == "success" and score.value == 0.9
    assert score.metadata["judge_target"] == "judge"


async def test_llm_judge_scorer_unparseable() -> None:
    judge = MockTarget(
        TargetConfig(type="mock", name="judge", params={"responses": ["free text only"]})
    )
    score = await LLMJudgeScorer(judge).score(_prompt(), _response("content"))
    assert score.label == "unknown"
    assert "unparseable" in (score.rationale or "")


class _BrokenTarget(Target):
    def __init__(self) -> None:
        super().__init__(TargetConfig(type="mock", name="broken"))

    async def send(self, messages: list[Message], **kwargs: object) -> Response:
        raise TargetError("connection refused")


async def test_llm_judge_scorer_unavailable_target() -> None:
    score = await LLMJudgeScorer(_BrokenTarget()).score(
        _prompt(), _response("content")
    )
    assert score.label == "unknown"
    assert "Judge target unavailable" in (score.rationale or "")


async def test_composite_scorer_any_and_all() -> None:
    good = SubstringScorer(success_strings=["yes"])
    bad = SubstringScorer(failure_strings=["no"])
    any_scorer = CompositeScorer([good, bad], mode="any")
    result = await any_scorer.score(_prompt(), _response("yes and no"))
    assert result.label == "success" and result.value == 1.0

    all_scorer = CompositeScorer(
        [SubstringScorer(success_strings=["yes"]), bad], mode="all"
    )
    assert (await all_scorer.score(_prompt(), _response("yes"))).label == "success"
    mixed = (await all_scorer.score(_prompt(), _response("yes and no"))).label
    assert mixed == "failure"

    refusal_mix = CompositeScorer([bad, RefusalScorer()])
    verdict = await refusal_mix.score(_prompt(), _response("I cannot, sorry"))
    assert verdict.label == "refusal"


async def test_composite_scorer_invalid_mode() -> None:
    with pytest.raises(ValueError, match="mode"):
        CompositeScorer([], mode="never")


async def test_human_scorer_pending_and_provided() -> None:
    scorer = HumanScorer(reviewer="alice")
    response = _response("content")
    pending = await scorer.score(_prompt(), response)
    assert pending.label == "unknown" and pending.metadata["pending"] is True

    scorer.provide(response.id, 1.0, "success", "analyst confirmed")
    confirmed = await scorer.score(_prompt(), response)
    assert confirmed.label == "success"
    assert confirmed.metadata["reviewer"] == "alice"
