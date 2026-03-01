"""Ingestion API.

POST /api/ingest/pdf - multipart upload
POST /api/ingest      - alias for the same behavior

Creates a Textbook record, chunks content by chapter/topic, embeds + stores in
FAISS, and returns detected chapters for the frontend.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.database import db_session
from app.models.textbook import Textbook
from app.models.user import User
from app.redis_client import get_redis
from app.services.cache_keys import chapter_compressed_key, chapter_raw_key, chunk_key
from app.services.chunker import chunk_by_topics
from app.services.embedder import embed_texts
from app.services.pdf_parser import extract_pages, extract_pdf_page_count, extract_toc_chapters
from app.services.textbook_store import build_structure, pdf_path, split_pdf_by_chapters, write_chunks
from app.services.vector_store import VectorMeta, get_store
from app.services.llm_client import chat_text
from app.config import settings
from app.utils.security import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ingest", tags=["ingest"])


async def _handle_ingest(
    user: User,
    file: UploadFile,
    subjectId: Optional[str] = None,
    chapterName: Optional[str] = None,
) -> dict:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Please upload a PDF file")

    # Create DB row first to get an ID.
    with db_session() as db:
        tb = Textbook(
            title=Path(file.filename).stem[:300],
            board=None,
            language=None,
            pdf_path="",
            chunks_path="",
            structure={},
        )
        db.add(tb)
        db.flush()  # populate tb.id
        textbook_id = int(tb.id)

        # Persist pdf
        out_pdf = pdf_path(textbook_id)
        content = await file.read()
        out_pdf.write_bytes(content)

        pages = extract_pages(str(out_pdf))

        # Prefer ToC/outline-based chapter splitting when available.
        toc_chapters = extract_toc_chapters(str(out_pdf))
        chunks = chunk_by_topics(pages, chapters=toc_chapters if toc_chapters else None)

        # Optional override: if frontend supplied a chapter name, treat as single chapter title.
        if chapterName:
            # Keep chapter-aware property: still one chapter, but named.
            for c in chunks:
                object.__setattr__(c, "chapter_title", chapterName)  # type: ignore[misc]

        # Namespace keys by textbook id to prevent collisions.
        namespaced = []
        for c in chunks:
            ch_key = f"tb{textbook_id}_{c.chapter_key}"
            tp_key = f"{ch_key}:{c.topic_key}"
            namespaced.append(
                type(c)(
                    chunk_id=f"tb{textbook_id}:{c.chunk_id}",
                    chapter_key=ch_key,
                    chapter_title=c.chapter_title,
                    topic_key=tp_key,
                    topic_title=c.topic_title,
                    page_start=c.page_start,
                    page_end=c.page_end,
                    text=c.text,
                )
            )
        chunks = namespaced

        chunks_file = write_chunks(textbook_id, chunks)
        tb.pdf_path = str(out_pdf)
        tb.chunks_path = str(chunks_file)
        structure = build_structure(chunks)

        # Split source PDF into per-chapter PDFs and attach URLs to structure.
        chapter_items = structure.get("chapters", [])
        split_map = split_pdf_by_chapters(textbook_id, out_pdf, chapter_items)
        for ch in chapter_items:
            key = str(ch.get("key") or "")
            if not key:
                continue
            if key in split_map:
                ch["pdf_url"] = f"/api/textbooks/{textbook_id}/chapters/{key}/pdf"
                ch["pdf_path"] = split_map[key]
                try:
                    ch["page_count"] = int(ch.get("page_end", 0)) - int(ch.get("page_start", 0)) + 1
                except Exception:
                    ch["page_count"] = None

        structure["textbook_id"] = textbook_id
        structure["total_pages"] = extract_pdf_page_count(str(out_pdf))
        tb.structure = structure
        db.add(tb)

    # Build vectors + add to FAISS.
    texts = [c.text for c in chunks]
    vectors = embed_texts(texts)

    metas = [
        VectorMeta(
            textbook_id=textbook_id,
            chapter_key=c.chapter_key,
            chapter_title=c.chapter_title,
            topic_key=c.topic_key,
            topic_title=c.topic_title,
            chunk_id=c.chunk_id,
        )
        for c in chunks
    ]

    store = get_store()
    store.add(vectors=vectors, metas=metas)

    # Cache chunk texts in Redis for faster ask path.
    r = get_redis()
    try:
        for c in chunks:
            await r.set(chunk_key(textbook_id, c.chunk_id), c.text)
    except Exception:
        logger.exception("Failed caching chunks in redis")

    # Pre-compress chapter contexts (mandatory for cost savings).
    try:
        structure = build_structure(chunks)
        chapters = structure.get("chapters", [])

        # Build chapter raw text from its chunks.
        chunk_text_by_id = {c.chunk_id: c.text for c in chunks}
        for ch in chapters:
            ch_key = str(ch.get("key"))
            topic_chunks: List[str] = []
            for t in ch.get("topics", []) or []:
                for cid in t.get("chunks", []) or []:
                    txt = chunk_text_by_id.get(str(cid), "")
                    if txt.strip():
                        topic_chunks.append(txt.strip())

            raw = "\n\n".join(topic_chunks)
            # Cap to keep preprocessing bounded.
            raw = raw[:40000]
            if not raw.strip():
                continue

            await r.set(chapter_raw_key(ch_key), raw)

            messages = [
                {
                    "role": "system",
                    "content": (
                        "You compress a chapter into short study notes for retrieval. "
                        "Keep key definitions, formulas, and typical examples. "
                        "Use bullet points, very simple language."
                    ),
                },
                {"role": "user", "content": raw},
            ]
            comp = await chat_text(model=settings.openai_model_small, messages=messages, temperature=0.0)
            if comp.text.strip():
                await r.set(chapter_compressed_key(ch_key), comp.text.strip())
    except Exception:
        logger.exception("Failed chapter pre-compression")

    # Response: chapters list for SubjectPage.
    chapters_payload = []
    structure = build_structure(chunks)
    total_pages = extract_pdf_page_count(str(pdf_path(textbook_id)))
    for ch in structure.get("chapters", []):
        key = ch.get("key")
        chapters_payload.append(
            {
                "id": key,
                "name": ch.get("title"),
                "pageRange": {"start": ch.get("page_start"), "end": ch.get("page_end")},
                "pdfUrl": f"/api/textbooks/{textbook_id}/chapters/{key}/pdf" if key else None,
            }
        )

    return {
        "documentId": str(textbook_id),
        "subjectId": subjectId,
        "totalPages": total_pages,
        "chapters": chapters_payload,
        "structure": structure,
    }


@router.post("/pdf")
async def ingest_pdf(
    file: UploadFile = File(...),
    subjectId: Optional[str] = Form(default=None),
    chapterName: Optional[str] = Form(default=None),
    user: User = Depends(get_current_user),
) -> dict:
    return await _handle_ingest(user=user, file=file, subjectId=subjectId, chapterName=chapterName)


@router.post("")
async def ingest_alias(
    file: UploadFile = File(...),
    subjectId: Optional[str] = Form(default=None),
    chapterName: Optional[str] = Form(default=None),
    user: User = Depends(get_current_user),
) -> dict:
    return await _handle_ingest(user=user, file=file, subjectId=subjectId, chapterName=chapterName)
