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


def _resolve_env_files() -> list[str]:
    """Resolve env files to load.

    Primary: `<backend>/.env` next to this source tree.
    Fallbacks: `.env` in CWD, or `backend/.env` relative to CWD.

    This prevents confusing cases where `uvicorn` is launched from a different
    directory or an unexpected `app` package is imported from site-packages.
    """

    candidates: list[Path] = []

    # Normal case: backend/.env (relative to this file location)
    candidates.append(Path(__file__).resolve().parents[1] / ".env")

    # Common local run fallbacks
    cwd = Path.cwd().resolve()
    candidates.append(cwd / ".env")
    candidates.append(cwd / "backend" / ".env")

    # Search upwards a bit (helps when launched from subfolders)
    for parent in list(cwd.parents)[:6]:
        candidates.append(parent / ".env")
        candidates.append(parent / "backend" / ".env")

    seen: set[Path] = set()
    resolved: list[str] = []
    for p in candidates:
        if p in seen:
            continue
        seen.add(p)
        if p.exists() and p.is_file():
            resolved.append(str(p))

    return resolved


class Settings(BaseSettings):
    """Strongly-typed settings for the FastAPI service."""

    model_config = SettingsConfigDict(
        # Load from backend/.env (plus process env). Includes safe fallbacks.
        env_file=_resolve_env_files(),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "vidyasetu-backend"
    environment: str = Field(default="dev", description="dev|staging|prod")

    # API
    api_prefix: str = "/api"
    allowed_origins: List[str] = Field(
        default_factory=lambda: [
            "http://localhost:8080",
            "http://127.0.0.1:8080",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
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

    # LLM provider
    llm_provider: str = Field(
        default="groq",
        description="Which provider to use for chat/compression: groq|openai",
    )

    # Debugging
    index_debug: bool = Field(
        default=False,
        description="Log OCR/index detection diagnostics during ingest when True (INDEX_DEBUG=true).",
    )

    # OpenAI (optional if llm_provider=groq)
    openai_api_key: str | None = Field(default=None)
    openai_model_large: str = "gpt-4o"
    openai_model_small: str = "gpt-4o-mini"

    # Groq (OpenAI-compatible)
    groq_api_key: str | None = Field(default=None, description="Groq API key")
    groq_base_url: str = Field(default="https://api.groq.com/openai/v1")
    groq_model_index_parser: str = Field(
        # Groq periodically decommissions older model IDs; keep a modern default.
        default="llama-3.3-70b-versatile",
        description="Groq model used for index parsing fallback (must output strict JSON)",
    )

    groq_model_large: str = Field(
        default="llama-3.3-70b-versatile",
        description="Groq model used for final answer generation",
    )
    groq_model_small: str = Field(
        default="llama-3.1-8b-instant",
        description="Groq model used for routing/compression/session memory",
    )

    @property
    def model_large(self) -> str:
        return self.groq_model_large if self.llm_provider == "groq" else self.openai_model_large

    @property
    def model_small(self) -> str:
        return self.groq_model_small if self.llm_provider == "groq" else self.openai_model_small

    # Cloudinary (PDF storage)
    cloudinary_cloud_name: str | None = Field(default=None, description="Cloudinary cloud name")
    cloudinary_api_key: str | None = Field(default=None, description="Cloudinary API key")
    cloudinary_api_secret: str | None = Field(default=None, description="Cloudinary API secret")

    @property
    def CLOUDINARY_CLOUD_NAME(self) -> str | None:  # noqa: N802
        return self.cloudinary_cloud_name

    @property
    def CLOUDINARY_API_KEY(self) -> str | None:  # noqa: N802
        return self.cloudinary_api_key

    @property
    def CLOUDINARY_API_SECRET(self) -> str | None:  # noqa: N802
        return self.cloudinary_api_secret

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
