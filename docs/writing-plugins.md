# Writing plugins

LRTK has six pluggable kinds:

| Kind | ABC | Decorator |
|------|-----|-----------|
| Target | `llm_redteam.targets.base.Target` | `register_target` |
| Converter | `llm_redteam.converters.base.Converter` | `register_converter` |
| Attack | `llm_redteam.attacks.base.Attack` | `register_attack` |
| Scorer | `llm_redteam.scorers.base.Scorer` | `register_scorer` |
| Memory | `llm_redteam.memory.base.Memory` | `register_memory` |
| Reporter | `llm_redteam.reporting.base.Reporter` | `register_reporter` |

## In-tree plugins

Just decorate the class and make sure the module is imported from its
package `__init__.py`:

```python
from llm_redteam.models import Prompt, Response, Score
from llm_redteam.registry import register_scorer
from llm_redteam.scorers.base import Scorer


@register_scorer("contains_secret_format")
class SecretFormatScorer(Scorer):
    """Success when a response leaks a known harmless test marker."""

    name = "contains_secret_format"

    def __init__(self, marker: str = "TEST-MARKER-") -> None:
        super().__init__(marker=marker)
        self.marker = marker

    async def score(self, prompt: Prompt, response: Response) -> Score:
        if self.marker in response.content:
            return self.build_score(
                response.id, 1.0, "success",
                f"Response contains marker {self.marker!r}",
            )
        return self.build_score(
            response.id, 0.0, "failure", "Marker not present"
        )
```

Use `override=True` (e.g. `@register_scorer("name", override=True)`) in tests
that need to swap a built-in.

## External distribution (entry points)

A complete worked example lives at
[`examples/plugins/custom_scorer.py`](../examples/plugins/custom_scorer.py).

1. Create a package with a no-argument `register()` callable:

   ```python
   # my_lrtk_plugin/plugin.py
   from llm_redteam.registry import register_scorer
   from llm_redteam.scorers.base import Scorer


   def register() -> None:
       register_scorer("exact_match")(ExactMatchScorer)
   ```

2. Declare the entry point in your `pyproject.toml`:

   ```toml
   [project.entry-points."llm_redteam.plugins"]
   exact_match = "my_lrtk_plugin.plugin:register"
   ```

3. Install the package (`pip install ./my-lrtk-plugin`). LRTK discovers and
   invokes the callable once during startup (both the CLI callback and
   `create_app()` call `load_plugins()`).

## Custom target notes

Subclass `Target`, accept a `TargetConfig`, and implement
`async send(messages, **kwargs) -> Response`. Build responses with
`self.make_response(...)` and rely on `self._request(call)` to get timeout,
retry and rate-limit behavior for HTTP-style calls. Credentials should be
resolved with `read_api_key(self.config)` — never from hardcoded values.

## Custom converter notes

Implement `transform(text) -> str`. The base `convert()` already deep-copies
the prompt, updates metadata (`converter_chain`, `original_text`) and passes
constructor options through. Keep transforms deterministic and synchronous.

## Custom attack notes

Subclass `Attack` and implement `async run(...)`. Reuse
`self.start_run(...)`, `self.finish(run)` and `self.evaluate(...)` so that
target/scorer failures are handled consistently and run records are shaped
correctly.

## Testing requirements for contributions

- Unit tests with `pytest`; use `pytest-asyncio` (auto mode).
- Mock all HTTP with `respx`; never call real providers in tests.
- New public API needs docstrings and type annotations (mypy strict on
  `src/`).
- Keep the offline demo (`MockTarget`) green without credentials.
