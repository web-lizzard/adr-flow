"""LLM provider and response parsing errors."""


class LlmProviderError(Exception):
    """Raised when an upstream LLM provider request fails."""


class LlmParseError(Exception):
    """Raised when provider output cannot be parsed into ReviewResult."""
