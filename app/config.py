import logging
import os

from pydantic import BaseModel

logger = logging.getLogger(__name__)

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

    # Primary backend is Supabase Postgres, via the transaction pooler (port 6543) as
    # the least-privilege `cutcarbon_app` role:
    #   postgresql+asyncpg://cutcarbon_app.<ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres
    # A sqlite+aiosqlite:// URL still works as a local dev fallback.
    DATABASE_URL: str = "sqlite+aiosqlite:///./cutcarbon.db"

    # Alembic uses this if set, otherwise falls back to DATABASE_URL. Point it at the
    # SESSION pooler (port 5432) or the direct connection — migrations need a stable
    # session and prepared statements, which the transaction pooler (6543) forbids.
    MIGRATION_DATABASE_URL: str = ""

    # Run `alembic upgrade head` from the app lifespan on startup. Off by default:
    # prod applies migrations out-of-band; enable only for single-instance dev/demo.
    RUN_MIGRATIONS_ON_STARTUP: bool = False

    # --- Supabase Auth ---------------------------------------------------------
    # Base project URL, e.g. https://abcxyz.supabase.co. Used to derive the JWKS
    # endpoint ({SUPABASE_URL}/auth/v1/.well-known/jwks.json) and the expected
    # token issuer ({SUPABASE_URL}/auth/v1).
    SUPABASE_URL: str = ""
    # Audience Supabase stamps on logged-in user tokens.
    SUPABASE_JWT_AUD: str = "authenticated"
    # Optional shared secret for HS256 verification (legacy JWT secret, or a test
    # secret). Empty = asymmetric-only (RS256/ES256 via JWKS).
    SUPABASE_JWT_SECRET: str = ""
    # Override the derived JWKS URL if needed; otherwise built from SUPABASE_URL.
    SUPABASE_JWKS_URL: str = ""
    SUPABASE_JWKS_CACHE_TTL: int = 600  # seconds

    # Comma-separated emails allowed to trigger TinyFish agent runs (which mutate
    # the global emission-factor file and scrape external sites). Empty = nobody.
    ADMIN_EMAILS: str = ""

    # Disable in tests; per-IP in-memory limits otherwise.
    RATE_LIMIT_ENABLED: bool = True

    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
