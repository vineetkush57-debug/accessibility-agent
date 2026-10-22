"""OpenAI-compatible LLM client using httpx."""

import logging
from typing import Any

import httpx

from backend.config import settings
from backend.llm.base import extract_and_parse_json
from backend.llm.cache import llm_cache

logger = logging.getLogger(__name__)


class OpenAICompatClient:
    name = "openai_compat"

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str = "gpt-4o-mini",
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    async def complete_json(
        self,
        *,
        system: str,
        user: str,
        schema_hint: str,
        temperature: float = 0.2,
        max_tokens: int = 1500,
    ) -> Any:
        cached = llm_cache.get(self.name, self.model, system, user, temperature)
        if cached is not None:
            return cached

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }

        async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT_SECONDS) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            text = data["choices"][0]["message"]["content"]

        parsed = extract_and_parse_json(text)
        llm_cache.set(self.name, self.model, system, user, parsed, temperature)
        return parsed
