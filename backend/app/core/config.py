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
    # Permissive by default ("*" = no restriction) since the real deployment
    # hostname isn't known ahead of time and enforcing the wrong value would
    # break the app outright. Set to the actual deployed host(s) via env var
    # (JSON array, same convention as cors_origins) once known — see
    # app/main.py's TrustedHostMiddleware.
    trusted_hosts: list[str] = ["*"]
    # Hard caps for the lightweight hardening in app/main.py — generous
    # enough that no legitimate request is ever affected.
    max_request_body_bytes: int = 262_144  # 256 KB

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

    # --- ML (see app/ml/, app/services/prediction_service.py) ---
    # The directory trained model artifacts are loaded from (see
    # training/train.py, which writes here).
    ml_artifact_dir: str = "./ml_artifacts"

    # Deterministic, configured action costs (simulated processor/ops cost
    # in cents) — expected-value ranking uses these; the model never
    # invents a cost of its own. Illustrative, not measured.
    action_costs_cents: dict[str, int] = {
        "retry_payment": 25,
        "request_method_update": 10,
        "escalate": 500,
    }

    # --- Agent (see app/agent/, app/services/agent_service.py) ---
    # Never hardcode a key: this reads from the ANTHROPIC_API_KEY env var
    # (or backend/.env). Empty/unset -> the deterministic engine is used
    # automatically, and the system is fully functional without it.
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-5"
    anthropic_api_base: str = "https://api.anthropic.com"
    anthropic_timeout_seconds: float = 30.0

    # Hard cap on tool-call turns within a single LLM decision — the loop
    # is forced to a final decision (or fails over to the deterministic
    # engine) once this is reached. Never unbounded.
    max_agent_tool_calls: int = 6
    # Hard cap on DECIDE calls per case — once reached, further automated
    # decisions are refused and the case must be escalated by a human.
    max_agent_decisions_per_case: int = 5

    # Deterministic thresholds that force requires_human_review=True
    # regardless of what a provider (LLM or deterministic) itself decided —
    # a provider's own judgment is never sufficient authorization on its
    # own for these. Illustrative configuration, not measured.
    human_review_amount_threshold_cents: int = 10000
    human_review_confidence_floor: float = 0.40
    human_review_repeated_failure_threshold: int = 2


@lru_cache
def get_settings() -> Settings:
    return Settings()
