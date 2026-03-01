"""Ingestion API.

POST /api/ingest/pdf - multipart upload
POST /api/ingest     - alias

IMPORTANT:
- Chapters are created strictly from the PDF Index/Table of Contents pages.
- No heuristic chapter guessing is allowed.
- Groq is permitted ONLY as a fallback for parsing complex index formatting.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.database import db_session
from app.models.chapter import Chapter
from app.models.textbook import Textbook
from app.models.textbook_index import TextbookIndex
from app.models.user import User
from app.redis_client import get_redis
from app.services.cache_keys import chapter_compressed_key, chapter_raw_key, chunk_key
from app.services.embedder import embed_texts
from app.services.pdf_parser import extract_pdf_page_count
from app.services.index_splitter import (
    ChapterRange,
    IndexNotFoundError,
    IndexParseError,
    compute_chapter_ranges,
    extract_index_text,
    parse_index_chapters,
)
from app.services.textbook_store import build_structure, pdf_path, write_chunks
from app.services.vector_store import VectorMeta, get_store
from app.services.llm_client import chat_text
from app.config import settings
from app.utils.security import get_current_user

router = APIRouter(prefix="/ingest", tags=["ingest"])


def _chapter_key(textbook_id: int, chapter_number: int) -> str:
    """Stable chapter identifier used across APIs + vector metadata."""

    return f"tb{textbook_id}_ch{int(chapter_number):02d}"


def _extract_text_by_page_range(pdf_file: Path, start_page: int, end_page: int) -> List[tuple[int, str]]:
    """Extract plain text for each page in [start_page, end_page] inclusive."""

    import fitz

    doc = fitz.open(str(pdf_file))
    try:
        total = int(doc.page_count)
        start = max(1, min(total, int(start_page)))
        end = max(start, min(total, int(end_page)))
        out: List[tuple[int, str]] = []
        for p in range(start, end + 1):
            page = doc.load_page(p - 1)
            txt = (page.get_text("text") or "").strip()
            out.append((p, txt))
        return out
    finally:
        doc.close()


async def _handle_ingest(
    user: User,
    file: UploadFile,
    subjectId: Optional[str] = None,
    textbookName: Optional[str] = None,
) -> dict:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Please upload a PDF file")

    # Create DB row first to get an ID.
    with db_session() as db:
        tb = Textbook(
            title=(textbookName or Path(file.filename).stem)[:300],
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

        total_pages = extract_pdf_page_count(str(out_pdf))

        # STEP 1: Detect index pages and extract raw text.
        try:
            index_pages, index_text = extract_index_text(str(out_pdf), max_pages=10)
        except IndexNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Index/Table of Contents not found: {e}",
            )

        # STEP 2: Parse index into chapters (regex fast-path; Groq fallback).
        try:
            parsed_chapters, page_offset = await parse_index_chapters(
                index_text=index_text,
                pdf_page_count=total_pages,
                pdf_path=str(out_pdf),
                index_pages=index_pages,
            )
            ranges = compute_chapter_ranges(parsed_chapters, pdf_page_count=total_pages, page_offset=page_offset)
        except (IndexParseError, Exception) as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to parse index into chapters: {e}",
            )

        # Cache index extraction/parsing in DB (never re-parse).
        idx_row = TextbookIndex(
            textbook_id=textbook_id,
            index_pages=index_pages,
            index_text=index_text,
            parsed={
                "chapters": [
                    {"chapter_number": c.chapter_number, "chapter_title": c.chapter_title, "start_page": c.start_page_printed}
                    for c in parsed_chapters
                ],
                "ranges": [
                    {
                        "chapter_number": r.chapter_number,
                        "chapter_title": r.chapter_title,
                        "start_page": r.start_page,
                        "end_page": r.end_page,
                    }
                    for r in ranges
                ],
            },
            page_offset=int(page_offset),
        )
        db.add(idx_row)

        # STEP 3+4: Persist chapters with exact ranges.
        chapters_db: List[Chapter] = []
        for r in ranges:
            key = _chapter_key(textbook_id, r.chapter_number)
            ch = Chapter(
                textbook_id=textbook_id,
                chapter_number=int(r.chapter_number),
                chapter_title=str(r.chapter_title)[:300],
                chapter_key=key,
                start_page=int(r.start_page),
                end_page=int(r.end_page),
                page_count=int(r.page_count),
            )
            db.add(ch)
            chapters_db.append(ch)

        db.flush()

        # STEP 5: Chapter-level ingestion (page-range text only) + embeddings.
        from app.services.chunker import Chunk

        chunks: List[Chunk] = []
        for ch in chapters_db:
            pages = _extract_text_by_page_range(out_pdf, ch.start_page, ch.end_page)
            # Deterministic chunking by fixed page windows (no token-based chunking).
            window = 2
            for i in range(0, len(pages), window):
                group = pages[i : i + window]
                if not group:
                    continue
                p_start = group[0][0]
                p_end = group[-1][0]
                text = "\n\n".join([t for _, t in group if (t or "").strip()]).strip()
                if not text:
                    continue
                topic_key = f"{ch.chapter_key}:p{p_start}-{p_end}"
                chunk_id = f"{topic_key}:c1"
                chunks.append(
                    Chunk(
                        chunk_id=chunk_id,
                        chapter_key=ch.chapter_key,
                        chapter_title=ch.chapter_title,
                        topic_key=topic_key,
                        topic_title=f"Pages {p_start}-{p_end}",
                        page_start=int(p_start),
                        page_end=int(p_end),
                        text=text,
                    )
                )

        if not chunks:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No extractable text found in chapter page ranges")

        chunks_file = write_chunks(textbook_id, chunks)
        tb.pdf_path = str(out_pdf)
        tb.chunks_path = str(chunks_file)
        structure = build_structure(chunks)
        for ch_item in structure.get("chapters", []) or []:
            key = str(ch_item.get("key") or "")
            if key:
                ch_item["pdf_url"] = f"/api/textbooks/{textbook_id}/chapters/{key}/pdf"
        structure["textbook_id"] = textbook_id
        structure["total_pages"] = total_pages
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
            page_start=c.page_start,
            page_end=c.page_end,
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
        pass

    # Pre-compress chapter contexts (mandatory for cost savings).
    try:
        chunk_text_by_id = {c.chunk_id: c.text for c in chunks}
        structure = build_structure(chunks)
        for ch in structure.get("chapters", []) or []:
            ch_key = str(ch.get("key") or "")
            if not ch_key:
                continue
            topic_chunks: List[str] = []
            for t in ch.get("topics", []) or []:
                for cid in t.get("chunks", []) or []:
                    txt = chunk_text_by_id.get(str(cid), "")
                    if txt.strip():
                        topic_chunks.append(txt.strip())
            raw = "\n\n".join(topic_chunks)[:40000].strip()
            if not raw:
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
        pass

    # Response: chapters list for SubjectPage.
    chapters_payload = []
    structure = build_structure(chunks)
    for ch in structure.get("chapters", []):
        key = ch.get("key")
        chapters_payload.append(
            {
                "id": key,
                "name": ch.get("title"),
                "start_page": ch.get("page_start"),
                "end_page": ch.get("page_end"),
                "pageRange": {"start": ch.get("page_start"), "end": ch.get("page_end")},
                "pdfUrl": f"/api/textbooks/{textbook_id}/chapters/{key}/pdf" if key else None,
            }
        )

    return {
        "textbook_id": str(textbook_id),
        "documentId": str(textbook_id),
        "subjectId": subjectId,
        "totalPages": total_pages,
        "chapters": chapters_payload,
        "structure": structure,
    }


@router.post("/pdf")
async def ingest_pdf(
    file: UploadFile = File(...),
    # preferred name
    subject_id: Optional[str] = Form(default=None),
    # backwards-compat alias
    subjectId: Optional[str] = Form(default=None),
    # new preferred field name
    textbookName: Optional[str] = Form(default=None),
    # backwards-compat alias
    textbook_name: Optional[str] = Form(default=None),
    user: User = Depends(get_current_user),
) -> dict:
    name = textbookName or textbook_name
    sid = subjectId or subject_id
    return await _handle_ingest(user=user, file=file, subjectId=sid, textbookName=name)


@router.post("")
async def ingest_alias(
    file: UploadFile = File(...),
    subject_id: Optional[str] = Form(default=None),
    subjectId: Optional[str] = Form(default=None),
    textbookName: Optional[str] = Form(default=None),
    textbook_name: Optional[str] = Form(default=None),
    user: User = Depends(get_current_user),
) -> dict:
    name = textbookName or textbook_name
    sid = subjectId or subject_id
    return await _handle_ingest(user=user, file=file, subjectId=sid, textbookName=name)
