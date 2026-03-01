"""Admin user seeding.

If ADMIN_EMAIL and ADMIN_PASSWORD are provided in settings, this module will
ensure an admin user exists on startup.

This is optional and idempotent.
"""

from __future__ import annotations

import logging

from app.config import settings
from app.database import db_session
from app.models.user import User, UserRole
from app.utils.security import hash_password

logger = logging.getLogger(__name__)


def seed_admin_if_configured() -> None:
    email = (settings.admin_email or "").strip().lower()
    password = settings.admin_password

    if not email or not password:
        return

    with db_session() as db:
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            if existing.role != UserRole.admin:
                existing.role = UserRole.admin
                db.add(existing)
                logger.info("Promoted existing user to admin", extra={"extra": {"email": email}})
            return

        user = User(email=email, password_hash=hash_password(password), role=UserRole.admin)
        db.add(user)
        logger.info("Seeded admin user", extra={"extra": {"email": email}})
