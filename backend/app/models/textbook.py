"""Textbook model.

Stores metadata for an ingested PDF and references to persisted chunk files and
FAISS vector IDs.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Textbook(Base):
    """An ingested PDF textbook."""

    __tablename__ = "textbooks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Optional link to a persisted subject (string id, user-owned).
    subject_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("subjects.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    board: Mapped[str | None] = mapped_column(String(120), nullable=True)
    language: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # Local paths for persistence
    pdf_path: Mapped[str] = mapped_column(Text, nullable=False)
    chunks_path: Mapped[str] = mapped_column(Text, nullable=False)

    # Stores chapter/topic structure and mapping to vector ids.
    structure: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
