# Attack strategies

All strategies implement the same contract: they receive a target, a list of
seed prompts and an `AttackContext` (converter chain, scorers, concurrency
and auxiliary targets), and return a fully populated `AttackRun`.

Every attack is safe to run offline against `MockTarget`; the example
escalation language consists of benign training placeholders.

## `single_turn`

The workhorse strategy. For each prompt:

1. apply the full converter chain (order preserved);
2. send one user message to the target (bounded concurrency);
3. run every scorer on the response;
4. record a `Turn`.

Target errors become error-bearing responses and scorer exceptions degrade
to `unknown`, so the run always completes.

```yaml
attack:
  type: single_turn
run:
  concurrency: 4
```

## `crescendo`

Multi-turn, gradual escalation. Each seed prompt is retried across up to
`max_turns` conversation rounds using increasingly insistent (but benign)
training framings. Full chat history is replayed each round, and the
strategy stops early as soon as any scorer reports success.

```yaml
attack:
  type: crescendo
  max_turns: 5
```

Custom steps can be supplied as the `steps` option (list of templates
containing `{prompt}`).

## `pair`

Prompt Automatic Iterative Refinement. An optional **attacker** auxiliary
target proposes refined candidates as JSON (`{"prompt": "..."}`), informed by
judge feedback from the previous round, for up to `iterations` rounds. With
no attacker configured the strategy falls back to deterministic follow-up
templates, so it remains usable in CI.

```yaml
attack:
  type: pair
  iterations: 3
  targets:
    attacker:
      type: mock
      name: attacker
      params: { mode: echo }
```

## `tap`

Tree of Attacks with Pruning. The seed is expanded breadth-first with
`branch_factor` children per node down to `max_depth`. Children that elicit a
refusal are pruned; successful branches are recorded but not expanded.
Children may come from an attacker target (`{"variants": [...]}`) or from
built-in defensive-reframing templates.

```yaml
attack:
  type: tap
  max_depth: 2
  branch_factor: 2
```

## `genetic`

Population-based search over prompt text. Each generation evaluates every
individual, keeps the fittest elites, breeds children with word-level
crossover, and mutates them (leetspeak) at `mutation_rate`. The RNG is seeded
(`seed`) for reproducibility.

```yaml
attack:
  type: genetic
  generations: 2
  population_size: 4
  elite_size: 1
  mutation_rate: 0.5
  seed: 42
```

Fitness is the maximum scorer value for the individual's response.

## Choosing a strategy

| Goal | Strategy |
|------|----------|
| Baseline regression suite, CI gating | `single_turn` |
| Measure whether context escalation erodes safeguards | `crescendo` |
| Test adaptive refinement with a second model | `pair` |
| Explore many rephrasings under a depth budget | `tap` |
| Search a prompt space with randomized recombination | `genetic` |

## Interpreting outcomes

A turn's *primary* label follows `success > refusal > failure > unknown`
across its scorer set. "Success" means a configured bypass criterion fired —
it is a signal to investigate and remediate, never an endorsement of the
underlying content.
