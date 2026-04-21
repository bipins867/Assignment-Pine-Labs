"""
Application configuration loaded from environment variables via pydantic-settings.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Central configuration for the application."""

    # Application
    APP_ENV: str = "development"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    LOG_LEVEL: str = "info"

    # MySQL
    MYSQL_HOST: str = "db"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "payment_user"
    MYSQL_PASSWORD: str = "payment_pass_2026"
    MYSQL_DATABASE: str = "payment_db"
    MYSQL_TEST_DATABASE: str = "payment_test_db"

    # CORS
    CORS_ORIGINS: str = "*"

    # Reconciliation
    DEFAULT_STALE_AFTER_HOURS: int = 24

    @property
    def DATABASE_URL(self) -> str:
        from urllib.parse import quote_plus
        return (
            f"mysql+pymysql://{self.MYSQL_USER}:{quote_plus(self.MYSQL_PASSWORD)}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"
        )

    @property
    def TEST_DATABASE_URL(self) -> str:
        from urllib.parse import quote_plus
        return (
            f"mysql+pymysql://{self.MYSQL_USER}:{quote_plus(self.MYSQL_PASSWORD)}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_TEST_DATABASE}"
        )

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
