"""Target adapter for a locally hosted Ollama server (``/api/chat``)."""

from __future__ import annotations

import os
from typing import Any

import httpx

from llm_redteam.exceptions import TargetError
from llm_redteam.models import Message, Response
from llm_redteam.registry import register_target
from llm_redteam.targets.base import Target


@register_target("ollama")
class OllamaTarget(Target):
    """Call a local Ollama daemon's chat API without an API key."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        params = self.config.params
        self._base_url = (
            self.config.base_url
            or params.get("base_url")
            or os.environ.get("OLLAMA_BASE_URL")
            or "http://localhost:11343"
        ).rstrip("/")
        self._options: dict[str, Any] = dict(params.get("options") or {})

    async def send(self, messages: list[Message], **kwargs: Any) -> Response:
        body: dict[str, Any] = {
            "model": self.config.model,
            "messages": [message.model_dump() for message in messages],
            "stream": False,
            **kwargs,
        }
        if self._options:
            body["options"] = self._options

        async def call() -> dict[str, Any]:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self._base_url}/api/chat",
                    json=body,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                return response.json()

        data, latency_ms = await self._request(call)
        return self._parse(data, latency_ms)

    def _parse(self, data: dict[str, Any], latency_ms: float) -> Response:
        try:
            content = data["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise TargetError(
                f"{self.name} returned an unexpected response shape: {exc}"
            ) from exc
        usage = {
            "prompt_tokens": data.get("prompt_eval_count"),
            "completion_tokens": data.get("eval_count"),
            "total_tokens": (data.get("prompt_eval_count") or 0)
            + (data.get("eval_count") or 0),
        }
        return self.make_response(str(content), latency_ms, raw=data, usage=usage)
