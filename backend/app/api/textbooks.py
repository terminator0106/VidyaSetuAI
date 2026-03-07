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
from app.models.session import Session
from app.models.textbook import Textbook
from app.models.textbook_index import TextbookIndex
from app.models.user import User
from app.redis_client import get_redis
from app.services.cache_keys import chapter_compressed_key, chapter_raw_key, chunk_key, session_summary_key
from app.services.cloudinary_storage import CloudinaryStorageError, delete_file, public_id_from_url
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
async def list_chapters(textbook_id: int, user: User = Depends(get_current_user)) -> list[dict]:
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

    return [
        {
            "chapter_number": int(ch.chapter_number),
            "chapter_title": str(ch.chapter_title),
            "cloudinary_url": str(ch.cloudinary_url) if ch.cloudinary_url else None,
        }
        for ch in chapters
    ]


@router.get("/{textbook_id}/chapters/ranges")
async def list_chapters_with_ranges(textbook_id: int, user: User = Depends(get_current_user)) -> dict:
    """Legacy chapter listing with page ranges."""

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
                "cloudinary_url": str(ch.cloudinary_url) if ch.cloudinary_url else None,
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

        if ch.start_page is None or ch.end_page is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Chapter page range is missing. Re-ingest the textbook to rebuild chapter ranges.",
            )

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

    # Phase 1: read current state (no side effects)
    with db_session() as db:
        tb = db.query(Textbook).filter(Textbook.id == textbook_id).first()
        if not tb:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Textbook not found")

        chapters = db.query(Chapter).filter(Chapter.textbook_id == textbook_id).all()
        sessions = db.query(Session.id).filter(Session.textbook_id == textbook_id).all()

        # Collect cache keys deterministically from DB + chunks.json.
        cache_keys: List[str] = []

        # Chunk keys (from FAISS meta; reliable even if chunks.json is missing)
        try:
            store = get_store()
            for cid in store.chunk_ids_for_textbook(textbook_id):
                cache_keys.append(chunk_key(int(tb.id), str(cid)))
        except Exception:
            logger.exception("Failed reading FAISS metadata for cache key cleanup")

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
        for ch in chapters:
            cache_keys.append(chapter_raw_key(ch.chapter_key))
            cache_keys.append(chapter_compressed_key(ch.chapter_key))

        # Session summaries (from sessions table)
        for (sid,) in sessions:
            try:
                cache_keys.append(session_summary_key(int(sid)))
            except Exception:
                continue

        # Cloudinary public IDs (derived from stored URLs)
        cloudinary_public_ids: List[str] = []
        for ch in chapters:
            pid = public_id_from_url(str(ch.cloudinary_url or ""))
            if pid:
                cloudinary_public_ids.append(pid)

    # Phase 2: delete external artifacts (best-effort) while collecting failures.
    cleanup_errors: List[str] = []

    removed_cloudinary = 0
    if cloudinary_public_ids:
        for pid in sorted(set(cloudinary_public_ids)):
            try:
                delete_file(pid)
                removed_cloudinary += 1
            except CloudinaryStorageError as e:
                cleanup_errors.append(f"cloudinary:{pid}: {e}")

    r = get_redis()
    removed_redis = 0
    try:
        if cache_keys:
            removed_redis = await r.delete(*sorted(set(cache_keys)))
    except Exception as e:
        cleanup_errors.append(f"redis: {e}")

    removed_vectors = 0
    try:
        store = get_store()
        removed_vectors = store.delete_textbook(textbook_id)
    except Exception as e:
        cleanup_errors.append(f"vectors: {e}")

    removed_files = False
    try:
        root = _textbook_root_dir(textbook_id)
        if root.exists():
            shutil.rmtree(root, ignore_errors=True)
            removed_files = not root.exists()
            if root.exists():
                cleanup_errors.append("files: failed to remove textbook directory")
    except Exception as e:
        cleanup_errors.append(f"files: {e}")

    # Phase 3: delete DB rows (chapters + index + textbook) for consistency.
    with db_session() as db:
        # Delete chapters explicitly (even though FK cascade exists) per requirement.
        db.query(Chapter).filter(Chapter.textbook_id == textbook_id).delete(synchronize_session=False)
        db.query(TextbookIndex).filter(TextbookIndex.textbook_id == textbook_id).delete(synchronize_session=False)
        tb = db.query(Textbook).filter(Textbook.id == textbook_id).first()
        if tb:
            db.delete(tb)

    return {
        "ok": len(cleanup_errors) == 0,
        "textbookId": textbook_id,
        "removed": {
            "redisKeys": removed_redis,
            "cloudinary": removed_cloudinary,
            "vectors": removed_vectors,
            "files": removed_files,
        },
        "errors": cleanup_errors,
    }
