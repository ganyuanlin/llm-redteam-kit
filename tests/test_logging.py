"""Tests for secret redaction and logging configuration."""

from __future__ import annotations

import logging

from llm_redteam.logging import (
    MASK,
    RedactingFormatter,
    configure_logging,
    get_logger,
    redact,
)


def test_redact_mapping_keys_recursively() -> None:
    payload = {
        "api_key": "sk-123",
        "nested": {"Authorization": "Bearer abcdef123456"},
        "ok": [{"token": "deadbeef"}, {"keep": "visible"}],
        " untouched ": "value",
    }
    redacted = redact(payload)
    assert redacted["api_key"] == MASK
    assert redacted["nested"]["Authorization"] == MASK
    assert redacted["ok"][0]["token"] == MASK
    assert redacted["ok"][1]["keep"] == "visible"
    assert redact("plain") == "plain"
    assert redact(42) == 42


def test_redact_credential_shapes_in_strings() -> None:
    assert "sk-abcdef123456" not in redact("use sk-abcdef123456 now")
    assert "Bearer abcdefghijklmnop" not in redact("auth Bearer abcdefghijklmnop")
    masked = redact("api_key=some-long-value-here")
    assert MASK in masked and "some-long-value" not in masked


def test_redacting_formatter_outputs_masked_text() -> None:
    formatter = RedactingFormatter("%(name)s %(message)s")
    record = logging.LogRecord(
        "llm_redteam.test",
        logging.INFO,
        __file__,
        1,
        "header sk-abcdef123456 trailer",
        (),
        None,
    )
    rendered = formatter.format(record)
    assert rendered.startswith("llm_redteam.test")
    assert "sk-abcdef123456" not in rendered
    assert MASK in rendered


def test_configure_logging_is_idempotent() -> None:
    configure_logging("INFO")
    configure_logging("WARNING")
    logger = logging.getLogger("llm_redteam")
    redacting = [
        handler
        for handler in logger.handlers
        if isinstance(handler.formatter, RedactingFormatter)
    ]
    assert len(redacting) == 1
    assert logger.level == logging.WARNING


def test_get_logger_namespacing() -> None:
    assert get_logger("child").name == "llm_redteam.child"
    assert get_logger("llm_redteam.already").name == "llm_redteam.already"
