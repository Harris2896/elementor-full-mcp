from pydantic import HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    wp_url: HttpUrl
    wp_api_key: str
    log_level: str = "info"
    http_timeout: int = 15
    openai_api_key: str = ""
    unsplash_access_key: str = ""


def load() -> Settings:
    return Settings()
