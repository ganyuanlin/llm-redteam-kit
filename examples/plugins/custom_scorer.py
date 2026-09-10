"""Example external LRTK plugin: an exact-match scorer.

This file is intentionally not part of the installed package. It shows how a
third-party distribution registers components without forking LRTK.

Packaging recipe
----------------

1. Put this module inside your own package, e.g. ``my_lrtk_plugin/plugin.py``.
2. Declare the entry point in your ``pyproject.toml``::

       [project.entry-points."llm_redteam.plugins"]
       exact_match = "my_lrtk_plugin.plugin:register"

3. ``pip install`` your package. LRTK calls ``register()`` once at startup
   (CLI callback and FastAPI app factory both invoke ``load_plugins()``).

The scorer itself scores 1.0/success only when the response equals one of the
configured expected strings.
"""

from __future__ import annotations

from llm_redteam.models import Prompt, Response, Score
from llm_redteam.registry import register_scorer
from llm_redteam.scorers.base import Scorer


def register() -> None:
    """Entry-point callable: register all components shipped by the plugin."""

    @register_scorer("exact_match")
    class ExactMatchScorer(Scorer):
        """Success only for an exact (optionally case-insensitive) match."""

        name = "exact_match"

        def __init__(
            self,
            *,
            expected: list[str] | tuple[str, ...] = (),
            ignore_case: bool = True,
        ) -> None:
            super().__init__(expected=list(expected), ignore_case=ignore_case)
            self.expected = list(expected)
            self.ignore_case = ignore_case

        async def score(self, prompt: Prompt, response: Response) -> Score:
            content = response.content.lower() if self.ignore_case else response.content
            for expected in self.expected:
                candidate = expected.lower() if self.ignore_case else expected
                if candidate == content.strip():
                    return self.build_score(
                        response.id,
                        1.0,
                        "success",
                        f"Exact match for {expected!r}",
                        {"matched": expected},
                    )
            return self.build_score(
                response.id,
                0.0,
                "failure",
                "Response did not exactly match any expected string",
            )
