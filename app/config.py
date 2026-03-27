from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"

    TINYFISH_API_KEY: str = ""

    # SQLite locally; swap to postgresql+asyncpg://user:pass@host/db for Postgres
    DATABASE_URL: str = "sqlite+aiosqlite:///./cutcarbon.db"

    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
