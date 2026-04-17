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

    # API Security (service-to-service)
    api_key: str = "sk_test_inventory_change_me"

    # Rate Limiting
    rate_limit_per_minute: int = 60

    # Ticket Reservation Settings
    ticket_reservation_ttl_minutes: int = 15
    expiry_check_interval_seconds: int = 30

    # KPI publishing for composer
    enable_kpi_endpoints: bool = True
    enable_kpi_event_logging: bool = True

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }


settings = Settings()
