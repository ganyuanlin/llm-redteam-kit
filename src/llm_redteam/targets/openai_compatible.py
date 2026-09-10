"""Target adapter for OpenAI-style ``/chat/completions`` HTTP endpoints.

The adapter speaks the HTTP API directly with httpx so it works against the
OpenAI service, vLLM, LiteLLM, llama.cpp server, Azure-compatible gateways
and any other OpenAI-compatible deployment without a vendor SDK.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from llm_redteam.exceptions import TargetError
from llm_redteam.models import Message, Response
from llm_redteam.registry import register_target
from llm_redteam.targets.base import Target, read_api_key


@register_target("openai_compatible")
class OpenAICompatibleTarget(Target):
    """Call an OpenAI-compatible chat-completions endpoint over HTTP."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        params = self.config.params
        self._base_url = (
            self.config.base_url
            or params.get("base_url")
            or os.environ.get("OPENAI_BASE_URL")
            or "https://api.openai.com/v1"
        ).rstrip("/")
        self._extra_headers: dict[str, str] = dict(params.get("headers") or {})
        self._extra_body: dict[str, Any] = dict(params.get("extra") or {})

    async def send(self, messages: list[Message], **kwargs: Any) -> Response:
        body: dict[str, Any] = {
            "model": self.config.model,
            "messages": [message.model_dump() for message in messages],
            **self._extra_body,
            **kwargs,
        }
        headers = {"Content-Type": "application/json", **self._extra_headers}
        api_key = read_api_key(self.config)
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        async def call() -> dict[str, Any]:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self._base_url}/chat/completions",
                    json=body,
                    headers=headers,
                )
                response.raise_for_status()
                return response.json()

        data, latency_ms = await self._request(call)
        return self._parse(data, latency_ms)

    def _parse(self, data: dict[str, Any], latency_ms: float) -> Response:
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise TargetError(
                f"{self.name} returned an unexpected response shape: {exc}"
            ) from exc
        return self.make_response(
            str(content),
            latency_ms,
            raw=data,
            usage=data.get("usage"),
        )
