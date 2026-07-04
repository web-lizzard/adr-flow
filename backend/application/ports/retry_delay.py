"""Port for computing retry delays between failed attempts."""

from typing import Protocol


class RetryDelayPort(Protocol):
    def compute_delay(
        self,
        attempt_index: int,
        *,
        base_seconds: float,
        error: Exception,
    ) -> float: ...


class ExponentialBackoff:
    """Simple exponential backoff without provider-specific intelligence."""

    def compute_delay(
        self,
        attempt_index: int,
        *,
        base_seconds: float,
        error: Exception,
    ) -> float:
        del error
        return base_seconds * (2**attempt_index)
