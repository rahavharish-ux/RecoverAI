from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "RecoverAI"
    environment: str = "development"
    api_prefix: str = "/api"
    api_v1_prefix: str = "/api/v1"

    # SQLite by default for zero-friction local dev/test; point this at a
    # Postgres/Supabase URL for anything beyond a single developer's machine.
    # Models avoid dialect-specific types so that switch is config-only.
    database_url: str = "sqlite:///./recoverai_dev.db"
    auto_create_tables: bool = True
    supabase_url: str = ""
    supabase_key: str = ""

    cors_origins: list[str] = ["http://localhost:5173"]

    # --- Deterministic policy (see app/domain/policy.py) ---
    max_retry_attempts: int = 3
    retry_cooldown_hours: int = 24
    automated_actions_enabled: bool = True

    # --- Payment simulator (see app/integrations/payment_gateway.py) ---
    # Illustrative, configurable sandbox parameters — not measured or
    # validated against real-world recovery rates. Keyed by decline_code.
    simulator_retry_success_rates: dict[str, float] = {
        "insufficient_funds": 0.35,
        "card_declined": 0.25,
        "processor_error": 0.60,
    }
    simulator_random_seed: int | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
