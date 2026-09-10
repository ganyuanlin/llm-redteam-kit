"""Target adapters for mock, OpenAI-compatible, Anthropic, Ollama and HTTP JSON."""

from llm_redteam.targets import (
    anthropic,
    http_json,
    mock,
    ollama,
    openai_compatible,
)
from llm_redteam.targets.base import Target, read_api_key

__all__ = [
    "Target",
    "anthropic",
    "http_json",
    "mock",
    "ollama",
    "openai_compatible",
    "read_api_key",
]
