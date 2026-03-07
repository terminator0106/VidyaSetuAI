"""Subject model.

A Subject is a user-owned grouping for textbooks (e.g., Physics, Chemistry).
Subjects must persist until the user deletes them.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Subject(Base):
    __tablename__ = "subjects"

    # Use a string id to match the frontend routing (`/subject/:subjectId`).
    id: Mapped[str] = mapped_column(String(64), primary_key=True)

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    icon: Mapped[str] = mapped_column(String(16), nullable=False, default="📖")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
