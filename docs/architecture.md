# Architecture

LRTK is built around small, independently replaceable components wired
together by an orchestrator. Every pluggable kind is defined by an abstract
base class and registered in a central registry.

## Data flow

```text
CLI (Typer) / FastAPI
        |
        v
  Orchestrator  ---- reads YAML/JSON config (Pydantic validated)
        |
        v
     Attack ------------------- uses
       |        |         |          |           |
       v        v         v          v           v
  Converter  Target    Scorer     Memory      Reporter
       |        |         |          |           |
  chainable  mock/http  marker/   in-memory/  json/md/html/
  transforms  backends   judge    sqlite/jsonl  sarif
```

An `AttackRun` is the single unit of reproducibility: it captures the run id,
status, the resolved configuration, every `Turn` (sent prompt, response,
scores), timestamps and the authorization record.

## Core modules

| Module | Responsibility |
|--------|----------------|
| `models.py` | Pydantic v2 models: `Message`, `Prompt`, `Response`, `Score`, `Turn`, `AttackContext`, `AttackRun`, `TargetConfig`. |
| `registry.py` | Typed `Registry[T]`, decorators (`register_target`, ...) and entry-point discovery (`llm_redteam.plugins`). |
| `config.py` | `Settings` (pydantic-settings), YAML loading, and factory functions that build components from plain dicts. |
| `orchestrator.py` | Validates config, constructs components, executes the attack, persists the run and writes reports. |
| `exceptions.py` | `LRTKError` hierarchy (`TargetError`, `ConfigError`, ...). |
| `logging.py` | Logger setup with mandatory secret redaction. |

## Component contracts

- **Target** (`targets/base.py`): `async send(messages, **kwargs) -> Response`.
  The base class supplies timeout, retry (`max_retries`, `retry_delay`) and
  rate-limiting (`min_interval`) policies, plus error normalization to
  `TargetError`. Concrete adapters: `MockTarget`, `OpenAICompatibleTarget`,
  `AnthropicTarget`, `OllamaTarget`, `HTTPJSONTarget`.
- **Converter** (`converters/base.py`): synchronous `transform(text) -> str`
  wrapped by `convert(prompt)` which preserves an `original_text` snapshot and
  an ordered `converter_chain` in prompt metadata. Chains compose via
  `ConverterChain` / the `|` operator.
- **Scorer** (`scorers/base.py`): `async score(prompt, response) -> Score`.
  Every verdict is normalized to `{value: 0..1, label, rationale, metadata}`.
- **Attack** (`attacks/base.py`): `async run(target, prompts, context) ->
  AttackRun`. A shared `evaluate()` helper turns target failures into
  error-bearing responses and scorer failures into `unknown` scores, so one
  bad component cannot abort an engagement.
- **Memory** (`memory/base.py`): `save_run`, `get_run`, `list_runs`;
  `InMemoryMemory`, async `SQLiteMemory` (SQLAlchemy 2.0 + aiosqlite) and
  `JSONLMemory`.
- **Reporter** (`reporting/base.py`): `generate(run) -> str`. A `summarize()`
  helper computes aggregate stats shared by Markdown/HTML/SARIF.

## Asynchrony

Everything IO-bound is `async`. The CLI bridges with `asyncio.run`; FastAPI
awaits the orchestrator natively. `single_turn` fans prompts out with an
`asyncio.Semaphore` using `run.concurrency`.

## Configuration resolution order

1. Explicit YAML/JSON config file (or API body).
2. `Settings` defaults and `LRTK_*` environment variables (`.env` supported).
3. Code-level defaults on models (e.g. `timeout=60.0`).

API keys never come from config files: a target sets `api_key_env` to the
**name** of an environment variable, resolved lazily in-process.

## Persistence and reproducibility

`AttackRun.config` stores the fully resolved configuration snapshot, and each
turn stores both the converted prompt actually sent and the original text.
Given the same config and target behavior, an engagement can be replayed
with `lrtk run --config <file>`; the JSON report is a canonical archive.

## Extension points

Use a decorator in-package, or ship an entry-point plugin; see
[writing-plugins.md](writing-plugins.md).
