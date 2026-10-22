"""LLM provider factory."""

import logging

from backend.config import settings
from backend.llm.base import LLMClient
from backend.llm.mock import MockLLMClient

logger = logging.getLogger(__name__)

_client_instance = None


def get_llm() -> LLMClient:
    """Return configured LLMClient based on LLM_PROVIDER setting."""
    global _client_instance
    if _client_instance is not None:
        return _client_instance

    provider = settings.LLM_PROVIDER.lower().strip()

    if provider == "gemini":
        if not settings.GEMINI_API_KEY:
            logger.warning("GEMINI_API_KEY not set. Falling back to mock LLM.")
            _client_instance = MockLLMClient()
        else:
            from backend.llm.gemini import GeminiClient

            _client_instance = GeminiClient(
                api_key=settings.GEMINI_API_KEY,
                model=settings.GEMINI_MODEL,
            )
    elif provider == "openai_compat":
        if not settings.OPENAI_COMPAT_BASE_URL:
            logger.warning("OPENAI_COMPAT_BASE_URL not set. Falling back to mock LLM.")
            _client_instance = MockLLMClient()
        else:
            from backend.llm.openai_compat import OpenAICompatClient

            _client_instance = OpenAICompatClient(
                base_url=settings.OPENAI_COMPAT_BASE_URL,
                api_key=settings.OPENAI_COMPAT_API_KEY or "dummy",
                model=settings.OPENAI_COMPAT_MODEL or "gpt-4o-mini",
            )
    else:
        _client_instance = MockLLMClient()

    return _client_instance
