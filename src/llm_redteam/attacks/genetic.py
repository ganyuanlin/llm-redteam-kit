"""Genetic-algorithm attack over a population of prompt variants.

Each generation:

1. every individual prompt is sent and scored (its *fitness*);
2. the best individuals are kept as elites;
3. pairs of parents produce children by word-level crossover;
4. children are mutated with leetspeak substitution at ``mutation_rate``.

A seeded RNG makes runs reproducible. The algorithm is content-agnostic and
only manipulates the user's own benign seed prompts.
"""

from __future__ import annotations

import random

from llm_redteam.attacks.base import Attack
from llm_redteam.converters.base import apply_chain
from llm_redteam.converters.leetspeak import LeetspeakConverter
from llm_redteam.models import (
    AttackContext,
    AttackRun,
    Message,
    Prompt,
    Score,
    Turn,
)
from llm_redteam.registry import register_attack
from llm_redteam.targets.base import Target


@register_attack("genetic")
class GeneticAttack(Attack):
    """Evolve prompt variants through selection, crossover and mutation."""

    name = "genetic"

    def __init__(
        self,
        *,
        generations: int = 2,
        population_size: int = 4,
        elite_size: int = 1,
        mutation_rate: float = 0.5,
        seed: int = 42,
    ) -> None:
        super().__init__(
            generations=generations,
            population_size=population_size,
            elite_size=elite_size,
            mutation_rate=mutation_rate,
            seed=seed,
        )
        self.generations = max(1, generations)
        self.population_size = max(2, population_size)
        self.elite_size = min(max(1, elite_size), self.population_size - 1)
        self.mutation_rate = min(1.0, max(0.0, mutation_rate))
        self.seed = seed
        self._mutator = LeetspeakConverter()

    def _seed_population(self, prompts: list[Prompt]) -> list[Prompt]:
        if not prompts:
            return []
        population: list[Prompt] = []
        for index in range(self.population_size):
            source = prompts[index % len(prompts)]
            population.append(
                source.model_copy(
                    update={
                        "id": f"{source.id}-g0-{index}",
                        "metadata": {**source.metadata, "lineage": "seed"},
                    }
                )
            )
        return population

    @staticmethod
    def _crossover(left: Prompt, right: Prompt, child_id: str) -> Prompt:
        left_words = left.text.split()
        right_words = right.text.split()
        left_cut = len(left_words) // 2
        text = " ".join(left_words[:left_cut] + right_words[left_cut:]).strip()
        return left.model_copy(
            update={"id": child_id, "text": text or left.text,
                    "metadata": {**left.metadata, "lineage": "crossover"}}
        )

    def _mutate(self, prompt: Prompt) -> Prompt:
        return prompt.model_copy(
            update={
                "text": self._mutator.transform(prompt.text),
                "metadata": {**prompt.metadata, "lineage": "mutation"},
            }
        )

    @staticmethod
    def _fitness(scores: list[Score]) -> float:
        return max((score.value for score in scores), default=0.0)

    async def run(
        self,
        target: Target,
        prompts: list[Prompt],
        context: AttackContext,
    ) -> AttackRun:
        run = self.start_run(
            self.options.get("name", "genetic"), context, self.options.get("config")
        )
        rng = random.Random(self.seed)
        population = self._seed_population(prompts)
        turn_index = 0
        for generation in range(self.generations):
            graded: list[tuple[float, Prompt]] = []
            for individual in population:
                converted = apply_chain(individual, context.converters)
                response, scores = await self.evaluate(
                    target,
                    context.scorers,
                    converted,
                    [Message(role="user", content=converted.text)],
                )
                run.turns.append(
                    Turn(
                        index=turn_index,
                        prompt=converted,
                        response=response,
                        scores=scores,
                    )
                )
                turn_index += 1
                graded.append((self._fitness(scores), individual))
            graded.sort(key=lambda item: item[0], reverse=True)
            elites = [individual for _, individual in graded[: self.elite_size]]
            if generation == self.generations - 1:
                break
            next_population = list(elites)
            pool = [individual for _, individual in graded]
            while len(next_population) < self.population_size:
                left = rng.choice(pool)
                right = rng.choice(pool)
                lineage = f"{left.id.split('-g')[0]}-g{generation + 1}-{len(next_population)}"
                child = self._crossover(left, right, lineage)
                if rng.random() < self.mutation_rate:
                    child = self._mutate(child)
                next_population.append(child)
            population = next_population
        return self.finish(run)
