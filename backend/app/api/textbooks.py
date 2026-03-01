"""Textbook utility APIs.

- Serve per-chapter PDFs created during ingestion
- Delete an ingested textbook and all associated artifacts
"""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from app.config import settings
from app.database import db_session
from app.models.textbook import Textbook
from app.models.user import User
from app.redis_client import get_redis
from app.services.cache_keys import chapter_compressed_key, chapter_raw_key, chunk_key
from app.services.textbook_store import chapter_pdf_path
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
    # chapter_key is sanitized to a safe file name internally.
    path = chapter_pdf_path(textbook_id, chapter_key)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chapter PDF not found")
    return FileResponse(
        str(path),
        media_type="application/pdf",
        filename=path.name,
    )


def _textbook_root_dir(textbook_id: int) -> Path:
    return Path(settings.data_dir) / "textbooks" / str(textbook_id)


def _collect_cache_keys(tb: Textbook) -> List[str]:
    keys: List[str] = []

    # Chunk keys
    try:
        chunks_path = Path(tb.chunks_path)
        if chunks_path.exists():
            raw = json.loads(chunks_path.read_text(encoding="utf-8"))
            for c in raw.get("chunks", []) or []:
                cid = str(c.get("chunk_id") or "")
                if cid:
                    keys.append(chunk_key(int(tb.id), cid))
    except Exception:
        logger.exception("Failed reading chunks for cache key cleanup")

    # Chapter raw/compressed keys
    try:
        structure = tb.structure or {}
        for ch in structure.get("chapters", []) or []:
            ch_key = str(ch.get("key") or "")
            if ch_key:
                keys.append(chapter_raw_key(ch_key))
                keys.append(chapter_compressed_key(ch_key))
    except Exception:
        logger.exception("Failed reading structure for cache key cleanup")

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

        cache_keys = _collect_cache_keys(tb)

        # Delete DB row first (so UI doesn't see it), then clean up artifacts.
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
