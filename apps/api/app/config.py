from decimal import Decimal
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://jt:jt@localhost:5432/jt"
    test_database_url: str = "postgresql+asyncpg://jt:jt@localhost:5432/jt_test"

    inngest_dev: bool = True
    inngest_event_key: str | None = None
    inngest_signing_key: str | None = None

    anthropic_api_key: str | None = None
    llm_model_score: str = "claude-haiku-5-5"
    llm_model_extract: str = "claude-haiku-5-5"
    llm_model_classify_email: str = "claude-haiku-5-5"
    llm_model_tailor: str = "claude-sonnet-5-5"
    llm_model_answer: str = "claude-sonnet-5-5"
    llm_daily_budget_usd: Decimal = Decimal("1.00")
    score_top_k: int = 60

    ntfy_url: str = "https://ntfy.sh"
    ntfy_topic: str | None = None
    ntfy_token: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
