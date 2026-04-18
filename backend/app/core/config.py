from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    gemini_api_key: str = ""
    census_api_key: str = ""
    environment: str = "development"

    # Phoenix metro bounding box
    metro_name: str = "Phoenix, AZ"
    metro_state_fips: str = "04"
    metro_county_fips: str = "013"  # Maricopa County

    # Default analysis radius in miles
    default_radius_miles: float = 10.0

    model_config = {"env_file": ".env"}

@lru_cache()
def get_settings() -> Settings:
    return Settings()
