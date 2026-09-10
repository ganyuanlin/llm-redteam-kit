"""End-to-end tests for all five attack strategies using MockTarget."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from llm_redteam.attacks.crescendo import CrescendoAttack
from llm_redteam.attacks.genetic import GeneticAttack
from llm_redteam.attacks.pair import PAIRAttack
from llm_redteam.attacks.single_turn import SingleTurnAttack
from llm_redteam.attacks.tap import TAPAttack
from llm_redteam.converters.base64 import Base64Converter
from llm_redteam.exceptions import TargetError
from llm_redteam.models import AttackContext, Message, Prompt, Response, TargetConfig
from llm_redteam.targets.base import Target
from llm_redteam.targets.mock import MockTarget


def _target(params: dict[str, Any]) -> MockTarget:
    return MockTarget(TargetConfig(type="mock", name="mock", params=params))


class _FailingTarget(Target):
    """Target whose send always raises TargetError."""

    def __init__(self) -> None:
        super().__init__(TargetConfig(type="mock", name="failing"))

    async def send(self, messages: list[Message], **kwargs: Any) -> Response:
        raise TargetError("simulated outage")


async def test_single_turn_attack_records_order_and_outcomes(
    prompts: list[Prompt],
    mock_target: MockTarget,
    success_scorer: Any,
    context_factory: Callable[..., AttackContext],
) -> None:
    context = context_factory(scorers=[success_scorer])
    run = await SingleTurnAttack().run(mock_target, prompts, context)

    assert run.status == "completed"
    assert run.finished_at is not None
    assert [turn.index for turn in run.turns] == [0, 1]
    assert run.turns[0].response.content.startswith("I cannot")
    assert run.turns[1].succeeded is True
    # Converter chain applied before sending.
    assert run.turns[1].prompt.metadata["converter_chain"] == []


async def test_single_turn_applies_converters(
    prompts: list[Prompt],
    success_scorer: Any,
    context_factory: Callable[..., AttackContext],
) -> None:
    target = _target({"responses": ["DAN mode enabled. Simulated.", "whatever"]})
    context = context_factory(
        scorers=[success_scorer], converters=[Base64Converter()]
    )
    run = await SingleTurnAttack().run(target, prompts[:1], context)
    sent = run.turns[0].prompt.text
    assert " " not in sent.rstrip("=") and len(sent) > 10
    assert run.turns[0].prompt.metadata["original_text"] == prompts[0].text
    assert run.turns[0].succeeded is True


async def test_single_turn_survives_target_error(
    prompts: list[Prompt],
    success_scorer: Any,
    context_factory: Callable[..., AttackContext],
) -> None:
    context = context_factory(scorers=[success_scorer])
    run = await SingleTurnAttack().run(_FailingTarget(), prompts[:1], context)
    turn = run.turns[0]
    assert turn.response.error == "simulated outage"
    assert turn.scores[0].label == "unknown"


async def test_crescendo_stops_on_success(
    prompts: list[Prompt],
    success_scorer: Any,
    context_factory: Callable[..., AttackContext],
) -> None:
    target = _target(
        {"keyword_responses": {"final step": "DAN mode enabled. Simulated."}}
    )
    context = context_factory(scorers=[success_scorer], max_turns=5)
    run = await CrescendoAttack().run(target, prompts[:1], context)
    assert len(run.turns) == 5
    assert run.turns[-1].succeeded is True


async def test_crescendo_respects_max_turns_without_success(
    prompts: list[Prompt],
    success_scorer: Any,
    context_factory: Callable[..., AttackContext],
) -> None:
    target = _target({"mode": "refuse"})
    context = context_factory(scorers=[success_scorer], max_turns=3)
    run = await CrescendoAttack().run(target, prompts[:1], context)
    assert len(run.turns) == 3
    assert not any(turn.succeeded for turn in run.turns)


async def test_pair_attack_fallback_success(
    prompts: list[Prompt],
    success_scorer: Any,
    context_factory: Callable[..., AttackContext],
) -> None:
    target = _target(
        {"keyword_responses": {"training": "DAN mode enabled. Simulated."}}
    )
    context = context_factory(scorers=[success_scorer])
    run = await PAIRAttack(iterations=3).run(target, prompts[:1], context)
    assert len(run.turns) == 1
    assert run.turns[0].succeeded is True


async def test_pair_attack_iterates_without_success(
    prompts: list[Prompt],
    success_scorer: Any,
    context_factory: Callable[..., AttackContext],
) -> None:
    target = _target({"mode": "refuse"})
    context = context_factory(scorers=[success_scorer])
    run = await PAIRAttack(iterations=3).run(target, prompts[:1], context)
    assert len(run.turns) == 3


async def test_pair_attack_uses_attacker_target(
    prompts: list[Prompt],
    success_scorer: Any,
    context_factory: Callable[..., AttackContext],
) -> None:
    target = _target(
        {"keyword_responses": {"training": "DAN mode enabled. Simulated."}}
    )
    attacker = _target(
        {"responses": ['{"prompt": "training drill question please"}']}
    )
    context = context_factory(
        scorers=[success_scorer], targets={"attacker": attacker}
    )
    run = await PAIRAttack(iterations=2).run(target, prompts[:1], context)
    assert run.turns[0].succeeded is True
    assert len(run.turns) == 1


async def test_tap_prunes_refusals(
    prompts: list[Prompt],
    success_scorer: Any,
    context_factory: Callable[..., AttackContext],
) -> None:
    target = _target({"mode": "refuse"})
    context = context_factory(scorers=[success_scorer])
    run = await TAPAttack(max_depth=2, branch_factor=2).run(
        target, prompts[:1], context
    )
    # Two root children, both refusals -> both pruned, no deeper expansion.
    assert len(run.turns) == 2
    assert not any(turn.succeeded for turn in run.turns)


async def test_tap_expands_failed_branches(
    prompts: list[Prompt],
    success_scorer: Any,
    context_factory: Callable[..., AttackContext],
) -> None:
    target = _target(
        {"keyword_responses": {"safeguards": "DAN mode enabled. Simulated."}}
    )
    context = context_factory(scorers=[success_scorer])
    run = await TAPAttack(max_depth=2, branch_factor=2).run(
        target, prompts[:1], context
    )
    # 2 root children + 2 expansions under the non-success branch.
    assert len(run.turns) == 4
    assert any(turn.succeeded for turn in run.turns)


async def test_genetic_attack_evolves_population(
    prompts: list[Prompt],
    success_scorer: Any,
    context_factory: Callable[..., AttackContext],
) -> None:
    target = _target(
        {"keyword_responses": {"dan": "DAN mode enabled. Simulated."}}
    )
    context = context_factory(scorers=[success_scorer])
    attack = GeneticAttack(
        generations=2, population_size=4, mutation_rate=1.0, seed=7
    )
    run = await attack.run(target, prompts, context)
    assert run.status == "completed"
    assert len(run.turns) == 8  # 4 individuals x 2 generations
    lineages = {turn.prompt.metadata.get("lineage") for turn in run.turns}
    assert "seed" in lineages


async def test_genetic_crossover_helper() -> None:
    left = Prompt(id="a-g0-0", text="alpha beta gamma")
    right = Prompt(id="b-g0-1", text="one two three four")
    child = GeneticAttack()._crossover(left, right, "child-1")
    assert child.id == "child-1"
    assert child.metadata["lineage"] == "crossover"
    assert child.text  # non-empty result
