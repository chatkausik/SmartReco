from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Mesh API — every LLM/embedding call in this app must go through Mesh.
    mesh_api_key: str = "rsk_placeholder"
    mesh_base_url: str = "https://api.meshapi.ai/v1"
    mesh_chat_model: str = "openai/gpt-4o-mini"
    mesh_embedding_model: str = "openai/text-embedding-3-small"

    # App / sessions
    secret_key: str = "dev-secret-change-me"
    database_url: str = "sqlite:///./smartreco.db"
    chroma_dir: str = "./chroma_data"
    session_cookie_name: str = "smartreco_session"
    session_max_age_seconds: int = 60 * 60 * 24 * 14  # 14 days

    # Bootstrap admin
    bootstrap_admin_email: str = "admin@example.com"
    bootstrap_admin_password: str = "change-me-admin-password"

    # On a fresh cloud deploy the filesystem is empty (and ephemeral). When true, startup
    # bootstraps the admin + seeds the catalog if the products table is empty, so the app comes
    # up populated without a manual shell step. Off by default so local dev never surprises you
    # with Mesh embedding calls at boot. Requires a funded MESH_API_KEY (seeding embeds via Mesh).
    auto_seed_on_startup: bool = False

    # Recommendation trigger thresholds — the "smart AI-call triggering" knobs.
    event_threshold: int = 15
    min_cooldown_minutes: int = 10
    max_staleness_hours: int = 24
    max_refinements: int = 2

    # Scheduled digest
    digest_hour: int = 15
    digest_minute: int = 0
    digest_dev_interval_minutes: int | None = None

    # SMTP (optional — digest emails log to console if unset)
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str = "SmartReco <noreply@smartreco.local>"

    # LangSmith (optional)
    langchain_tracing_v2: bool = False
    langchain_api_key: str | None = None
    langchain_project: str = "smartreco"

    @field_validator(
        "digest_dev_interval_minutes", "smtp_host", "smtp_user", "smtp_password", "langchain_api_key",
        mode="before",
    )
    @classmethod
    def _blank_env_string_to_none(cls, value):
        # Optional .env vars are often left as an empty string rather than omitted entirely.
        if isinstance(value, str) and value.strip() == "":
            return None
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
