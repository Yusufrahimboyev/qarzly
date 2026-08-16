"""Ilova sozlamalari (typed, validatsiyalangan).

Barcha konfiguratsiya shu yagona manbadan o'qiladi. `.env` fayl avtomatik
yuklanadi. Majburiy qiymatlar (masalan BOT_TOKEN) bo'lmasa, ilova ishga
tushishida aniq xatolik beradi — noto'g'ri holatda jimgina ishlab ketmaydi.
"""
from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Muhit o'zgaruvchilaridan (.env) o'qiladigan sozlamalar."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Telegram ---
    bot_token: SecretStr = Field(..., description="BotFather'dan olingan token")

    # --- Web / hosting ---
    port: int = Field(default=8080, ge=1, le=65535)
    render_external_url: str = Field(
        default="",
        description="Render.com tashqi URL (keep-alive va Mini App uchun).",
    )

    # --- Ma'lumotlar bazasi ---
    database_path: Path = Field(default=Path("data/bot.db"))

    # --- Logging ---
    log_level: str = Field(default="INFO")

    @field_validator("bot_token")
    @classmethod
    def _token_not_empty(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError(
                "BOT_TOKEN bo'sh. .env faylida to'g'ri token ko'rsating."
            )
        return value

    @property
    def token(self) -> str:
        """Tokenning ochiq (plaintext) qiymati."""
        return self.bot_token.get_secret_value()

    @property
    def web_app_url(self) -> str:
        """Telegram Mini App uchun to'liq URL (agar sozlangan bo'lsa)."""
        return self.render_external_url.rstrip("/")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Sozlamalarni bir marta o'qib, keshlaydi (singleton)."""
    return Settings()  # type: ignore[call-arg]
