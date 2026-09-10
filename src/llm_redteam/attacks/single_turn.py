"""Single-turn attack: convert, send, score, record - once per prompt."""

from __future__ import annotations

import asyncio

from llm_redteam.attacks.base import Attack
from llm_redteam.converters.base import apply_chain
from llm_redteam.models import (
    AttackContext,
    AttackRun,
    Message,
    Prompt,
    Turn,
)
from llm_redteam.registry import register_attack
from llm_redteam.targets.base import Target


@register_attack("single_turn")
class SingleTurnAttack(Attack):
    """Independently attack every prompt with the configured converter chain."""

    name = "single_turn"

    async def run(
        self,
        target: Target,
        prompts: list[Prompt],
        context: AttackContext,
    ) -> AttackRun:
        run = self.start_run(
            self.options.get("name", "single_turn"),
            context,
            self.options.get("config"),
        )
        concurrency = max(1, context.concurrency)
        semaphore = asyncio.Semaphore(concurrency)

        async def attack_one(index: int, prompt: Prompt) -> Turn:
            converted = apply_chain(prompt, context.converters)
            async with semaphore:
                response, scores = await self.evaluate(
                    target,
                    context.scorers,
                    converted,
                    [Message(role="user", content=converted.text)],
                )
            return Turn(index=index, prompt=converted, response=response, scores=scores)

        turns = await asyncio.gather(
            *(attack_one(index, prompt) for index, prompt in enumerate(prompts))
        )
        run.turns = list(turns)
        return self.finish(run)
