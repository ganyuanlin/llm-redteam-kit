"""Abstract target adapter shared by every concrete LLM backend."""

from __future__ import annotations

import asyncio
import os
import time
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from llm_redteam.exceptions import TargetError
from llm_redteam.models import Message, Response, TargetConfig, new_id

#: HTTP status codes worth retrying (rate limits and transient failures).
RETRYABLE_STATUS: frozenset[int] = frozenset({408, 409, 425, 429, 500, 502, 503, 504})


def read_api_key(config: TargetConfig) -> str | None:
    """Resolve the API key for ``config`` from an environment variable.

    The key value is returned to the caller for use in a request header; it
    is never logged or persisted. When ``api_key_env`` is unset or the
    variable is empty, ``None`` is returned (e.g. for local models).
    """
    if not config.api_key_env:
        return None
    return os.environ.get(config.api_key_env)


class Target(ABC):
    """A send-only abstraction over a chat-completion style LLM endpoint."""

    def __init__(self, config: TargetConfig) -> None:
        self.config = config
        self._last_request_at = 0.0

    @property
    def name(self) -> str:
        """Human-readable target name used in responses and reports."""
        return self.config.name

    @abstractmethod
    async def send(self, messages: list[Message], **kwargs: Any) -> Response:
        """Send ``messages`` and return a normalized :class:`Response`."""

    async def aclose(self) -> None:
        """Release any held network resources. Default is a no-op."""

    def make_response(
        self,
        content: str,
        latency_ms: float,
        *,
        raw: dict[str, Any] | None = None,
        usage: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> Response:
        """Construct a :class:`Response` attributed to this target."""
        return Response(
            id=new_id("resp_"),
            target_name=self.name,
            content=content,
            raw=raw,
            usage=usage,
            latency_ms=round(latency_ms, 3),
            error=error,
        )

    async def _request(
        self, call: Callable[[], Awaitable[Any]]
    ) -> tuple[Any, float]:
        """Run ``call`` with timeout, retry and rate-limit policies.

        Policies are read from ``config.params``:

        * ``max_retries``: number of retries after the first attempt (0).
        * ``retry_delay``: base seconds between retries, grows linearly.
        * ``min_interval``: minimum seconds between two outgoing requests.
        """
        params = self.config.params
        max_retries = max(0, int(params.get("max_retries", 0)))
        retry_delay = float(params.get("retry_delay", 0.5))
        min_interval = float(params.get("min_interval", 0.0))

        started = time.perf_counter()
        last_exc: Exception | None = None
        for attempt in range(max_retries + 1):
            await self._respect_rate_limit(min_interval)
            try:
                async with asyncio.timeout(self.config.timeout):
                    result = await call()
            except TimeoutError as exc:  # raised by asyncio.timeout()
                last_exc = exc
            except httpx.HTTPError as exc:
                status = getattr(getattr(exc, "response", None), "status_code", None)
                if status is not None and status not in RETRYABLE_STATUS:
                    raise TargetError(
                        f"{self.name} request failed with HTTP {status}"
                    ) from exc
                last_exc = exc
            else:
                return result, (time.perf_counter() - started) * 1000.0
            if attempt < max_retries:
                await asyncio.sleep(retry_delay * (attempt + 1))
        raise TargetError(
            f"{self.name} request failed after {max_retries + 1} attempt(s): {last_exc}"
        ) from last_exc

    async def _respect_rate_limit(self, min_interval: float) -> None:
        """Sleep just long enough to honor ``min_interval`` between calls."""
        if min_interval <= 0:
            return
        now = time.monotonic()
        elapsed = now - self._last_request_at
        if self._last_request_at and elapsed < min_interval:
            await asyncio.sleep(min_interval - elapsed)
        self._last_request_at = time.monotonic()
