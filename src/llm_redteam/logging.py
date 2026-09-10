"""Logging helpers with mandatory secret redaction.

Credentials must never appear in logs. :func:`redact` recursively masks
sensitive mapping keys and common credential patterns inside strings, and
:class:`RedactingFormatter` applies the same masking to formatted log
records.
"""

from __future__ import annotations

import logging
import re
from typing import Any

#: Mapping keys whose values are always masked (compared case-insensitively).
SENSITIVE_KEYS: frozenset[str] = frozenset(
    {
        "api_key",
        "apikey",
        "authorization",
        "token",
        "access_token",
        "refresh_token",
        "secret",
        "password",
        "passwd",
    }
)

#: Common credential shapes that must never survive in a log line.
_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"sk-[A-Za-z0-9_\-]{10,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]{10,}"),
    re.compile(r"(?i)(api[_-]?key|authorization|token)(\s*[:=]\s*)(\S{6,})"),
)

MASK = "***REDACTED***"


def redact(value: Any) -> Any:
    """Recursively mask sensitive data inside mappings, lists and strings.

    The result is always safe to log or embed in a report. Non-sensitive
    values are returned unchanged.
    """
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if isinstance(key, str) and key.lower() in SENSITIVE_KEYS:
                redacted[key] = MASK
            else:
                redacted[key] = redact(item)
        return redacted
    if isinstance(value, list | tuple | set):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return _redact_string(value)
    return value


def _redact_string(text: str) -> str:
    masked = text
    for pattern in _SECRET_PATTERNS:
        if pattern.groups >= 3:  # key: value style - preserve the key name
            masked = pattern.sub(lambda m: f"{m.group(1)}{m.group(2)}{MASK}", masked)
        else:
            masked = pattern.sub(MASK, masked)
    return masked


class RedactingFormatter(logging.Formatter):
    """Logging formatter that masks secrets in every formatted message."""

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        rendered = super().format(record)
        return _redact_string(rendered)


_CONFIGURED = False


def configure_logging(level: int | str = logging.INFO) -> None:
    """Configure the root LRTK logger exactly once with a redacting handler."""
    global _CONFIGURED
    if _CONFIGURED:
        logging.getLogger("llm_redteam").setLevel(level)
        return
    handler = logging.StreamHandler()
    handler.setFormatter(
        RedactingFormatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s")
    )
    root = logging.getLogger("llm_redteam")
    root.addHandler(handler)
    root.setLevel(level)
    root.propagate = False
    _CONFIGURED = True


def get_logger(name: str = "llm_redteam") -> logging.Logger:
    """Return a child logger under the ``llm_redteam`` namespace."""
    if not name.startswith("llm_redteam"):
        name = f"llm_redteam.{name}"
    return logging.getLogger(name)
