"""Structlog configuration for the backend process."""

import logging
import re
import sys

import structlog
from structlog.typing import EventDict, WrappedLogger

_configured = False
_last_config: tuple[bool, str] | None = None

_SERVER_LOGGER_NAMES = (
    "uvicorn",
    "uvicorn.error",
    "uvicorn.access",
    "uvicorn.asgi",
    "fastapi",
)

_FOREIGN_EVENT_PREFIXES: tuple[tuple[str, str], ...] = (
    ("Started reloader process", "server.reloader_started"),
    ("Started server process", "server.process_started"),
    ("Finished server process", "server.process_finished"),
    ("Will watch for changes", "server.reload_watching"),
    ("Waiting for application startup", "server.startup_waiting"),
    ("Application startup complete", "server.startup_complete"),
    ("Application startup failed", "server.startup_failed"),
    ("Waiting for application shutdown", "server.shutdown_waiting"),
    ("Application shutdown complete", "server.shutdown_complete"),
    ("Application shutdown failed", "server.shutdown_failed"),
    ("Shutting down", "server.shutdown_started"),
    ("Uvicorn running on", "server.listening"),
)

_PROCESS_STARTED_RE = re.compile(r"Started server process \[(\d+)\]")


def normalize_foreign_server_event(
    _logger: WrappedLogger, _method_name: str, event_dict: EventDict
) -> EventDict:
    """Map uvicorn/fastapi stdlib messages to hierarchical event names."""
    if event_dict.get("_from_structlog"):
        return event_dict

    record = event_dict.get("_record")
    message = event_dict.get("event")
    if record is None or not isinstance(message, str):
        return event_dict

    if not record.name.startswith("uvicorn") and record.name != "fastapi":
        return event_dict

    for prefix, event_name in _FOREIGN_EVENT_PREFIXES:
        if message.startswith(prefix):
            event_dict["event"] = event_name
            break

    event = event_dict.get("event")
    if event == "server.listening":
        _, _, url = message.partition(" on ")
        if url:
            event_dict["url"] = url
    elif event == "server.process_started":
        match = _PROCESS_STARTED_RE.match(message)
        if match:
            event_dict["pid"] = int(match.group(1))

    return event_dict


def _harmonize_server_loggers() -> None:
    """Route uvicorn/fastapi loggers through the structlog root handler."""
    for name in _SERVER_LOGGER_NAMES:
        server_logger = logging.getLogger(name)
        server_logger.handlers.clear()
        server_logger.propagate = True


def configure_logging(*, log_json: bool, log_level: str) -> None:
    """Configure structlog and stdlib logging (idempotent for identical settings)."""
    global _configured, _last_config

    normalized_level = log_level.upper()
    config_key = (log_json, normalized_level)
    if _configured and _last_config == config_key:
        _harmonize_server_loggers()
        return

    level = getattr(logging, normalized_level, logging.INFO)

    foreign_pre_chain: list[structlog.types.Processor] = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        normalize_foreign_server_event,
    ]

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ]

    structlog.configure(
        processors=shared_processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    renderer: structlog.types.Processor = (
        structlog.processors.JSONRenderer()
        if log_json
        else structlog.dev.ConsoleRenderer(colors=True)
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=foreign_pre_chain,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    _harmonize_server_loggers()

    _configured = True
    _last_config = config_key
