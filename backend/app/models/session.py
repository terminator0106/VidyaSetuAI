"""Session + query logging models.

Sessions represent a conversational thread. Query logs capture token/cost metrics.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Session(Base):
    """A user chat session."""

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)

    # Optional linkage
    textbook_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("textbooks.id", ondelete="SET NULL"), nullable=True)
    chapter_key: Mapped[str | None] = mapped_column(String(200), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class QueryLog(Base):
    """Stores per-query model usage + savings metrics."""

    __tablename__ = "query_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    session_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True)

    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)

    model_used: Mapped[str] = mapped_column(String(50), nullable=False)
    language: Mapped[str] = mapped_column(String(32), nullable=False)

    # Token/cost metrics
    baseline_input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    actual_input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    actual_output_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    tokens_saved: Mapped[int] = mapped_column(Integer, nullable=False)

    baseline_cost_inr: Mapped[float] = mapped_column(Float, nullable=False)
    actual_cost_inr: Mapped[float] = mapped_column(Float, nullable=False)
    inr_saved: Mapped[float] = mapped_column(Float, nullable=False)
    avg_cost_reduction_pct: Mapped[float] = mapped_column(Float, nullable=False)

    extra: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
