"""Chapter model.

Chapters are created strictly from the textbook's Index/Table of Contents.

Important:
- start_page/end_page are 1-based PDF page numbers.
- chapter_key is a stable, API-friendly identifier used by the frontend and
  retrieval metadata (e.g. "tb12_ch01").
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Chapter(Base):
    """A logical chapter of a textbook (page-accurate)."""

    __tablename__ = "chapters"
    __table_args__ = (
        UniqueConstraint("textbook_id", "chapter_key", name="uq_chapters_textbook_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    textbook_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("textbooks.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False)
    chapter_title: Mapped[str] = mapped_column(String(300), nullable=False)

    # Stable public identifier used by APIs and vector metadata.
    chapter_key: Mapped[str] = mapped_column(String(64), index=True, nullable=False)

    # 1-based PDF page numbers.
    start_page: Mapped[int] = mapped_column(Integer, nullable=False)
    end_page: Mapped[int] = mapped_column(Integer, nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
