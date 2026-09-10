"""Tests for mock target and the four HTTP-based target adapters (respx)."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx

from llm_redteam.exceptions import TargetError
from llm_redteam.models import Message, TargetConfig
from llm_redteam.targets.anthropic import AnthropicTarget
from llm_redteam.targets.base import read_api_key
from llm_redteam.targets.http_json import HTTPJSONTarget, get_by_path
from llm_redteam.targets.mock import MockTarget
from llm_redteam.targets.ollama import OllamaTarget
from llm_redteam.targets.openai_compatible import OpenAICompatibleTarget


def _config(target_type: str = "mock", **kwargs: Any) -> TargetConfig:
    kwargs.setdefault("name", "unit-target")
    return TargetConfig(type=target_type, **kwargs)


def _messages() -> list[Message]:
    return [
        Message(role="system", content="system guardrails"),
        Message(role="user", content="placeholder question"),
    ]


# --- MockTarget -----------------------------------------------------------


async def test_mock_target_cycles_responses() -> None:
    target = MockTarget(_config(params={"responses": ["a", "b"]}))
    results = [await target.send(_messages()) for _ in range(3)]
    assert [r.content for r in results] == ["a", "b", "a"]
    assert results[0].usage is not None
    assert results[0].usage["total_tokens"] > 0
    assert results[0].raw == {"mock": True, "mode": "cycle"}


async def test_mock_target_modes() -> None:
    echo = MockTarget(_config(params={"mode": "echo"}))
    assert (await echo.send(_messages())).content == "placeholder question"

    refuse = MockTarget(_config(params={"mode": "refuse"}))
    assert "cannot" in (await refuse.send(_messages())).content.lower()

    keyword = MockTarget(
        _config(params={"keyword_responses": {"secret-word": "matched"}})
    )
    no_keyword = await keyword.send(_messages())
    assert "mock" in no_keyword.content.lower()
    messages = [Message(role="user", content="contains secret-word inside")]
    assert (await keyword.send(messages)).content == "matched"

    default = MockTarget(_config(params={}))
    assert "mock target" in (await default.send(messages)).content.lower()


# --- OpenAI-compatible ----------------------------------------------------


async def test_openai_compatible_target_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_TEST_KEY", "sk-test-value")
    config = _config(
        "openai_compatible",
        model="gpt-test",
        base_url="https://example.test/v1",
        api_key_env="OPENAI_TEST_KEY",
        params={"extra": {"temperature": 0}},
    )
    target = OpenAICompatibleTarget(config)
    with respx.mock(assert_all_called=False) as router:
        route = router.post(
            "https://example.test/v1/chat/completions"
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": "hello back"}}],
                    "usage": {"total_tokens": 12},
                },
            )
        )
        response = await target.send(_messages())

    assert route.called
    request = route.calls.last.request
    assert request.headers["authorization"] == "Bearer sk-test-value"
    body_json = request.read()
    import json

    body = json.loads(body_json)
    assert body["model"] == "gpt-test"
    assert len(body["messages"]) == 2
    assert response.content == "hello back"
    assert response.usage == {"total_tokens": 12}
    assert response.target_name == "unit-target"
    await target.aclose()


async def test_openai_compatible_target_retries() -> None:
    config = _config(
        "openai_compatible",
        model="gpt-test",
        base_url="https://example.test/v1",
        params={"max_retries": 1, "retry_delay": 0},
    )
    target = OpenAICompatibleTarget(config)
    with respx.mock(assert_all_called=False) as router:
        router.post("https://example.test/v1/chat/completions").mock(
            side_effect=[
                httpx.Response(500, text="boom"),
                httpx.Response(
                    200, json={"choices": [{"message": {"content": "ok"}}]}
                ),
            ]
        )
        response = await target.send(_messages())
    assert response.content == "ok"


async def test_openai_compatible_target_non_retryable_error() -> None:
    config = _config(
        "openai_compatible",
        model="gpt-test",
        base_url="https://example.test/v1",
        params={"max_retries": 2, "retry_delay": 0},
    )
    target = OpenAICompatibleTarget(config)
    with respx.mock(assert_all_called=False) as router:
        router.post("https://example.test/v1/chat/completions").mock(
            return_value=httpx.Response(404, text="missing")
        )
        with pytest.raises(TargetError, match="HTTP 404"):
            await target.send(_messages())


async def test_openai_compatible_target_bad_shape() -> None:
    config = _config(
        "openai_compatible", model="g", base_url="https://example.test/v1"
    )
    target = OpenAICompatibleTarget(config)
    with respx.mock(assert_all_called=False) as router:
        router.post("https://example.test/v1/chat/completions").mock(
            return_value=httpx.Response(200, json={"unexpected": True})
        )
        with pytest.raises(TargetError, match="response shape"):
            await target.send(_messages())


# --- Anthropic ------------------------------------------------------------


async def test_anthropic_target(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_TEST_KEY", "anth-secret")
    config = _config(
        "anthropic",
        model="claude-test",
        base_url="https://anthropic.example.test",
        api_key_env="ANTHROPIC_TEST_KEY",
        params={"max_tokens": 64},
    )
    target = AnthropicTarget(config)
    with respx.mock(assert_all_called=False) as router:
        route = router.post(
            "https://anthropic.example.test/v1/messages"
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "content": [
                        {"type": "text", "text": "parsed "},
                        {"type": "text", "text": "reply"},
                        {"type": "thinking", "text": "ignored"},
                    ],
                    "usage": {"input_tokens": 3},
                },
            )
        )
        response = await target.send(_messages())

    request = route.calls.last.request
    import json

    body = json.loads(request.read())
    assert body["system"] == "system guardrails"
    assert all(msg["role"] != "system" for msg in body["messages"])
    assert body["max_tokens"] == 64
    assert request.headers["x-api-key"] == "anth-secret"
    assert response.content == "parsed reply"
    assert response.usage == {"input_tokens": 3}


async def test_anthropic_target_missing_content() -> None:
    config = _config("anthropic", model="c", base_url="https://a.example.test")
    target = AnthropicTarget(config)
    with respx.mock(assert_all_called=False) as router:
        router.post("https://a.example.test/v1/messages").mock(
            return_value=httpx.Response(200, json={"nope": 1})
        )
        with pytest.raises(TargetError, match="content"):
            await target.send(_messages())


# --- Ollama ---------------------------------------------------------------


async def test_ollama_target() -> None:
    config = _config(
        "ollama", model="llama-test", base_url="http://ollama.local:11343"
    )
    target = OllamaTarget(config)
    with respx.mock(assert_all_called=False) as router:
        route = router.post("http://ollama.local:11343/api/chat").mock(
            return_value=httpx.Response(
                200,
                json={
                    "message": {"content": "local reply"},
                    "prompt_eval_count": 4,
                    "eval_count": 2,
                },
            )
        )
        response = await target.send(_messages())
    assert route.called
    assert response.content == "local reply"
    assert response.usage is not None
    assert response.usage["total_tokens"] == 6


async def test_ollama_target_bad_shape() -> None:
    config = _config("ollama", model="x", base_url="http://ollama-bad:11343")
    target = OllamaTarget(config)
    with respx.mock(assert_all_called=False) as router:
        router.post("http://ollama-bad:11343/api/chat").mock(
            return_value=httpx.Response(200, json={})
        )
        with pytest.raises(TargetError, match="response shape"):
            await target.send(_messages())


# --- Generic HTTP/JSON ----------------------------------------------------


async def test_http_json_target_templating_and_path() -> None:
    config = _config(
        "http_json",
        params={
            "url": "https://gateway.example.test/infer",
            "body": {
                "q": "{{last_user}}",
                "history": "{{messages}}",
                "model": "{{model}}",
            },
            "content_path": "result.0.text",
            "usage_path": "meta.usage",
        },
        model="custom",
    )
    target = HTTPJSONTarget(config)
    with respx.mock(assert_all_called=False) as router:
        route = router.post("https://gateway.example.test/infer").mock(
            return_value=httpx.Response(
                200,
                json={
                    "result": [{"text": "gateway ok"}],
                    "meta": {"usage": {"total": 9}},
                },
            )
        )
        response = await target.send(_messages())

    import json

    body = json.loads(route.calls.last.request.read())
    assert body["q"] == "placeholder question"
    assert json.loads(body["history"])[0]["role"] == "system"
    assert body["model"] == "custom"
    assert response.content == "gateway ok"
    assert response.usage == {"total": 9}


async def test_http_json_target_error_path_and_base_url() -> None:
    config = _config(
        "http_json",
        base_url="https://gw.example.test",
        params={
            "path": "v2/ask",
            "body": {"q": "{{last_user}}"},
            "content_path": "data",
            "error_path": "error.message",
        },
    )
    target = HTTPJSONTarget(config)
    with respx.mock(assert_all_called=False) as router:
        router.post("https://gw.example.test/v2/ask").mock(
            return_value=httpx.Response(
                200, json={"error": {"message": "blocked by gateway"}}
            )
        )
        response = await target.send(_messages())
    assert response.error == "blocked by gateway"


async def test_http_json_target_requires_endpoint() -> None:
    target = HTTPJSONTarget(_config("http_json", params={"body": {}}))
    with pytest.raises(TargetError, match="params.url"):
        await target.send(_messages())


def test_get_by_path() -> None:
    data = {"a": {"b": [{"c": 1}, {"c": 2}]}}
    assert get_by_path(data, "a.b.1.c") == 2
    assert get_by_path(data, "") is data
    with pytest.raises(TargetError):
        get_by_path(data, "a.b.5.c")
    with pytest.raises(TargetError):
        get_by_path(data, "a.b.x.c")
    with pytest.raises(TargetError):
        get_by_path({"a": 1}, "a.b")


def test_read_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    assert read_api_key(_config()) is None
    monkeypatch.delenv("SOME_KEY", raising=False)
    missing = _config(api_key_env="SOME_KEY")
    assert read_api_key(missing) is None
    monkeypatch.setenv("SOME_KEY", "present")
    assert read_api_key(missing) == "present"
