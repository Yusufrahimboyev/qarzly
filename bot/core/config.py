"""Ilova sozlamalari (typed, validatsiyalangan).

Barcha konfiguratsiya shu yagona manbadan o'qiladi. `.env` fayl avtomatik
yuklanadi. Majburiy qiymatlar (masalan BOT_TOKEN) bo'lmasa, ilova ishga
tushishida aniq xatolik beradi — noto'g'ri holatda jimgina ishlab ketmaydi.

Muhim: `ADMIN_IDS` bo'sh bo'lsa ilova ishga tushmaydi. Ochiq rejim faqat
`ALLOW_OPEN_ACCESS=true` deb ongli ravishda yoqilganda ishlaydi — deploy
paytida bitta o'zgaruvchi unutilishi mijozlar ma'lumotlarini ochib
qo'ymasligi kerak (fail-closed).
"""
from functools import lru_cache

from pydantic import Field, SecretStr, field_validator, model_validator
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
    admin_ids: list[int] | str = Field(
        default_factory=list,
        description="Bot adminlarining Telegram ID lari (vergul bilan ajratilgan)",
    )
    allow_open_access: bool = Field(
        default=False,
        description=(
            "Faqat development uchun: ADMIN_IDS bo'sh bo'lganda ham "
            "har qanday Telegram foydalanuvchisiga ruxsat beradi."
        ),
    )

    # --- Web / hosting ---
    port: int = Field(default=8080, ge=1, le=65535)
    render_external_url: str = Field(
        default="",
        description="Render.com tashqi URL (keep-alive va Mini App uchun).",
    )
    api_rate_limit_per_minute: int = Field(
        default=120,
        ge=1,
        le=10_000,
        description="Bitta foydalanuvchi/IP uchun daqiqadagi API so'rovlar chegarasi.",
    )
    init_data_max_age_seconds: int = Field(
        default=24 * 60 * 60,
        ge=60,
        le=7 * 24 * 60 * 60,
        description="Telegram initData'ning maksimal amal qilish muddati.",
    )

    # --- Ma'lumotlar bazasi ---
    database_url: SecretStr = Field(
        ...,
        description="PostgreSQL DSN (parol bo'lgani uchun secret sifatida saqlanadi).",
    )
    db_pool_min_size: int = Field(default=2, ge=1, le=50)
    db_pool_max_size: int = Field(default=10, ge=1, le=100)
    db_command_timeout: int = Field(default=60, ge=1, le=600)
    apply_migrations: bool = Field(
        default=True,
        description="Startupda versiyalangan migratsiyalarni bajarish.",
    )

    # --- Logging ---
    log_level: str = Field(default="INFO")
    log_json: bool = Field(
        default=False,
        description="Structured (JSON) log formati — log agregatorlar uchun.",
    )

    @field_validator("bot_token")
    @classmethod
    def _token_not_empty(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError(
                "BOT_TOKEN bo'sh. .env faylida to'g'ri token ko'rsating."
            )
        return value

    @field_validator("database_url")
    @classmethod
    def _database_url_not_empty(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("DATABASE_URL bo'sh. PostgreSQL DSN ni ko'rsating.")
        return value

    @field_validator("admin_ids", mode="before")
    @classmethod
    def _parse_admin_ids(cls, value: object) -> list[int]:
        if isinstance(value, str):
            val = value.strip()
            if not val:
                return []
            if val.startswith("[") and val.endswith("]"):
                try:
                    import json
                    parsed = json.loads(val)
                    if isinstance(parsed, list):
                        return [int(item) for item in parsed]
                except Exception:
                    pass
            return [int(item.strip()) for item in val.split(",") if item.strip()]
        if isinstance(value, (list, tuple, set)):
            return [int(item) for item in value]
        if isinstance(value, int):
            return [value]
        return []

    @model_validator(mode="after")
    def _require_authorization(self) -> "Settings":
        """Ruxsat ro'yxatisiz ishga tushishni rad etadi (fail-closed)."""
        if not self.admin_ids and not self.allow_open_access:
            raise ValueError(
                "ADMIN_IDS majburiy: bo'sh ro'yxat bilan bot va API har qanday "
                "Telegram foydalanuvchisiga ochiq bo'lib qolardi. "
                "Ochiq rejim kerak bo'lsa ALLOW_OPEN_ACCESS=true ni ongli "
                "ravishda yoqing (faqat development uchun)."
            )
        return self

    @property
    def token(self) -> str:
        """Tokenning ochiq (plaintext) qiymati."""
        return self.bot_token.get_secret_value()

    @property
    def dsn(self) -> str:
        """PostgreSQL DSN ning ochiq qiymati."""
        return self.database_url.get_secret_value()

    @property
    def admin_id_list(self) -> list[int]:
        """Adminlar ro'yxati (parse qilingan holatda)."""
        return self.admin_ids if isinstance(self.admin_ids, list) else []

    @property
    def web_app_url(self) -> str:
        """Telegram Mini App uchun to'liq URL (agar sozlangan bo'lsa)."""
        return self.render_external_url.rstrip("/")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Sozlamalarni bir marta o'qib, keshlaydi (singleton)."""
    return Settings()  # type: ignore[call-arg]
