from functools import lru_cache
from typing import List
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def normalize_database_url(value: str) -> str:
    """Make DATABASE_URL work with SQLAlchemy + Supabase/Render."""
    if not isinstance(value, str) or not value:
        return value

    if value.startswith("postgres://"):
        value = value.replace("postgres://", "postgresql://", 1)

    # Do not re-serialize sqlite URLs — urlparse mangles them
    if value.startswith("sqlite:"):
        return value

    parsed = urlparse(value)
    host = (parsed.hostname or "").lower()
    is_supabase = "supabase.co" in host or "supabase.com" in host

    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    if is_supabase and "sslmode" not in query:
        query["sslmode"] = "require"

    return urlunparse(parsed._replace(query=urlencode(query)))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Outcome Orchestration Platform"
    app_env: str = "prototype"
    debug: bool = True
    secret_key: str = "change-me-to-a-long-random-string"
    api_prefix: str = "/api/v1"
    cors_origins: str = "http://localhost:3000"

    database_url: str = "sqlite:///./orchestration.db"
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_timeout: int = 30
    # create_all on boot — fine for prototype; prefer Alembic in production
    schema_auto_create: bool = True
    run_migrations_on_startup: bool = False
    auto_seed: bool = True

    admin_email: str = "admin@prototype.local"
    admin_password: str = "admin123"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 480

    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    ai_prompt_version: str = "v1.0.0"

    gmail_client_id: str = ""
    gmail_client_secret: str = ""
    gmail_redirect_uri: str = "http://localhost:8000/api/v1/integrations/gmail/callback"
    gmail_token_path: str = "./secrets/gmail_token.json"
    gmail_scopes: str = "https://www.googleapis.com/auth/gmail.modify"
    gmail_poll_interval_seconds: int = 30
    gmail_user_id: str = "me"

    worker_poll_interval_seconds: float = 2.0
    worker_max_concurrent_ai_jobs: int = 5
    worker_max_retries: int = 5
    worker_retry_base_seconds: float = 5.0

    attachment_max_bytes: int = 10_485_760
    attachment_allowlist: str = "pdf,png,jpg,jpeg,gif,txt,csv,xlsx,docx"

    storage_path: str = "./storage"
    audit_append_only: bool = True

    @field_validator("database_url", mode="before")
    @classmethod
    def coerce_database_url(cls, value: str) -> str:
        return normalize_database_url(value)

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def attachment_extensions(self) -> set[str]:
        return {e.strip().lower().lstrip(".") for e in self.attachment_allowlist.split(",") if e.strip()}

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in {"production", "prod"}

    @property
    def uses_supabase_pooler(self) -> bool:
        host = (urlparse(self.database_url).hostname or "").lower()
        return "pooler.supabase.com" in host

    @property
    def uses_transaction_pooler(self) -> bool:
        """Supabase transaction pooler is typically port 6543."""
        parsed = urlparse(self.database_url)
        return self.uses_supabase_pooler and parsed.port == 6543


@lru_cache
def get_settings() -> Settings:
    return Settings()
