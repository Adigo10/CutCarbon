import os
import secrets
import sys

from pydantic import BaseModel, model_validator

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ImportError:
    try:
        from dotenv import load_dotenv
    except ImportError:
        load_dotenv = None

    def SettingsConfigDict(**kwargs):
        return kwargs

    class BaseSettings(BaseModel):
        def __init__(self, **values):
            if load_dotenv:
                load_dotenv(".env")

            merged = {
                name: os.environ[name]
                for name in self.__class__.model_fields
                if name in os.environ
            }
            merged.update(values)
            super().__init__(**merged)


# The placeholder that ships in source. A JWT secret equal to this (or empty/too
# short) is treated as "unset" — anyone reading the repo could otherwise forge a
# token for any user. We never sign with a known/committed value.
PLACEHOLDER_JWT_SECRET = "change-me-in-production-use-a-long-random-string"


class Settings(BaseSettings):
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"

    TINYFISH_API_KEY: str = ""

    # SQLite locally; swap to postgresql+asyncpg://user:pass@host/db for Postgres
    DATABASE_URL: str = "sqlite+aiosqlite:///./cutcarbon.db"

    JWT_SECRET: str = PLACEHOLDER_JWT_SECRET
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # Comma-separated emails allowed to trigger TinyFish agent runs (which mutate
    # the global emission-factor file and scrape external sites). Empty = nobody.
    ADMIN_EMAILS: str = ""

    # Disable in tests; per-IP in-memory limits otherwise.
    RATE_LIMIT_ENABLED: bool = True

    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def _ensure_strong_jwt_secret(self):
        """Never run with a missing, placeholder, or weak JWT secret.

        In production set JWT_SECRET (>=32 chars) via the environment. If it is
        unset/placeholder/too short we generate an EPHEMERAL random secret for
        this process so token forgery with the known committed value is
        impossible — tokens simply won't survive a restart. This keeps a
        demo/dev run working while closing the auth-bypass hole.
        """
        weak = (
            not self.JWT_SECRET
            or self.JWT_SECRET == PLACEHOLDER_JWT_SECRET
            or len(self.JWT_SECRET) < 32
        )
        if weak:
            self.JWT_SECRET = secrets.token_urlsafe(64)
            print(
                "[config] WARNING: JWT_SECRET was unset, the built-in placeholder, "
                "or shorter than 32 chars. Generated an ephemeral random secret for "
                "this process (tokens will not survive a restart). Set a strong "
                "JWT_SECRET in .env for production.",
                file=sys.stderr,
            )
        return self


settings = Settings()
