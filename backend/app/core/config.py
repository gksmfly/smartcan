# backend/app/core/config.py

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # .env에서 읽고, 없는 값은 환경변수에서 읽음
    model_config = SettingsConfigDict(
        env_file=".env",        # 여기 .env에 DATABASE_URL=Neon주소 써두면 됨
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "SmartCan Backend"

    # 반드시 .env 또는 환경변수에 있어야 하는 값
    DATABASE_URL: str

    BACKEND_CORS_ORIGINS: str = ""

    MQTT_BROKER_HOST: str = "localhost"
    MQTT_BROKER_PORT: int = 1883
    MQTT_CLIENT_ID: str = "smartcan-backend"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()