"""Configuration settings for A11y Pilot using pydantic-settings."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    LLM_PROVIDER: str = "mock"
    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-2.5-flash"
    OPENAI_COMPAT_BASE_URL: str | None = None
    OPENAI_COMPAT_API_KEY: str | None = None
    OPENAI_COMPAT_MODEL: str | None = None
    LLM_CACHE_DIR: str = "data/cache/llm"
    LLM_TIMEOUT_SECONDS: int = 40
    LLM_MAX_RETRIES: int = 2
    APP_HOST: str = "127.0.0.1"
    APP_PORT: int = 8000
    ALLOWED_LOCAL_HOSTS: str = "127.0.0.1:8000,localhost:8000,127.0.0.1:8001,localhost:8001"
    PAGE_LOAD_TIMEOUT_MS: int = 20000
    MAX_PAGE_BYTES: int = 5000000
    MAX_ISSUES_FOR_FIXING: int = 10
    MAX_RETRIES_PER_FIX: int = 2
    CONFIDENCE_THRESHOLD: float = 0.6
    MOCK_SCENARIO: str = "normal"  # normal | retry | revert

    @property
    def allowed_hosts_list(self) -> list[str]:
        return [h.strip() for h in self.ALLOWED_LOCAL_HOSTS.split(",") if h.strip()]

    @property
    def project_root(self) -> Path:
        return Path(__file__).resolve().parent.parent


settings = Settings()
