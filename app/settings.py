"""Application settings loaded from environment."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/lead_scoring"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"

    app_env: str = "development"
    log_level: str = "INFO"
    batch_size_threshold: int = 20

    auto_outreach_tiers: str = "Hot,Hot-leaning Warm"

    scoring_config_path: str = "scoring_config.yaml"

    @property
    def auto_outreach_tier_set(self) -> set[str]:
        return {t.strip() for t in self.auto_outreach_tiers.split(",") if t.strip()}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
