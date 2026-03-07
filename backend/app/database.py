"""PostgreSQL database setup (SQLAlchemy).

We use a synchronous engine for simplicity and broad compatibility. FastAPI
endpoints remain `async` and DB work runs quickly; if you expect very high DB
latency/throughput, move to SQLAlchemy async + asyncpg.
"""

from __future__ import annotations

from contextlib import contextmanager
import logging

from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import resolve_database_url, settings


class Base(DeclarativeBase):
    """Declarative base for ORM models."""


_db_url = resolve_database_url(settings)

_engine_kwargs: dict = {"pool_pre_ping": True}
if _db_url.startswith("sqlite"):
    _engine_kwargs.update(
        {
            "connect_args": {"check_same_thread": False},
            # Avoid pooled connections for local file-based SQLite.
            "poolclass": NullPool,
        }
    )
else:
    _engine_kwargs.update({"pool_size": 10, "max_overflow": 20})

    # Fail fast instead of hanging on unreachable DB hosts.
    # psycopg2 respects `connect_timeout` (seconds).
    _engine_kwargs.setdefault("connect_args", {})
    _engine_kwargs["connect_args"].setdefault("connect_timeout", 10)

engine = create_engine(_db_url, **_engine_kwargs)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

logger = logging.getLogger(__name__)


def _ensure_chapters_columns() -> None:
    """Ensure expected columns exist on the chapters table.

    SQLAlchemy's `create_all` does not add columns to existing tables.
    In this project we keep migrations lightweight; this function makes local/dev
    environments resilient when the DB schema lags behind the ORM models.
    """

    # Keep statements idempotent and safe to re-run.
    stmts = [
        "ALTER TABLE IF EXISTS public.chapters ADD COLUMN IF NOT EXISTS subject_id text",
        "ALTER TABLE IF EXISTS public.chapters ADD COLUMN IF NOT EXISTS cloudinary_url text",
        "CREATE INDEX IF NOT EXISTS ix_chapters_subject_id ON public.chapters(subject_id)",
        "CREATE INDEX IF NOT EXISTS ix_chapters_textbook_id ON public.chapters(textbook_id)",
    ]

    try:
        with engine.begin() as conn:
            for s in stmts:
                conn.execute(text(s))
    except Exception as e:
        # Don't crash startup; routes that depend on these columns will still fail,
        # but we emit a clear log message pointing to the SQL script.
        logger.warning(
            "Schema ensure for chapters failed; run backend/sql/07_chapters_add_subject_cloudinary.sql manually",
            extra={"extra": {"err": str(e)}},
        )


def _ensure_textbooks_columns() -> None:
    """Ensure expected columns exist on the textbooks table."""

    stmts = [
        "ALTER TABLE IF EXISTS public.textbooks ADD COLUMN IF NOT EXISTS subject_id text",
        "CREATE INDEX IF NOT EXISTS ix_textbooks_subject_id ON public.textbooks(subject_id)",
    ]

    try:
        with engine.begin() as conn:
            for s in stmts:
                conn.execute(text(s))
    except Exception as e:
        logger.warning(
            "Schema ensure for textbooks failed; subject persistence may not work until subject_id exists",
            extra={"extra": {"err": str(e)}},
        )


def init_db() -> None:
    """Create tables if they do not exist.

    This keeps the project runnable without Alembic for the initial setup.
    For production migrations, add Alembic.
    """

    # Import models so they register with Base.metadata
    from app.models import session as _session  # noqa: F401
    from app.models import textbook as _textbook  # noqa: F401
    from app.models import user as _user  # noqa: F401
    from app.models import subject as _subject  # noqa: F401
    from app.models import chapter as _chapter  # noqa: F401
    from app.models import textbook_index as _textbook_index  # noqa: F401

    Base.metadata.create_all(bind=engine)

    # Ensure additive columns exist on existing tables.
    _ensure_chapters_columns()
    _ensure_textbooks_columns()


@contextmanager
def db_session():
    """Yield a DB session and ensure close/rollback on error."""

    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
