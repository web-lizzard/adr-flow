"""AdrReviewService orchestration tests."""

import asyncio
from datetime import UTC, datetime
from typing import TypeVar

import pytest
from pydantic import BaseModel

from application.ports.llm_completion import ChatMessage
from domain.adr.review_llm_schema import ReviewAnnotationPayload, ReviewPayload
from domain.adr.value_objects import ReviewAnnotationKind, ReviewResult
from infrastructure.llm.errors import LlmProviderError

T = TypeVar("T", bound=BaseModel)

_REVIEWED_AT = datetime(2026, 6, 18, 12, 0, tzinfo=UTC)


class RecordingCompletionPort:
    def __init__(self, *, payload: ReviewPayload) -> None:
        self._payload = payload
        self.messages: list[ChatMessage] = []

    async def complete_structured(
        self,
        *,
        messages: list[ChatMessage],
        response_model: type[T],
    ) -> T:
        self.messages = list(messages)
        return response_model.model_validate(self._payload.model_dump())


class FailingCompletionPort:
    async def complete_structured(
        self,
        *,
        messages: list[ChatMessage],
        response_model: type[T],
    ) -> T:
        raise LlmProviderError("provider down")


def test_review_adr_maps_valid_payload_to_review_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from application.services.adr_review_service import AdrReviewService

    markdown = "## Context\n\nWe need a store.\n"
    payload = ReviewPayload(
        annotations=(
            ReviewAnnotationPayload(
                kind=ReviewAnnotationKind.MISSING_SECTION,
                message="Missing Decision section",
                location="## Decision",
                suggestion="Document the chosen option.",
            ),
        )
    )
    port = RecordingCompletionPort(payload=payload)
    monkeypatch.setattr(
        "application.services.adr_review_service.datetime",
        type(
            "_FixedDatetime",
            (),
            {"now": staticmethod(lambda tz=None: _REVIEWED_AT)},
        ),
    )
    service = AdrReviewService(port)

    result = asyncio.run(service.review_adr(markdown))

    assert isinstance(result, ReviewResult)
    assert result.reviewed_content == markdown
    assert result.reviewed_at == _REVIEWED_AT
    assert len(result.annotations) == 1
    assert result.annotations[0].kind == ReviewAnnotationKind.MISSING_SECTION
    assert result.annotations[0].message == "Missing Decision section"


def test_review_adr_sends_system_and_user_messages() -> None:
    from application.services.adr_review_service import AdrReviewService

    markdown = "## Context\n\nBody.\n"
    payload = ReviewPayload(annotations=())
    port = RecordingCompletionPort(payload=payload)
    service = AdrReviewService(port)

    asyncio.run(service.review_adr(markdown))

    roles = [message["role"] for message in port.messages]
    assert roles == ["system", "user"]
    assert "Required sections" in port.messages[0]["content"]
    assert markdown in port.messages[1]["content"]


def test_review_adr_propagates_provider_error() -> None:
    from application.services.adr_review_service import AdrReviewService

    service = AdrReviewService(FailingCompletionPort())

    with pytest.raises(LlmProviderError, match="provider down"):
        asyncio.run(service.review_adr("## Context\n\nBody.\n"))


def test_review_adr_attaches_validation_feedback_to_user_message() -> None:
    from application.services.adr_review_service import AdrReviewService

    markdown = "## Context\n\nBody.\n"
    feedback = ("false negative: missing annotation for Decision",)
    payload = ReviewPayload(annotations=())
    port = RecordingCompletionPort(payload=payload)
    service = AdrReviewService(port)

    asyncio.run(service.review_adr(markdown, validation_feedback=feedback))

    user_content = port.messages[1]["content"]
    assert feedback[0] in user_content
    assert "static validation" in user_content.casefold()
