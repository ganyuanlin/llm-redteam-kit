"""Generic HTTP/JSON target with user-defined request and response mapping.

This adapter allows testing arbitrary internal model gateways without
writing a new Python class. Request bodies support simple ``{{token}}``
substitution and responses are extracted via dotted paths such as
``choices.0.message.content``.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from llm_redteam.exceptions import TargetError
from llm_redteam.models import Message, Response
from llm_redteam.registry import register_target
from llm_redteam.targets.base import Target, read_api_key

_TOKEN_LAST_USER = "{{last_user}}"
_TOKEN_MESSAGES = "{{messages}}"
_TOKEN_MODEL = "{{model}}"


def get_by_path(data: Any, path: str) -> Any:
    """Extract a value from nested dicts/lists using a dotted path.

    Integer segments index lists, everything else indexes mappings.
    ``""`` returns ``data`` unchanged.
    """
    current = data
    for segment in path.split("."):
        if not segment:
            continue
        try:
            if isinstance(current, list):
                current = current[int(segment)]
            elif isinstance(current, dict):
                current = current[segment]
            else:
                raise TargetError(f"Cannot descend into {segment!r} on {type(current)!r}")
        except (KeyError, IndexError, ValueError, TypeError) as exc:
            raise TargetError(f"Path {path!r} could not be resolved: {exc}") from exc
    return current


def _substitute(value: Any, tokens: dict[str, str]) -> Any:
    if isinstance(value, str):
        rendered = value
        for token, replacement in tokens.items():
            rendered = rendered.replace(token, replacement)
        return rendered
    if isinstance(value, list):
        return [_substitute(item, tokens) for item in value]
    if isinstance(value, dict):
        return {key: _substitute(item, tokens) for key, item in value.items()}
    return value


@register_target("http_json")
class HTTPJSONTarget(Target):
    """POST templated JSON and extract content from a dotted response path."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        params = self.config.params
        self._url = params.get("url")
        self._path = str(params.get("path", ""))
        self._method = str(params.get("method", "POST")).upper()
        self._body_template: Any = params.get("body")
        self._headers: dict[str, str] = dict(params.get("headers") or {})
        self._content_path = str(params.get("content_path", "content"))
        self._usage_path = params.get("usage_path")
        self._error_path = params.get("error_path")

    def _endpoint(self) -> str:
        if self._url:
            return str(self._url)
        if not self.config.base_url:
            raise TargetError(f"{self.name} requires params.url or config.base_url")
        return f"{self.config.base_url.rstrip('/')}/{self._path.lstrip('/')}".rstrip("/")

    async def send(self, messages: list[Message], **kwargs: Any) -> Response:
        last_user = next(
            (m.content for m in reversed(messages) if m.role == "user"),
            "",
        )
        tokens = {
            _TOKEN_LAST_USER: last_user,
            _TOKEN_MESSAGES: json.dumps([m.model_dump() for m in messages]),
            _TOKEN_MODEL: self.config.model or "",
        }
        body = _substitute(self._body_template, tokens) if self._body_template is not None else None
        headers = {"Content-Type": "application/json", **self._headers}
        api_key = read_api_key(self.config)
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        endpoint = self._endpoint()

        async def call() -> dict[str, Any]:
            async with httpx.AsyncClient() as client:
                response = await client.request(
                    self._method, endpoint, json=body, headers=headers
                )
                response.raise_for_status()
                return response.json()

        data, latency_ms = await self._request(call)
        if self._error_path:
            error_value = get_by_path(data, str(self._error_path))
            if error_value:
                return self.make_response(
                    "", latency_ms, raw=data, error=str(error_value)
                )
        content = get_by_path(data, self._content_path)
        usage = get_by_path(data, str(self._usage_path)) if self._usage_path else None
        return self.make_response(
            str(content),
            latency_ms,
            raw=data,
            usage=usage if isinstance(usage, dict) else None,
        )
