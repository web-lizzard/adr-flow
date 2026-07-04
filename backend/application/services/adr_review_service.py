"""ADR AI review orchestration."""

import asyncio
from datetime import UTC, datetime
from typing import TypeVar

from application.logging import get_logger
from application.ports.llm_completion import ChatMessage, LlmCompletionPort
from application.review_quality import validate_review_result
from domain.errors import AdrReviewFailedError
from domain.adr.required_sections import (
    ParsedAdrSections,
    SectionName,
    find_missing_or_empty_sections,
    parse_adr_sections,
)
from domain.adr.review_instructions import (
    build_cross_section_system_prompt,
    build_cross_section_user_message,
    build_section_system_prompt,
    build_section_user_message,
)
from domain.adr.review_llm_schema import (
    CrossSectionReviewPayload,
    SectionReviewPayload,
    merge_review_results,
)
from domain.adr.static_review import synthesize_static_review
from domain.adr.value_objects import ReviewResult

from infrastructure.llm.rate_limit import retry_delay_seconds

_logger = get_logger(__name__)

_ResponseModel = TypeVar(
    "_ResponseModel",
    SectionReviewPayload,
    CrossSectionReviewPayload,
)


class AdrReviewService:
    def __init__(
        self,
        completion_port: LlmCompletionPort,
        *,
        review_llm_attempts_per_call: int = 2,
        review_llm_retry_base_seconds: float = 2.0,
    ) -> None:
        self._completion_port = completion_port
        self._review_llm_attempts_per_call = review_llm_attempts_per_call
        self._review_llm_retry_base_seconds = review_llm_retry_base_seconds

    async def review_adr(
        self,
        markdown: str,
        *,
        validation_feedback: tuple[str, ...] = (),
    ) -> ReviewResult:
        # validation_feedback is retained for handler compatibility; unused in MVP.
        del validation_feedback

        static_annotations, static_ratings = synthesize_static_review(markdown)
        gaps = find_missing_or_empty_sections(markdown)
        parsed = parse_adr_sections(markdown)
        present_sections = tuple(
            section for section in SectionName if section not in gaps
        )

        section_payloads: list[SectionReviewPayload] = []
        cross_payload: CrossSectionReviewPayload | None = None

        try:
            async with asyncio.TaskGroup() as task_group:
                section_tasks = {
                    section: task_group.create_task(
                        self._review_section(section, parsed, markdown),
                        name=f"adr-review:{section.value}",
                    )
                    for section in present_sections
                }
                cross_task = None
                if SectionName.DECISION not in gaps and SectionName.STATUS not in gaps:
                    cross_task = task_group.create_task(
                        self._review_cross_section(markdown),
                        name="adr-review:cross-section",
                    )
        except ExceptionGroup as error_group:
            for exc in error_group.exceptions:
                if isinstance(exc, AdrReviewFailedError):
                    raise exc
            raise AdrReviewFailedError(str(error_group.exceptions[0])) from error_group

        section_payloads = [task.result() for task in section_tasks.values()]
        if cross_task is not None:
            cross_payload = cross_task.result()
        else:
            cross_payload = CrossSectionReviewPayload()

        reviewed_at = datetime.now(UTC)
        result = merge_review_results(
            static_annotations,
            static_ratings,
            tuple(section_payloads),
            cross_payload,
            markdown=markdown,
            reviewed_at=reviewed_at,
        )

        validation = validate_review_result(markdown, result)
        if not validation.passed:
            _logger.warning(
                "adr_review.validation_failed",
                failures=validation.failures,
            )
            raise AdrReviewFailedError(
                "Merged review result failed validation: "
                + "; ".join(validation.failures)
            )

        return result

    async def _review_section(
        self,
        section: SectionName,
        parsed: ParsedAdrSections,
        markdown: str,
    ) -> SectionReviewPayload:
        body = parsed.body_for(section)
        if body is None:
            raise AdrReviewFailedError(
                f"Section {section.value} is present but has no body",
                section=section.value,
            )

        messages: list[ChatMessage] = [
            {"role": "system", "content": build_section_system_prompt(section)},
            {
                "role": "user",
                "content": build_section_user_message(
                    section,
                    body,
                    doc_markdown=markdown if section is SectionName.CONTEXT else None,
                ),
            },
        ]
        return await self._complete_with_retry(
            messages=messages,
            response_model=SectionReviewPayload,
            section=section.value,
        )

    async def _review_cross_section(self, markdown: str) -> CrossSectionReviewPayload:
        messages: list[ChatMessage] = [
            {"role": "system", "content": build_cross_section_system_prompt()},
            {"role": "user", "content": build_cross_section_user_message(markdown)},
        ]
        return await self._complete_with_retry(
            messages=messages,
            response_model=CrossSectionReviewPayload,
            section="cross-section",
        )

    async def _complete_with_retry(
        self,
        *,
        messages: list[ChatMessage],
        response_model: type[_ResponseModel],
        section: str,
    ) -> _ResponseModel:
        last_error: Exception | None = None
        for attempt_index in range(self._review_llm_attempts_per_call):
            try:
                return await self._completion_port.complete_structured(
                    messages=messages,
                    response_model=response_model,
                )
            except Exception as exc:
                last_error = exc
                if attempt_index + 1 >= self._review_llm_attempts_per_call:
                    break
                delay_seconds = retry_delay_seconds(
                    attempt_index,
                    base_seconds=self._review_llm_retry_base_seconds,
                    error=exc,
                )
                if delay_seconds > 0:
                    _logger.warning(
                        "adr_review.llm_call_retry_scheduled",
                        section=section,
                        attempt=attempt_index + 1,
                        max_attempts=self._review_llm_attempts_per_call,
                        delay_seconds=delay_seconds,
                        error=str(exc),
                    )
                    await asyncio.sleep(delay_seconds)

        raise AdrReviewFailedError(
            f"LLM review failed for {section} after "
            f"{self._review_llm_attempts_per_call} attempts: {last_error}",
            section=section,
        )
