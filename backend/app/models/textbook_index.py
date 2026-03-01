"""Cached index/Table of Contents extraction for a textbook.

We cache index pages + raw extracted text + parsed structured JSON to ensure we
never re-parse the index on subsequent operations.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TextbookIndex(Base):
    """Stores cached index extraction/parsing results for a textbook."""

    __tablename__ = "textbook_indexes"
    __table_args__ = (UniqueConstraint("textbook_id", name="uq_textbook_indexes_textbook"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    textbook_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("textbooks.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    index_pages: Mapped[list[int]] = mapped_column(JSON, nullable=False)
    index_text: Mapped[str] = mapped_column(Text, nullable=False)

    # Parsed list of chapters as JSON.
    parsed: Mapped[dict] = mapped_column(JSON, nullable=False)
    page_offset: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
