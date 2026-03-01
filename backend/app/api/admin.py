"""Admin metrics API."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List

from fastapi import APIRouter, Depends
from sqlalchemy import func

from app.database import db_session
from app.models.session import QueryLog
from app.models.user import User
from app.utils.security import require_admin

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/savings")
def savings(user: User = Depends(require_admin)) -> dict:
    """Return aggregate savings metrics for the admin dashboard."""

    with db_session() as db:
        total_queries = db.query(func.count(QueryLog.id)).scalar() or 0
        tokens_saved = db.query(func.coalesce(func.sum(QueryLog.tokens_saved), 0)).scalar() or 0
        inr_saved = db.query(func.coalesce(func.sum(QueryLog.inr_saved), 0.0)).scalar() or 0.0
        avg_cost_reduction = db.query(func.coalesce(func.avg(QueryLog.avg_cost_reduction_pct), 0.0)).scalar() or 0.0

        # by day
        rows = (
            db.query(
                func.date(QueryLog.created_at).label("day"),
                func.count(QueryLog.id).label("queries"),
                func.coalesce(func.sum(QueryLog.tokens_saved), 0).label("tokens_saved"),
                func.coalesce(func.sum(QueryLog.inr_saved), 0.0).label("inr_saved"),
            )
            .group_by(func.date(QueryLog.created_at))
            .order_by(func.date(QueryLog.created_at))
            .all()
        )

        by_day = [
            {
                "date": str(r.day),
                "queries": int(r.queries),
                "tokensSaved": int(r.tokens_saved),
                "inrSaved": float(r.inr_saved),
            }
            for r in rows
        ]

    return {
        "totalQueries": int(total_queries),
        "tokensSaved": int(tokens_saved),
        "inrSaved": float(inr_saved),
        "avgCostReductionPct": float(avg_cost_reduction),
        "byDay": by_day,
    }
