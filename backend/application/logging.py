"""Application-layer logging API (no infrastructure imports)."""

import structlog


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a structlog logger bound to the given module name."""
    return structlog.get_logger(name)
