"""Construct the configured ADR review service."""

from application.logging import get_logger
from application.services.adr_review_service import AdrReviewService
from infrastructure.config import Settings
from infrastructure.llm.fake_completion import FakeLlmCompletionPort
from infrastructure.llm.openai_sdk_client import OpenAiSdkCompletionClient

_logger = get_logger(__name__)
_OPENROUTER_DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"


def build_adr_review_service(settings: Settings) -> AdrReviewService:
    if settings.llm_provider == "fake":
        completion_port = FakeLlmCompletionPort()
    elif settings.llm_provider == "openai_compatible":
        if settings.llm_base_url is None:
            msg = "LLM_BASE_URL is required for openai_compatible provider"
            raise ValueError(msg)
        completion_port = OpenAiSdkCompletionClient(
            provider="openai_compatible",
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            timeout_seconds=settings.llm_timeout_seconds,
            base_url=settings.llm_base_url,
        )
    else:
        if settings.llm_api_key is None:
            msg = "LLM_API_KEY is required for openrouter provider"
            raise ValueError(msg)
        completion_port = OpenAiSdkCompletionClient(
            provider="openrouter",
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            timeout_seconds=settings.llm_timeout_seconds,
            base_url=settings.llm_base_url or _OPENROUTER_DEFAULT_BASE_URL,
        )

    _logger.info(
        "llm.reviewer_built",
        provider=settings.llm_provider,
        model=settings.llm_model,
    )
    return AdrReviewService(completion_port)
