"""Subjects API.

Persists user-created subjects so they survive refresh/idle.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.database import db_session
from app.models.subject import Subject
from app.models.textbook import Textbook
from app.models.chapter import Chapter
from app.models.user import User
from app.utils.security import get_current_user

router = APIRouter(prefix="/subjects", tags=["subjects"])


class SubjectCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class SubjectOut(BaseModel):
    id: str
    name: str
    icon: str


@router.get("")
async def list_subjects(user: User = Depends(get_current_user)) -> list[SubjectOut]:
    with db_session() as db:
        rows = (
            db.query(Subject)
            .filter(Subject.user_id == int(user.id))
            .order_by(Subject.created_at.desc())
            .all()
        )
        out = [SubjectOut(id=str(s.id), name=str(s.name), icon=str(s.icon)) for s in rows]
        return out


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_subject(payload: SubjectCreateIn, user: User = Depends(get_current_user)) -> SubjectOut:
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Subject name is required")

    sid = uuid.uuid4().hex
    with db_session() as db:
        s = Subject(id=sid, user_id=int(user.id), name=name[:120], icon="📖")
        db.add(s)

    return SubjectOut(id=str(sid), name=str(name[:120]), icon="📖")


@router.get("/{subject_id}")
async def get_subject(subject_id: str, user: User = Depends(get_current_user)) -> dict:
    with db_session() as db:
        s = (
            db.query(Subject)
            .filter(Subject.user_id == int(user.id), Subject.id == str(subject_id))
            .first()
        )
        if not s:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")

        textbooks = (
            db.query(Textbook)
            .filter(Textbook.subject_id == str(subject_id))
            .order_by(Textbook.created_at.desc())
            .all()
        )

        out_textbooks: list[dict] = []
        for tb in textbooks:
            total_pages = None
            try:
                if isinstance(tb.structure, dict):
                    total_pages = tb.structure.get("total_pages")
            except Exception:
                total_pages = None

            chapters = (
                db.query(Chapter)
                .filter(Chapter.textbook_id == int(tb.id))
                .order_by(Chapter.chapter_number.asc())
                .all()
            )

            out_textbooks.append(
                {
                    "id": str(tb.id),
                    "title": str(tb.title),
                    "totalPages": int(total_pages) if isinstance(total_pages, int) else None,
                    "chapters": [
                        {
                            "id": str(ch.chapter_key),
                            "name": str(ch.chapter_title),
                            "pdfUrl": f"/api/textbooks/{int(tb.id)}/chapters/{str(ch.chapter_key)}/pdf",
                            "pageRange": {"start": int(ch.start_page or 1), "end": int(ch.end_page or 1)},
                            "documentId": str(tb.id),
                            "totalPages": int(total_pages) if isinstance(total_pages, int) else None,
                        }
                        for ch in chapters
                    ],
                }
            )

        return {
            "id": str(s.id),
            "name": str(s.name),
            "icon": str(s.icon),
            "textbooks": out_textbooks,
        }


@router.delete("/{subject_id}")
async def delete_subject(subject_id: str, user: User = Depends(get_current_user)) -> dict:
    with db_session() as db:
        s = (
            db.query(Subject)
            .filter(Subject.user_id == int(user.id), Subject.id == str(subject_id))
            .first()
        )
        if not s:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")

        # We intentionally do not delete textbooks here because that requires
        # cleaning vectors/files/cloudinary. Users can delete textbooks explicitly.
        db.delete(s)

    return {"ok": True}
