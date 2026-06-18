"""Smoke tests for structlog configuration."""

import json
import logging

import pytest

import infrastructure.logging as infra_logging
from application.logging import get_logger
from infrastructure.logging import configure_logging


@pytest.fixture(autouse=True)
def _reset_logging_state() -> None:
    infra_logging._configured = False
    infra_logging._last_config = None
    logging.getLogger().handlers.clear()


def test_configure_logging_json_emits_parseable_event(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(log_json=True, log_level="INFO")
    logger = get_logger("test.logging")
    logger.info("test.event", key="value")

    captured = capsys.readouterr()
    lines = [line for line in captured.out.splitlines() if line.strip()]
    assert lines
    payload = json.loads(lines[-1])
    assert payload["event"] == "test.event"
    assert payload["key"] == "value"


def test_configure_logging_console_does_not_raise(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(log_json=False, log_level="INFO")
    logger = get_logger("test.logging")
    logger.info("test.console_event")

    assert capsys.readouterr().out
