"""Disk cache for LLM completion calls keyed by prompt hash."""

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from backend.config import settings

logger = logging.getLogger(__name__)


class LLMCache:
    def __init__(self, cache_dir: Path | None = None):
        self.cache_dir = cache_dir or (settings.project_root / settings.LLM_CACHE_DIR)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _compute_key(
        self,
        provider: str,
        model: str,
        system: str,
        user: str,
        temperature: float,
    ) -> str:
        content = f"{provider}:{model}:{temperature}:{system}:{user}"
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def get(
        self,
        provider: str,
        model: str,
        system: str,
        user: str,
        temperature: float = 0.2,
    ) -> Any | None:
        key = self._compute_key(provider, model, system, user, temperature)
        file_path = self.cache_dir / f"{key}.json"
        if file_path.exists():
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
                logger.debug("LLM cache hit for key %s", key[:8])
                return data
            except Exception as e:
                logger.warning("Error reading LLM cache %s: %s", key, e)
        return None

    def set(
        self,
        provider: str,
        model: str,
        system: str,
        user: str,
        data: Any,
        temperature: float = 0.2,
    ):
        key = self._compute_key(provider, model, system, user, temperature)
        file_path = self.cache_dir / f"{key}.json"
        try:
            file_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning("Error writing LLM cache %s: %s", key, e)


llm_cache = LLMCache()
