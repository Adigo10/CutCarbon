import os

from pydantic import BaseModel

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


class Settings(BaseSettings):
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"

    TINYFISH_API_KEY: str = ""

    # SQLite locally; swap to postgresql+asyncpg://user:pass@host/db for Postgres
    DATABASE_URL: str = "sqlite+aiosqlite:///./cutcarbon.db"

    JWT_SECRET: str = "change-me-in-production-use-a-long-random-string"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
