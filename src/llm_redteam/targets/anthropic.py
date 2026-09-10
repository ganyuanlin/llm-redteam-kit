"""Target adapter for the Anthropic Messages API (``/v1/messages``)."""

from __future__ import annotations

import os
from typing import Any

import httpx

from llm_redteam.exceptions import TargetError
from llm_redteam.models import Message, Response
from llm_redteam.registry import register_target
from llm_redteam.targets.base import Target, read_api_key

DEFAULT_ANTHROPIC_VERSION = "2023-06-01"


@register_target("anthropic")
class AnthropicTarget(Target):
    """Call the Anthropic Messages API directly over HTTP."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        params = self.config.params
        base = (
            self.config.base_url
            or params.get("base_url")
            or os.environ.get("ANTHROPIC_BASE_URL")
            or "https://api.anthropic.com"
        ).rstrip("/")
        self._endpoint = base if base.endswith("/messages") else f"{base}/v1/messages"
        self._api_version = str(params.get("api_version", DEFAULT_ANTHROPIC_VERSION))
        self._max_tokens = int(params.get("max_tokens", 1024))
        self._extra_headers: dict[str, str] = dict(params.get("headers") or {})
        self._extra_body: dict[str, Any] = dict(params.get("extra") or {})

    async def send(self, messages: list[Message], **kwargs: Any) -> Response:
        system_parts = [m.content for m in messages if m.role == "system"]
        chat_messages = [m.model_dump() for m in messages if m.role != "system"]
        body: dict[str, Any] = {
            "model": self.config.model,
            "messages": chat_messages,
            "max_tokens": self._max_tokens,
            **self._extra_body,
            **kwargs,
        }
        if system_parts:
            body["system"] = "\n\n".join(system_parts)
        headers = {
            "Content-Type": "application/json",
            "anthropic-version": self._api_version,
            **self._extra_headers,
        }
        api_key = read_api_key(self.config)
        if api_key:
            headers["x-api-key"] = api_key

        async def call() -> dict[str, Any]:
            async with httpx.AsyncClient() as client:
                response = await client.post(self._endpoint, json=body, headers=headers)
                response.raise_for_status()
                return response.json()

        data, latency_ms = await self._request(call)
        return self._parse(data, latency_ms)

    def _parse(self, data: dict[str, Any], latency_ms: float) -> Response:
        blocks = data.get("content")
        if not isinstance(blocks, list):
            raise TargetError(f"{self.name} response is missing a 'content' list")
        text_parts = [
            str(block.get("text", ""))
            for block in blocks
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else None
        return self.make_response(
            "".join(text_parts),
            latency_ms,
            raw=data,
            usage=usage,
        )
