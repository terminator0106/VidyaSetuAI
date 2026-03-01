"""PostgreSQL database setup (SQLAlchemy).

We use a synchronous engine for simplicity and broad compatibility. FastAPI
endpoints remain `async` and DB work runs quickly; if you expect very high DB
latency/throughput, move to SQLAlchemy async + asyncpg.
"""

from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine
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

engine = create_engine(_db_url, **_engine_kwargs)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def init_db() -> None:
    """Create tables if they do not exist.

    This keeps the project runnable without Alembic for the initial setup.
    For production migrations, add Alembic.
    """

    # Import models so they register with Base.metadata
    from app.models import session as _session  # noqa: F401
    from app.models import textbook as _textbook  # noqa: F401
    from app.models import user as _user  # noqa: F401
    from app.models import chapter as _chapter  # noqa: F401
    from app.models import textbook_index as _textbook_index  # noqa: F401

    Base.metadata.create_all(bind=engine)


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
