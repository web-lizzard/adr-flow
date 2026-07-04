"""LLM provider and response parsing errors."""

from datetime import datetime


class LlmProviderError(Exception):
    """Raised when an upstream LLM provider request fails."""

    def __init__(
        self,
        message: str,
        *,
        rate_limit_reset_at: datetime | None = None,
    ) -> None:
        super().__init__(message)
        self.rate_limit_reset_at = rate_limit_reset_at


class LlmParseError(Exception):
    """Raised when provider output cannot be parsed into ReviewResult."""
