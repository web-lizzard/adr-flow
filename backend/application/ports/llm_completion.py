"""Transport-only LLM completion port."""

from typing import Protocol, TypeVar, TypedDict

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class ChatMessage(TypedDict):
    role: str
    content: str


class LlmCompletionPort(Protocol):
    async def complete_structured(
        self,
        *,
        messages: list[ChatMessage],
        response_model: type[T],
    ) -> T: ...
