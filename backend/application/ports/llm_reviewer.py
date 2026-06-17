"""LLM reviewer port for async AI review."""

from typing import Protocol

from domain.adr.value_objects import ReviewResult


class LlmReviewer(Protocol):
    async def review(self, markdown: str) -> ReviewResult: ...
