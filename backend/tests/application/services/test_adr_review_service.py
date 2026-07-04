"""AdrReviewService parallel orchestration tests."""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import TypeVar

import pytest
from pydantic import BaseModel

from application.ports.llm_completion import ChatMessage
from domain.adr.required_sections import SectionName
from domain.adr.review_llm_schema import (
    CrossSectionReviewPayload,
    SectionReviewPayload,
)
from domain.adr.value_objects import ReviewAnnotationKind, ReviewResult
from domain.errors import RetryableInternalError
from infrastructure.llm.errors import LlmProviderError
from tests.review_quality.cases import load_fixture

T = TypeVar("T", bound=BaseModel)

_REVIEWED_AT = datetime(2026, 6, 18, 12, 0, tzinfo=UTC)


def _section_payload(section: SectionName, *, score: int = 4) -> SectionReviewPayload:
    return SectionReviewPayload(
        section=section,
        score=score,
        feedback=f"Solid {section.value} content.",
    )


def _cross_payload() -> CrossSectionReviewPayload:
    return CrossSectionReviewPayload(annotations=())


class RecordingCompletionPort:
    def __init__(self) -> None:
        self.call_count = 0
        self.messages_by_call: list[list[ChatMessage]] = []

    async def complete_structured(
        self,
        *,
        messages: list[ChatMessage],
        response_model: type[T],
    ) -> T:
        self.call_count += 1
        self.messages_by_call.append(list(messages))
        if response_model is SectionReviewPayload:
            section = _section_from_system_prompt(messages[0]["content"])
            return response_model.model_validate(_section_payload(section).model_dump())
        if response_model is CrossSectionReviewPayload:
            return response_model.model_validate(_cross_payload().model_dump())
        msg = f"Unexpected response model: {response_model}"
        raise TypeError(msg)


class FlakyCompletionPort:
    def __init__(self) -> None:
        self.call_count = 0
        self._failed_keys: set[str] = set()

    async def complete_structured(
        self,
        *,
        messages: list[ChatMessage],
        response_model: type[T],
    ) -> T:
        self.call_count += 1
        key = messages[0]["content"]
        if key not in self._failed_keys:
            self._failed_keys.add(key)
            raise LlmProviderError("transient failure")
        if response_model is SectionReviewPayload:
            section = _section_from_system_prompt(messages[0]["content"])
            return response_model.model_validate(_section_payload(section).model_dump())
        return response_model.model_validate(_cross_payload().model_dump())


class AlwaysFailingCompletionPort:
    def __init__(self) -> None:
        self.call_count = 0

    async def complete_structured(
        self,
        *,
        messages: list[ChatMessage],
        response_model: type[T],
    ) -> T:
        self.call_count += 1
        raise LlmProviderError("provider down")


def _section_from_system_prompt(system_content: str) -> SectionName:
    for section in SectionName:
        if f"ADR {section.value} section" in system_content:
            return section
    msg = "Could not determine section from system prompt"
    raise ValueError(msg)


def _patch_reviewed_at(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "application.services.adr_review_service.datetime",
        type(
            "_FixedDatetime",
            (),
            {"now": staticmethod(lambda tz=None: _REVIEWED_AT)},
        ),
    )


