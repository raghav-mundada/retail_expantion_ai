from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    openai_api_key: str = ""
    census_api_key: str = ""
    tinyfish_api_key: str = ""
    geoapify_api_key: str = ""
    environment: str = "development"

    # Supabase (optional — for result persistence)
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_key: str = ""

    # Stripe billing
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_pro_monthly: str = ""
    stripe_price_pro_annual: str = ""

    # Frontend URL — used to build redirect URLs for Stripe sessions
    frontend_url: str = "http://localhost:5173"

    # Default analysis radius in miles
    default_radius_miles: float = 5.0

    # ── Analysis pipeline performance (blocking /api/analyze) ─────────────────
    # Tuned aggressively for sub-30s cold-path /api/analyze. On timeout any
    # individual agent falls back to deterministic proxies — analysis still returns.
    tinyfish_agent_timeout_seconds: int = 8
    tinyfish_search_http_timeout_seconds: int = 6
    # Wall-clock cap for all hotspot TinyFish work; on timeout → fast proxy hotspot.
    analysis_hotspot_total_budget_seconds: float = 12.0
    # Simulation timeout is only used on /api/simulate now — we can afford to be generous.
    analysis_simulation_openai_timeout_seconds: float = 26.0
    analysis_brand_narrative_timeout_seconds: float = 6.0
    analysis_brand_resolver_openai_timeout_seconds: float = 8.0

    model_config = ConfigDict(env_file=".env", extra="ignore")


@lru_cache()
def get_settings() -> Settings:
    return Settings()
