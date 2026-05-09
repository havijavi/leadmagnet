import hashlib
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql+asyncpg://leadmagnet:leadmagnet@postgres:5432/leadmagnet"
    REDIS_URL: str = "redis://redis:6379/0"

    # ADMIN_TOKEN is the break-glass superuser bearer token. Anyone presenting
    # it is treated as an admin without a user account. Used by the setup-vps
    # script and useful for emergency access if you've locked yourself out.
    ADMIN_TOKEN: str = "changeme"

    # Signs JWTs issued at /api/auth/login. Auto-derived from ADMIN_TOKEN if
    # left blank — fine for solo use, set explicitly when sharing the box.
    JWT_SECRET: str = ""
    JWT_TTL_SECONDS: int = 86400  # 24 hours

    LLM_PROVIDER: str = "deepseek"
    LLM_BASE_URL: str = "https://api.deepseek.com/v1"
    LLM_MODEL: str = "deepseek-chat"
    LLM_API_KEY: str = ""

    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    SMTP_FROM_NAME: str = "LeadMagnet"

    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    NOTIFY_WEBHOOK_URL: str = ""
    NOTIFY_EMAIL: str = ""

    CRAWLER_CONCURRENCY: int = 4
    CRAWLER_USER_AGENT: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    SEARXNG_URL: str = ""

    HUNTER_API_KEY: str = ""
    SNOV_CLIENT_ID: str = ""
    SNOV_CLIENT_SECRET: str = ""

    GOOGLE_SHEETS_CREDENTIALS_JSON: str = ""
    GOOGLE_SHEETS_CREDENTIALS_FILE: str = ""

    SCHEDULER_ENABLED: bool = True

    NOTIFY_FIT_THRESHOLD: int = 70

    @property
    def effective_jwt_secret(self) -> str:
        if self.JWT_SECRET:
            return self.JWT_SECRET
        return hashlib.sha256(b"jwt:" + self.ADMIN_TOKEN.encode()).hexdigest()


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