def test_static_gaps_produce_score_zero_ratings_without_llm_for_gap_sections(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from application.services.adr_review_service import AdrReviewService

    markdown = load_fixture("missing_context.md")
    port = RecordingCompletionPort()
    _patch_reviewed_at(monkeypatch)
    service = AdrReviewService(
        port,
        review_llm_attempts_per_call=2,
        review_llm_retry_base_seconds=0,
    )

    result = asyncio.run(service.review_adr(markdown))

    context_rating = next(
        rating
        for rating in result.section_ratings
        if rating.section is SectionName.CONTEXT
    )
    assert context_rating.score == 0
    assert context_rating.feedback == ""
    missing = [
        annotation
        for annotation in result.annotations
        if annotation.kind is ReviewAnnotationKind.MISSING_SECTION
    ]
    assert len(missing) == 1
    assert missing[0].location == "## Context"
    assert port.call_count == 5


def test_present_sections_invoke_parallel_llm_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from application.services.adr_review_service import AdrReviewService

    markdown = load_fixture("complete.md")
    port = RecordingCompletionPort()
    _patch_reviewed_at(monkeypatch)
    service = AdrReviewService(
        port,
        review_llm_attempts_per_call=2,
        review_llm_retry_base_seconds=0,
    )

    result = asyncio.run(service.review_adr(markdown))

    assert port.call_count == 6
    assert len(result.section_ratings) == 5
    assert all(rating.score >= 1 for rating in result.section_ratings)


def test_per_call_retry_succeeds_on_second_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from application.services.adr_review_service import AdrReviewService

    markdown = load_fixture("complete.md")
    port = FlakyCompletionPort()
    _patch_reviewed_at(monkeypatch)
    service = AdrReviewService(
        port,
        review_llm_attempts_per_call=2,
        review_llm_retry_base_seconds=0,
    )

    result = asyncio.run(service.review_adr(markdown))

    assert isinstance(result, ReviewResult)
    assert port.call_count == 12


def test_exhausted_per_call_retries_raise_retryable_internal_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from application.services.adr_review_service import AdrReviewService

    markdown = load_fixture("complete.md")
    port = AlwaysFailingCompletionPort()
    _patch_reviewed_at(monkeypatch)
    service = AdrReviewService(
        port,
        review_llm_attempts_per_call=2,
        review_llm_retry_base_seconds=0,
    )

    with pytest.raises(RetryableInternalError):
        asyncio.run(service.review_adr(markdown))

    assert port.call_count >= 2


def test_section_failure_after_retries_raises_without_partial_merge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from application.services.adr_review_service import AdrReviewService

    class ContextFailingPort(RecordingCompletionPort):
        async def complete_structured(
            self,
            *,
            messages: list[ChatMessage],
            response_model: type[T],
        ) -> T:
            if response_model is SectionReviewPayload:
                section = _section_from_system_prompt(messages[0]["content"])
                if section is SectionName.CONTEXT:
                    raise LlmProviderError("context review failed")
            return await super().complete_structured(
                messages=messages,
                response_model=response_model,
            )

    markdown = load_fixture("complete.md")
    port = ContextFailingPort()
    _patch_reviewed_at(monkeypatch)
    service = AdrReviewService(
        port,
        review_llm_attempts_per_call=2,
        review_llm_retry_base_seconds=0,
    )

    with pytest.raises(RetryableInternalError):
        asyncio.run(service.review_adr(markdown))


def test_per_call_retry_uses_exponential_backoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from application.services.adr_review_service import AdrReviewService

    markdown = load_fixture("complete.md")
    port = FlakyCompletionPort()
    _patch_reviewed_at(monkeypatch)
    sleeps: list[float] = []

    async def record_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr(
        "application.services.adr_review_service.asyncio.sleep",
        record_sleep,
    )
    service = AdrReviewService(
        port,
        review_llm_attempts_per_call=2,
        review_llm_retry_base_seconds=2.0,
    )

    result = asyncio.run(service.review_adr(markdown))

    assert isinstance(result, ReviewResult)
    assert sleeps == [2.0] * 6


def test_rate_limit_errors_wait_until_reset_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from application.services.adr_review_service import AdrReviewService

    now = datetime(2026, 7, 4, 16, 0, 0, tzinfo=UTC)
    reset_at = now + timedelta(seconds=15)

    class RateLimitedThenOkPort(FlakyCompletionPort):
        async def complete_structured(
            self,
            *,
            messages: list[ChatMessage],
            response_model: type[T],
        ) -> T:
            self.call_count += 1
            key = messages[0]["content"]
            if key not in self._failed_keys:
                self._failed_keys.add(key)
                raise LlmProviderError(
                    "LLM completion request failed: Error code: 429",
                    rate_limit_reset_at=reset_at,
                )
            if response_model is SectionReviewPayload:
                section = _section_from_system_prompt(messages[0]["content"])
                return response_model.model_validate(
                    _section_payload(section).model_dump(),
                )
            return response_model.model_validate(_cross_payload().model_dump())

    markdown = load_fixture("complete.md")
    port = RateLimitedThenOkPort()
    _patch_reviewed_at(monkeypatch)
    sleeps: list[float] = []

    async def record_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr(
        "application.services.adr_review_service.asyncio.sleep",
        record_sleep,
    )
    monkeypatch.setattr(
        "infrastructure.llm.rate_limit.random.uniform",
        lambda _low, _high: 2.0,
    )
    monkeypatch.setattr(
        "infrastructure.llm.rate_limit.datetime",
        type(
            "_FixedDatetime",
            (),
            {"now": staticmethod(lambda tz=None: now)},
        ),
    )
    from infrastructure.llm.rate_limit import LlmRetryDelay

    service = AdrReviewService(
        port,
        review_llm_attempts_per_call=2,
        review_llm_retry_base_seconds=2.0,
        retry_delay=LlmRetryDelay(),
    )

    asyncio.run(service.review_adr(markdown))

    assert all(delay == pytest.approx(17.0) for delay in sleeps)
    assert len(sleeps) == 6


def test_validation_failure_returns_result_without_raising(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from application.review_quality import ReviewValidationResult
    from application.services.adr_review_service import AdrReviewService

    markdown = load_fixture("complete.md")
    port = RecordingCompletionPort()
    _patch_reviewed_at(monkeypatch)
    service = AdrReviewService(
        port,
        review_llm_attempts_per_call=2,
        review_llm_retry_base_seconds=0,
    )

    monkeypatch.setattr(
        "application.services.adr_review_service.validate_review_result",
        lambda _markdown, _result: ReviewValidationResult(
            passed=False,
            failures=("expected 5 section ratings",),
        ),
    )

    result = asyncio.run(service.review_adr(markdown))

    assert isinstance(result, ReviewResult)
    assert len(result.section_ratings) == 5


def test_merged_complete_fixture_passes_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from application.services.adr_review_service import AdrReviewService
    from application.review_quality import validate_review_result

    markdown = load_fixture("complete.md")
    port = RecordingCompletionPort()
    _patch_reviewed_at(monkeypatch)
    service = AdrReviewService(
        port,
        review_llm_attempts_per_call=2,
        review_llm_retry_base_seconds=0,
    )

    result = asyncio.run(service.review_adr(markdown))

    validation = validate_review_result(markdown, result)
    assert validation.passed, validation.failures
