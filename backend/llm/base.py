"""LLM client protocol and JSON parsing utilities."""

import json
import logging
import re
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class LLMClient(Protocol):
    name: str

    async def complete_json(
        self,
        *,
        system: str,
        user: str,
        schema_hint: str,
        temperature: float = 0.2,
        max_tokens: int = 1500,
    ) -> Any: ...


def extract_and_parse_json(text: str) -> Any:
    """Extract and parse JSON from LLM output, handling markdown fences and stray text."""
    if not text or not isinstance(text, str):
        raise ValueError("Empty or invalid LLM response string")

    cleaned = text.strip()

    # 1. Strip markdown code fences if present
    fence_pattern = r"^```(?:json)?\s*\n?(.*?)\n?```$"
    m = re.match(fence_pattern, cleaned, re.DOTALL | re.IGNORECASE)
    if m:
        cleaned = m.group(1).strip()

    # 2. Try direct JSON parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # 3. Locate first { or [ and matching last } or ]
    start_brace = cleaned.find("{")
    start_bracket = cleaned.find("[")

    if start_brace != -1 and (start_bracket == -1 or start_brace < start_bracket):
        end_brace = cleaned.rfind("}")
        if end_brace != -1:
            snippet = cleaned[start_brace : end_brace + 1]
            try:
                return json.loads(snippet)
            except json.JSONDecodeError as e:
                logger.debug("Failed parsing extracted object snippet: %s", e)

    elif start_bracket != -1:
        end_bracket = cleaned.rfind("]")
        if end_bracket != -1:
            snippet = cleaned[start_bracket : end_bracket + 1]
            try:
                return json.loads(snippet)
            except json.JSONDecodeError as e:
                logger.debug("Failed parsing extracted array snippet: %s", e)

    raise ValueError(f"Could not extract valid JSON from LLM response: {cleaned[:200]}...")
