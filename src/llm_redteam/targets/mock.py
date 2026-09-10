"""Deterministic, network-free mock target used by demos, CI and tests."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from llm_redteam.models import Message, Response
from llm_redteam.registry import register_target
from llm_redteam.targets.base import Target

_DEFAULT_MOCK_REPLY = (
    "This is a simulated response from a mock target for authorized testing."
)
_DEFAULT_REFUSAL = "I cannot help with that request."


@register_target("mock")
class MockTarget(Target):
    """Return scripted responses without touching the network.

    Supported ``config.params`` keys:

    * ``responses``: list of strings returned round-robin (default mode).
    * ``default_response``: reply used once the list is exhausted.
    * ``keyword_responses``: mapping of substring -> reply, checked first.
    * ``mode``: one of ``cycle`` (default), ``echo`` or ``refuse``.
    * ``delay``: artificial latency in seconds.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        params = self.config.params
        self._responses = [str(item) for item in params.get("responses", [])]
        self._default = str(params.get("default_response", _DEFAULT_MOCK_REPLY))
        self._refusal = str(params.get("refusal_response", _DEFAULT_REFUSAL))
        self._keywords = {
            str(key): str(value)
            for key, value in (params.get("keyword_responses") or {}).items()
        }
        self._mode = str(params.get("mode", "cycle"))
        self._delay = float(params.get("delay", 0.0))
        self._index = 0

    async def send(self, messages: list[Message], **kwargs: Any) -> Response:
        started = time.perf_counter()
        if self._delay:
            await asyncio.sleep(self._delay)
        last_user = next(
            (m.content for m in reversed(messages) if m.role == "user"),
            "",
        )
        content = self._produce(last_user)
        latency_ms = (time.perf_counter() - started) * 1000.0
        prompt_tokens = max(1, len(last_user) // 4)
        completion_tokens = max(1, len(content) // 4)
        usage = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        }
        return self.make_response(
            content,
            latency_ms,
            raw={"mock": True, "mode": self._mode},
            usage=usage,
        )

    def _produce(self, last_user: str) -> str:
        """Compute the scripted reply for the latest user message."""
        lowered = last_user.lower()
        for keyword, reply in self._keywords.items():
            if keyword.lower() in lowered:
                return reply
        if self._mode == "echo":
            return last_user or self._default
        if self._mode == "refuse":
            return self._refusal
        if self._responses:
            reply = self._responses[self._index % len(self._responses)]
            self._index += 1
            return reply
        return self._default
