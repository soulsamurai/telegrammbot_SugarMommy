"""Конфигурация приложения из переменных окружения."""

from functools import lru_cache
from zoneinfo import ZoneInfo

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    bot_token: str = Field(alias="BOT_TOKEN")
    db_url: str = Field(
        validation_alias=AliasChoices("DB_URL", "DATABASE_URL"),
    )
    admin_ids: list[int] = Field(default_factory=list, alias="ADMIN_IDS")
    master_ids: list[int] = Field(default_factory=list, alias="MASTER_IDS")
    broadcast_rate_limit: int = Field(default=30, alias="BROADCAST_RATE_LIMIT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_json: bool = Field(default=True, alias="LOG_JSON")
    timezone: str = Field(default="Asia/Tashkent", alias="TIMEZONE")

    cancel_min_hours: int = 2
    confirm_visit_hours: int = 3
    unconfirmed_alert_hours: float = 1.5
    waitlist_offer_minutes: int = 15
    calendar_days_ahead: int = 14
    services_per_page: int = 8

    @field_validator("db_url", mode="before")
    @classmethod
    def normalize_db_url(cls, value: object) -> object:
        if value is None:
            return value
        url = str(value).strip()
        if url.startswith("postgres://"):
            return "postgresql+asyncpg://" + url.removeprefix("postgres://")
        if url.startswith("postgresql://"):
            return "postgresql+asyncpg://" + url.removeprefix("postgresql://")
        return url

    @field_validator("admin_ids", "master_ids", mode="before")
    @classmethod
    def parse_id_list(cls, value: object) -> list[int]:
        if value is None or value == "":
            return []
        if isinstance(value, list):
            return [int(x) for x in value]
        if isinstance(value, (int, float)):
            return [int(value)]
        parts = str(value).replace(";", ",").split(",")
        return [int(p.strip()) for p in parts if p.strip()]

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


@lru_cache
def get_settings() -> Settings:
    return Settings()
