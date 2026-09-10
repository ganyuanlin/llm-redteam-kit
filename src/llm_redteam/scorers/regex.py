"""Regular-expression scorer."""

from __future__ import annotations

import re
from collections.abc import Sequence

from llm_redteam.models import Prompt, Response, Score
from llm_redteam.registry import register_scorer
from llm_redteam.scorers.base import Scorer


@register_scorer("regex")
class RegexScorer(Scorer):
    """Label a response by success/failure regular expressions.

    ``success_patterns`` and ``failure_patterns`` are searched with
    :func:`re.search`. Patterns are case-insensitive by default; pass
    ``ignore_case=False`` to disable.
    """

    name = "regex"

    def __init__(
        self,
        *,
        success_patterns: Sequence[str] = (),
        failure_patterns: Sequence[str] = (),
        ignore_case: bool = True,
    ) -> None:
        super().__init__(
            success_patterns=list(success_patterns),
            failure_patterns=list(failure_patterns),
            ignore_case=ignore_case,
        )
        flags = re.IGNORECASE if ignore_case else 0
        self._success = [re.compile(pattern, flags) for pattern in success_patterns]
        self._failure = [re.compile(pattern, flags) for pattern in failure_patterns]

    async def score(self, prompt: Prompt, response: Response) -> Score:
        for pattern in self._success:
            match = pattern.search(response.content)
            if match:
                return self.build_score(
                    response.id,
                    1.0,
                    "success",
                    f"Matched success pattern {pattern.pattern!r}",
                    {"pattern": pattern.pattern, "matched": match.group(0)},
                )
        for pattern in self._failure:
            match = pattern.search(response.content)
            if match:
                return self.build_score(
                    response.id,
                    0.0,
                    "failure",
                    f"Matched failure pattern {pattern.pattern!r}",
                    {"pattern": pattern.pattern, "matched": match.group(0)},
                )
        return self.build_score(
            response.id,
            0.0,
            "unknown",
            "No configured pattern matched",
        )
