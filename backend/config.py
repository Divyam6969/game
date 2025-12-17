import os
from functools import lru_cache


class Settings:
    """Application configuration loaded from environment variables.

    Designed to work nicely with Docker Compose and local development.
    """

    PROJECT_NAME: str = "Game Leaderboard"

    # Database
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "leaderboard")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "leaderboard")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "leaderboard")
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT: str = os.getenv("POSTGRES_PORT", "5432")

    # Redis
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))

    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me-in-prod")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
    )

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:"
            f"{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:"
            f"{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


@lru_cache()
def get_settings() -> Settings:
    return Settings()


