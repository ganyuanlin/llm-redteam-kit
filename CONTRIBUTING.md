# Contributing to LRTK

Thanks for taking the time to improve LLM Red Team Kit! Contributions of
bug reports, documentation fixes, new targets, converters, attacks, scorers,
reporters and tests are all welcome.

## Ground rules

1. **Authorization framing.** LRTK is for authorized security testing only.
   Contributions must not add weaponized payloads, real-world targeting,
   evasion of provider abuse systems, or instructions for unlawful acts.
   Example prompts must remain harmless placeholders.
2. **No secrets.** Never commit API keys, tokens, customer data or real
   engagement artifacts. Credentials are read from environment variables
   only, and new log output must pass through the redacting logger.
3. **Keep the mock experience working.** The default demo must run offline
   with no API key. Do not require network access for tests or for
   `lrtk run --config examples/configs/demo.yaml`.

## Development setup

```bash
git clone https://github.com/ganyuanlin/llm-redteam-kit.git
cd llm-redteam-kit
python -m venv .venv
# Windows: .venv\Scripts\Activate.ps1 ; POSIX: source .venv/bin/activate
python -m pip install -e ".[dev]"
```

Optional tooling:

```bash
pip install pre-commit
pre-commit install
```

## Quality gates

Every change must pass all three gates (CI enforces them):

```bash
ruff check .          # lint and import sorting
mypy src              # static typing on the package
pytest                # tests with >=80% coverage gate
```

Guidelines:

- Public functions, classes and methods need type annotations and docstrings.
- Prefer raising a specific exception from `llm_redteam.exceptions` over a
  bare built-in.
- New components must be registered with the matching
  `@register_*("name")` decorator and covered by tests.
- Network calls belong in target adapters only and must be exercised with
  [respx](https://github.com/lundberg/respx) mocks.
- Do not add new runtime dependencies without discussing them in an issue.

## Project layout

```text
src/llm_redteam/
  models.py        Pydantic v2 data models
  registry.py      decorator + entry-point registries
  config.py        YAML loading and component factories
  orchestrator.py  end-to-end run orchestration
  targets/         target adapters (mock + HTTP backends)
  converters/      prompt transformations
  attacks/         attack strategies
  scorers/         response scorers
  memory/          persistence backends
  reporting/       JSON/Markdown/HTML/SARIF renderers
  cli/             Typer CLI
  api/             FastAPI service
tests/             pytest suite (mirrors behavior, not package layout)
examples/          offline demo configs, prompts and a plugin example
docs/              narrative documentation
```

## Adding a component

1. Create a new module under the relevant package and subclass the matching
   ABC (`Target`, `Converter`, `Attack`, `Scorer`, `Memory`, `Reporter`).
2. Decorate it, e.g. `@register_scorer("my_scorer")`.
3. Export/import the module from the package `__init__.py` so registration
   runs at import time.
4. Add unit tests in `tests/` and, for user-facing components, a short docs
   section.
5. External plugins can register through the `llm_redteam.plugins` entry
   point instead — see [docs/writing-plugins.md](docs/writing-plugins.md).

## Commit messages

Use concise, imperative summaries (`Add leetspeak intensity option`) and
explain *why* in the body when the change is non-obvious. One logical change
per commit is preferred.

## Pull requests

- Fork the repository and create a feature branch from `main`.
- Ensure `ruff`, `mypy` and `pytest` are green locally.
- Update or add tests and documentation for behavior changes.
- Fill out the PR template, including the testing performed and the
  compliance framing for any new attack-related feature.

## Code of Conduct

Participation is governed by the [Contributor Covenant](CODE_OF_CONDUCT.md).
Be respectful and constructive; harassment of any kind is not tolerated.

## Legal

Contributions are accepted under the [Apache License 2.0](LICENSE). By
submitting a pull request you confirm that you have the right to license
your contribution under these terms.
