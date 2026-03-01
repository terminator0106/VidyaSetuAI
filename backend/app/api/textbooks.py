"""Textbook utility APIs.

- Serve per-chapter PDFs (generated on demand from page ranges)
- List chapters with page ranges
- Delete an ingested textbook and all associated artifacts
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.config import settings
from app.database import db_session
from app.models.chapter import Chapter
from app.models.textbook import Textbook
from app.models.textbook_index import TextbookIndex
from app.models.user import User
from app.redis_client import get_redis
from app.services.cache_keys import chapter_compressed_key, chapter_raw_key, chunk_key
from app.services.textbook_store import chunks_path, pdf_path
from app.services.vector_store import get_store
from app.utils.security import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/textbooks", tags=["textbooks"])


@router.get("/{textbook_id}/chapters/{chapter_key}/pdf")
async def get_chapter_pdf(
    textbook_id: int,
    chapter_key: str,
    user: User = Depends(get_current_user),
):
    with db_session() as db:
        ch = (
            db.query(Chapter)
            .filter(Chapter.textbook_id == textbook_id, Chapter.chapter_key == chapter_key)
            .first()
        )
        if not ch:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found")

        src = pdf_path(textbook_id)
        if not src.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source PDF not found")

        # Generate chapter PDF on-demand (no stored per-chapter files).
        import fitz  # local import to keep module import light

        doc = fitz.open(str(src))
        try:
            total = int(doc.page_count)
            start = max(1, min(total, int(ch.start_page)))
            end = max(start, min(total, int(ch.end_page)))

            out_doc = fitz.open()
            try:
                out_doc.insert_pdf(doc, from_page=start - 1, to_page=end - 1)
                pdf_bytes = out_doc.tobytes(deflate=True)
            finally:
                out_doc.close()
        finally:
            doc.close()

    filename = f"{chapter_key}.pdf"
    return StreamingResponse(
        content=iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename=\"{filename}\""},
    )


@router.get("/{textbook_id}/chapters")
async def list_chapters(textbook_id: int, user: User = Depends(get_current_user)) -> dict:
    with db_session() as db:
        tb = db.query(Textbook).filter(Textbook.id == textbook_id).first()
        if not tb:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Textbook not found")

        chapters = (
            db.query(Chapter)
            .filter(Chapter.textbook_id == textbook_id)
            .order_by(Chapter.chapter_number.asc())
            .all()
        )

    return {
        "textbook_id": str(textbook_id),
        "chapters": [
            {
                "id": ch.chapter_key,
                "title": ch.chapter_title,
                "start_page": int(ch.start_page),
                "end_page": int(ch.end_page),
                "page_count": int(ch.page_count),
            }
            for ch in chapters
        ],
    }


@router.get("/{textbook_id}/chapters/{chapter_key}/pages")
async def get_chapter_pages(textbook_id: int, chapter_key: str, user: User = Depends(get_current_user)) -> dict:
    with db_session() as db:
        ch = (
            db.query(Chapter)
            .filter(Chapter.textbook_id == textbook_id, Chapter.chapter_key == chapter_key)
            .first()
        )
        if not ch:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found")

    return {
        "textbook_id": str(textbook_id),
        "chapter_id": chapter_key,
        "start_page": int(ch.start_page),
        "end_page": int(ch.end_page),
        "pdf_url": f"/api/textbooks/{textbook_id}/chapters/{chapter_key}/pdf",
    }


def _textbook_root_dir(textbook_id: int) -> Path:
    return Path(settings.data_dir) / "textbooks" / str(textbook_id)


def _collect_cache_keys(tb: Textbook) -> List[str]:
    keys: List[str] = []
    return keys


@router.delete("/{textbook_id}")
async def delete_textbook(
    textbook_id: int,
    user: User = Depends(get_current_user),
):
    # NOTE: At the moment textbooks are not owned by a user in the DB schema.
    # We require authentication and assume a single-user deployment.

    with db_session() as db:
        tb = db.query(Textbook).filter(Textbook.id == textbook_id).first()
        if not tb:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Textbook not found")

        # Collect cache keys deterministically from DB + chunks.json.
        cache_keys: List[str] = []

        # Chunk keys (from chunks.json on disk)
        try:
            p = Path(tb.chunks_path)
            if p.exists():
                import json

                raw = json.loads(p.read_text(encoding="utf-8"))
                for c in raw.get("chunks", []) or []:
                    cid = str(c.get("chunk_id") or "")
                    if cid:
                        cache_keys.append(chunk_key(int(tb.id), cid))
        except Exception:
            logger.exception("Failed reading chunks for cache key cleanup")

        # Chapter raw/compressed keys (from chapters table)
        try:
            chapters = db.query(Chapter).filter(Chapter.textbook_id == textbook_id).all()
            for ch in chapters:
                cache_keys.append(chapter_raw_key(ch.chapter_key))
                cache_keys.append(chapter_compressed_key(ch.chapter_key))
        except Exception:
            logger.exception("Failed reading chapters for cache key cleanup")

        # Delete DB rows first (so UI doesn't see it), then clean up artifacts.
        # Chapters + index rows cascade via FK.
        db.delete(tb)

    # Redis cleanup (best-effort)
    r = get_redis()
    try:
        if cache_keys:
            await r.delete(*cache_keys)
    except Exception:
        logger.exception("Failed deleting redis keys")

    # FAISS cleanup
    removed_vectors = 0
    try:
        store = get_store()
        removed_vectors = store.delete_textbook(textbook_id)
    except Exception:
        logger.exception("Failed deleting textbook vectors")

    # Filesystem cleanup
    removed_files = False
    try:
        root = _textbook_root_dir(textbook_id)
        if root.exists():
            shutil.rmtree(root, ignore_errors=True)
            removed_files = True
    except Exception:
        logger.exception("Failed deleting textbook files")

    return {
        "ok": True,
        "textbookId": textbook_id,
        "removed": {
            "redisKeys": len(cache_keys),
            "vectors": removed_vectors,
            "files": removed_files,
        },
    }
