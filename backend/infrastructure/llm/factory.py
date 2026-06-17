"""Construct the configured LLM reviewer adapter."""

from application.ports.llm_reviewer import LlmReviewer
from infrastructure.config import Settings
from infrastructure.llm.fake_reviewer import FakeReviewer
from infrastructure.llm.openai_compatible import OpenAiCompatibleReviewer
from infrastructure.llm.openrouter import OpenRouterReviewer


def build_llm_reviewer(settings: Settings) -> LlmReviewer:
    if settings.llm_provider == "fake":
        return FakeReviewer()

    if settings.llm_provider == "openai_compatible":
        if settings.llm_base_url is None:
            msg = "LLM_BASE_URL is required for openai_compatible provider"
            raise ValueError(msg)
        return OpenAiCompatibleReviewer(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            timeout_seconds=settings.llm_timeout_seconds,
        )

    if settings.llm_api_key is None:
        msg = "LLM_API_KEY is required for openrouter provider"
        raise ValueError(msg)
    return OpenRouterReviewer(
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        timeout_seconds=settings.llm_timeout_seconds,
        base_url=settings.llm_base_url,
    )
