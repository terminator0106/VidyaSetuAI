"""FastAPI entrypoint.

Routes are mounted under `/api/*` to match the frontend proxy.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.config import settings
from app.logging_config import configure_logging
from app.database import engine, init_db
from app.redis_client import get_redis
from app.api.auth import router as auth_router
from app.api.ingest import router as ingest_router
from app.api.ask import router as ask_router
from app.api.admin import router as admin_router
from app.api.textbooks import router as textbooks_router
from app.api.subjects import router as subjects_router
from app.services.admin_seed import seed_admin_if_configured


configure_logging("INFO")
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"] ,
        allow_headers=["*"],
    )

    app.include_router(auth_router, prefix=settings.api_prefix)
    app.include_router(subjects_router, prefix=settings.api_prefix)
    app.include_router(ingest_router, prefix=settings.api_prefix)
    app.include_router(ask_router, prefix=settings.api_prefix)
    app.include_router(admin_router, prefix=settings.api_prefix)
    app.include_router(textbooks_router, prefix=settings.api_prefix)

    @app.exception_handler(OperationalError)
    async def _handle_db_down(_request: Request, _exc: OperationalError) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={"detail": "Database unavailable. Ensure Postgres is running and settings are correct."},
        )

    @app.on_event("startup")
    async def _startup() -> None:
        try:
            init_db()
        except SQLAlchemyError as e:
            logger.warning(
                "Database initialization failed; continuing (API routes that need DB will return 503)",
                extra={"extra": {"err": str(e)}},
            )
        # Redis is optional; the facade handles failures gracefully.
        await get_redis().ping()
        try:
            seed_admin_if_configured()
        except SQLAlchemyError as e:
            logger.warning(
                "Admin seed skipped because database is unavailable",
                extra={"extra": {"err": str(e)}},
            )

    @app.get("/health")
    async def health() -> dict:
        db_ok = False
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            db_ok = True
        except Exception:
            db_ok = False

        r = get_redis()
        await r.ping()
        return {"status": "ok", "db": {"ok": db_ok}, "redis": r.health()}

    return app


app = create_app()
