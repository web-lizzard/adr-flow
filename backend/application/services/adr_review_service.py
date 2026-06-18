"""ADR AI review orchestration."""

from datetime import UTC, datetime

from application.ports.llm_completion import ChatMessage, LlmCompletionPort
from domain.adr.review_instructions import (
    build_review_system_prompt,
    build_review_user_message,
)
from domain.adr.review_llm_schema import ReviewPayload, to_review_result
from domain.adr.value_objects import ReviewResult


class AdrReviewService:
    def __init__(self, completion_port: LlmCompletionPort) -> None:
        self._completion_port = completion_port

    async def review_adr(
        self,
        markdown: str,
        *,
        validation_feedback: tuple[str, ...] = (),
    ) -> ReviewResult:
        messages: list[ChatMessage] = [
            {"role": "system", "content": build_review_system_prompt()},
            {
                "role": "user",
                "content": build_review_user_message(
                    markdown,
                    validation_feedback=validation_feedback,
                ),
            },
        ]
        payload = await self._completion_port.complete_structured(
            messages=messages,
            response_model=ReviewPayload,
        )
        reviewed_at = datetime.now(UTC)
        return to_review_result(payload, markdown=markdown, reviewed_at=reviewed_at)
