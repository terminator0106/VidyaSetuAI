"""Application configuration loaded from environment variables.

The backend loads configuration from a local `.env` file (project root) and/or
process environment variables.
"""

from __future__ import annotations

from pathlib import Path
from typing import List
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed settings for the FastAPI service."""

    model_config = SettingsConfigDict(
        # Load ONLY from backend/.env (plus process env). Do not auto-fallback.
        env_file=str(Path(__file__).resolve().parents[1] / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "vidyasetu-backend"
    environment: str = Field(default="dev", description="dev|staging|prod")

    # API
    api_prefix: str = "/api"
    allowed_origins: List[str] = Field(
        default_factory=lambda: ["http://localhost:8080"],
        description="CORS allowlist origins (exact matches).",
    )

    # Auth
    jwt_secret: str = Field(..., description="JWT signing secret")
    jwt_algorithm: str = "HS256"
    access_token_exp_minutes: int = 60 * 24
    cookie_name: str = "access_token"
    cookie_secure: bool = False
    cookie_samesite: str = "lax"  # 'lax' for local dev; use 'none' + secure on HTTPS cross-site.

    # Datastores (local dev defaults)
    # Optional override (e.g., sqlite:///./data/vidyasetu.db)
    database_url: str | None = Field(default=None, description="Full SQLAlchemy DB URL override")

    postgres_host: str = Field(default="localhost")
    postgres_port: int = Field(default=5432)
    postgres_db: str = Field(default="vidyasetu")
    postgres_user: str = Field(default="postgres")
    postgres_password: str = Field(default="postgres")
    postgres_sslmode: str = Field(
        default="prefer",
        description="psycopg2 sslmode (disable|allow|prefer|require|verify-ca|verify-full). Supabase typically needs require.",
    )

    redis_url: str = Field(default="redis://localhost:6379/0", description="Redis URL")

    # Optional: seed an admin user on startup when provided.
    admin_email: str | None = None
    admin_password: str | None = None

    # OpenAI
    openai_api_key: str = Field(...)
    openai_model_large: str = "gpt-4o"
    openai_model_small: str = "gpt-4o-mini"

    # Embeddings
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # Vector store
    # Relative to the backend project directory by default.
    data_dir: str = "data"
    faiss_index_path: str = "faiss/index.bin"
    faiss_meta_path: str = "faiss/meta.json"

    # Cost tracking (rough, configurable)
    usd_to_inr: float = 83.0
    # USD per 1M tokens (input/output). Adjust to your contract if needed.
    gpt4o_in_usd_per_1m: float = 5.0
    gpt4o_out_usd_per_1m: float = 15.0
    gpt4omini_in_usd_per_1m: float = 0.15
    gpt4omini_out_usd_per_1m: float = 0.60


settings = Settings()


def build_postgres_dsn(s: Settings) -> str:
    """Build a SQLAlchemy DSN from discrete POSTGRES_* settings."""

    user = quote(s.postgres_user)
    password = quote(s.postgres_password)
    host = s.postgres_host
    port = int(s.postgres_port)
    db = quote(s.postgres_db)
    base = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"
    sslmode = (s.postgres_sslmode or "").strip()
    if not sslmode:
        return base
    return f"{base}?sslmode={quote(sslmode)}"


def _ensure_sslmode(url: str, sslmode: str) -> str:
    parts = urlsplit(url)
    existing = dict(parse_qsl(parts.query, keep_blank_values=True))
    if "sslmode" in existing:
        return url
    existing["sslmode"] = sslmode
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(existing), parts.fragment))


def resolve_database_url(s: Settings) -> str:
    """Return the SQLAlchemy URL to use (DATABASE_URL overrides Postgres settings)."""

    url = s.database_url or build_postgres_dsn(s)

    # Normalize common shorthand.
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]

    # Supabase Postgres requires SSL. If user supplied a DATABASE_URL pointing
    # to Supabase but forgot sslmode, enforce sslmode=require.
    try:
        host = urlsplit(url).hostname or ""
        if host.endswith(".supabase.co") or host.endswith(".supabase.com"):
            url = _ensure_sslmode(url, "require")
    except Exception:
        return url

    return url
