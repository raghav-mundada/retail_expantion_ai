from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    gemini_api_key: str = ""
    census_api_key: str = ""
    tinyfish_api_key: str = ""
    environment: str = "development"

    # Supabase (optional — for result persistence)
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_key: str = ""

    # Default analysis radius in miles
    default_radius_miles: float = 5.0

    model_config = ConfigDict(env_file=".env", extra="ignore")


@lru_cache()
def get_settings() -> Settings:
    return Settings()
