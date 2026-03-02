from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Application
    app_name: str = "Inventory Service"
    app_version: str = "1.0.0"
    debug: bool = False

    # Database
    database_url: str = "postgresql+asyncpg://inventory_user:inventory_pass@db:5432/inventory_db"

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # API Security
    api_key: str = "sk_test_inventory_change_me"

    # Rate Limiting
    rate_limit_per_minute: int = 60

    # Reservation Settings
    reservation_ttl_minutes: int = 15

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


settings = Settings()
