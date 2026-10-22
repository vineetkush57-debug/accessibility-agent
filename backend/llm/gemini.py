"""Gemini LLM client using httpx REST endpoints."""

import logging
from typing import Any

import httpx

from backend.config import settings
from backend.llm.base import extract_and_parse_json
from backend.llm.cache import llm_cache

logger = logging.getLogger(__name__)


class GeminiClient:
    name = "gemini"

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
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

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        payload = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"parts": [{"text": user}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
                "responseMimeType": "application/json",
            },
        }

        async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT_SECONDS) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                raise RuntimeError("No generation candidates returned from Gemini.")
            text = candidates[0]["content"]["parts"][0]["text"]

        parsed = extract_and_parse_json(text)
        llm_cache.set(self.name, self.model, system, user, parsed, temperature)
        return parsed
