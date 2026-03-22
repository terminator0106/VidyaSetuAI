"""Ingestion API.

POST /api/ingest/pdf - multipart upload
POST /api/ingest     - alias

IMPORTANT:
- Chapters are created strictly from the PDF Index/Table of Contents pages.
- No heuristic chapter guessing is allowed.
- Groq is permitted ONLY as a fallback for parsing complex index formatting.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.database import db_session
from app.models.chapter import Chapter
from app.models.textbook import Textbook
from app.models.subject import Subject
from app.models.textbook_index import TextbookIndex
from app.models.user import User
from app.redis_client import get_redis
from app.services.cache_keys import chapter_compressed_key, chapter_raw_key, chunk_key
from app.services.embedder import embed_texts
from app.services.pdf_parser import extract_pdf_page_count
from app.services.pdf_extraction import extract_text_by_page_range
from app.services.index_splitter import (
    ChapterRange,
    IndexNotFoundError,
    IndexParseError,
    compute_chapter_ranges,
    extract_index_text,
    parse_index_chapters,
)
from app.services.cloudinary_storage import CloudinaryStorageError, upload_pdf
from app.services.textbook_store import build_structure, pdf_path, write_chunks
from app.services.vector_store import VectorMeta, get_store
from app.services.llm_client import chat_text
from app.services.text_translation import translate_chunk_to_english
from app.config import settings
from app.utils.security import get_current_user

router = APIRouter(prefix="/ingest", tags=["ingest"])

logger = logging.getLogger(__name__)


def _chapter_key(textbook_id: int, chapter_number: int) -> str:
    """Stable chapter identifier used across APIs + vector metadata."""

    return f"tb{textbook_id}_ch{int(chapter_number):02d}"


def _sanitize_subject(subject_id: Optional[str]) -> str:
    """Sanitize a subject identifier for filenames/public IDs."""

    raw = (subject_id or "").strip().lower()
    if not raw:
        return "subject"
    out = []
    for ch in raw:
        if ch.isalnum():
            out.append(ch)
        elif ch in {"_", "-"}:
            out.append(ch)
        else:
            out.append("_")
    cleaned = "".join(out).strip("_-")
    return cleaned or "subject"


def _sanitize_component(raw: Optional[str], *, default: str) -> str:
    """Sanitize a path component for Cloudinary public IDs."""

    val = (raw or "").strip().lower()
    if not val:
        return default
    out = []
    for ch in val:
        if ch.isalnum():
            out.append(ch)
        elif ch in {"_", "-"}:
            out.append(ch)
        elif ch.isspace() or ch in {"/", "\\", "."}:
            out.append("_")
        else:
            out.append("_")
    cleaned = "".join(out)
    cleaned = "_".join([p for p in cleaned.split("_") if p])
    cleaned = cleaned.strip("_-")
    return cleaned or default


def _cloudinary_is_configured() -> bool:
    """Return True if Cloudinary credentials are configured."""

    return bool(
        (settings.CLOUDINARY_CLOUD_NAME or "").strip()
        and (settings.CLOUDINARY_API_KEY or "").strip()
        and (settings.CLOUDINARY_API_SECRET or "").strip()
    )


def _tmp_chapters_dir() -> Path:
    """Return the temp directory used for per-chapter PDFs.

    Spec requires `/tmp/chapters/`.
    On Windows, this resolves to a path under the current drive root.
    """

    d = Path("/tmp/chapters")
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write_chapter_pdfs_to_tmp(
    source_pdf: Path,
    subject_id: Optional[str],
    ranges: List[ChapterRange],
) -> List[Path]:
    """Generate per-chapter PDFs into `/tmp/chapters/`.

    Naming convention: `{subject}_ch{chapter_number}.pdf`.

    Returns:
        List of written file paths, in chapter order.
    """

    import fitz

    subject = _sanitize_subject(subject_id)
    out_dir = _tmp_chapters_dir()
    written: List[Path] = []

    doc = fitz.open(str(source_pdf))
    try:
        total = int(doc.page_count)
        for r in ranges:
            start = max(1, min(total, int(r.start_page)))
            end = max(start, min(total, int(r.end_page)))

            out_path = out_dir / f"{subject}_ch{int(r.chapter_number)}.pdf"
            new_doc = fitz.open()
            try:
                new_doc.insert_pdf(doc, from_page=start - 1, to_page=end - 1)
                new_doc.save(str(out_path), deflate=True)
            finally:
                new_doc.close()

            written.append(out_path)
    finally:
        doc.close()

    return written


def _extract_text_by_page_range(pdf_file: Path, start_page: int, end_page: int) -> List[tuple[int, str]]:
    """Extract text for each page in [start_page, end_page] inclusive.

    Uses OCR fallback for multilingual/scanned PDFs.
    """

    return extract_text_by_page_range(
        str(pdf_file),
        start_page=int(start_page),
        end_page=int(end_page),
    )


async def _handle_ingest(
    user: User,
    file: UploadFile,
    subjectId: Optional[str] = None,
    textbookName: Optional[str] = None,
) -> dict:
    t0 = time.monotonic()

    chapter_pdf_metadata: List[dict] = []

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Please upload a PDF file")

    logger.info(
        "Ingest started",
        extra={
            "extra": {
                "user_id": int(user.id),
                "subject_id": str(subjectId or ""),
                "filename": str(file.filename or ""),
            }
        },
    )

    try:
        # Variables populated inside the DB transaction and used after.
        textbook_id: int
        total_pages: int
        out_pdf: Path
        ranges: List[ChapterRange]
        chunks: List[Any]

        with db_session() as db:
            # Backwards-compat: if the frontend passes a subjectId but the subject
            # wasn't created via /subjects yet, create a minimal subject row.
            if subjectId:
                existing_subject = (
                    db.query(Subject)
                    .filter(Subject.user_id == int(user.id), Subject.id == str(subjectId))
                    .first()
                )
                if existing_subject is None:
                    db.add(Subject(id=str(subjectId), user_id=int(user.id), name=str(subjectId)[:120], icon="📖"))

            tb = Textbook(
                subject_id=str(subjectId) if subjectId else None,
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

            total_pages = int(extract_pdf_page_count(str(out_pdf)))
            logger.info(
                "Ingest PDF saved",
                extra={"extra": {"textbook_id": textbook_id, "total_pages": int(total_pages)}},
            )

            # STEP 1: Detect index pages and extract raw text.
            try:
                index_pages, index_text = extract_index_text(str(out_pdf), max_pages=25)
                logger.info(
                    "Ingest index detected",
                    extra={
                        "extra": {
                            "textbook_id": textbook_id,
                            "index_pages": list(index_pages),
                            "index_len": len(index_text or ""),
                        }
                    },
                )
            except IndexNotFoundError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Index/Table of Contents not found: {e}",
                )
            except RuntimeError as e:
                # Typically indicates unreadable PDF text + OCR not available/failed.
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(e),
                )

            # STEP 2: Parse index into chapters.
            try:
                parsed_chapters, page_offset = await parse_index_chapters(
                    index_text=index_text,
                    pdf_page_count=total_pages,
                    pdf_path=str(out_pdf),
                    index_pages=index_pages,
                )
                ranges = compute_chapter_ranges(parsed_chapters, pdf_page_count=total_pages, page_offset=page_offset)
                logger.info(
                    "Ingest index parsed",
                    extra={
                        "extra": {
                            "textbook_id": textbook_id,
                            "chapters": len(parsed_chapters),
                            "offset": int(page_offset),
                        }
                    },
                )
            except (IndexParseError, Exception) as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to parse index into chapters: {e}",
                )

            # STEP 2b: Generate chapter PDFs into /tmp/chapters and upload.
            if not _cloudinary_is_configured():
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=(
                        "Cloudinary is not configured. Set CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, "
                        "and CLOUDINARY_API_SECRET in backend/.env."
                    ),
                )

            subject_slug = _sanitize_component(subjectId, default="subject")

            tmp_paths: List[Path] = []
            try:
                tmp_paths = _write_chapter_pdfs_to_tmp(out_pdf, subjectId, list(ranges))

                for r in ranges:
                    chapter_number = int(r.chapter_number)
                    public_id = f"{subject_slug}_ch{chapter_number}"

                    local_path = _tmp_chapters_dir() / f"{_sanitize_subject(subjectId)}_ch{chapter_number}.pdf"
                    try:
                        url = upload_pdf(file_path=str(local_path), public_id=public_id)
                        chapter_pdf_metadata.append(
                            {
                                "chapter_title": str(r.chapter_title),
                                "chapter_number": chapter_number,
                                "cloudinary_url": url,
                            }
                        )
                    except CloudinaryStorageError as e:
                        raise HTTPException(
                            status_code=status.HTTP_502_BAD_GATEWAY,
                            detail=f"Failed to upload chapter PDF to Cloudinary: {e}",
                        )
                    finally:
                        try:
                            local_path.unlink(missing_ok=True)
                        except Exception:
                            pass
            finally:
                for p in tmp_paths:
                    try:
                        p.unlink(missing_ok=True)
                    except Exception:
                        pass

            # Cache index extraction/parsing in DB (never re-parse).
            idx_row = TextbookIndex(
                textbook_id=textbook_id,
                index_pages=index_pages,
                index_text=index_text,
                parsed={
                    "chapters": [
                        {
                            "chapter_number": c.chapter_number,
                            "chapter_title": c.chapter_title,
                            "start_page": c.start_page_printed,
                        }
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

            # STEP 3+4: Persist chapters with exact ranges (upsert; no duplicates).
            cloud_url_by_num = {
                int(item.get("chapter_number")): str(item.get("cloudinary_url") or "")
                for item in chapter_pdf_metadata
                if item.get("chapter_number") is not None
            }

            existing_rows: List[Chapter] = list(db.query(Chapter).filter(Chapter.textbook_id == textbook_id).all())
            existing_by_num = {int(c.chapter_number): c for c in existing_rows}

            chapters_db: List[Chapter] = []
            for r in ranges:
                ch_num = int(r.chapter_number)
                key = _chapter_key(textbook_id, ch_num)
                cloud_url = (cloud_url_by_num.get(ch_num) or "").strip() or None

                existing = existing_by_num.get(ch_num)
                if existing is not None:
                    existing.subject_id = subjectId
                    existing.chapter_title = str(r.chapter_title)[:300]
                    existing.chapter_key = key
                    existing.start_page = int(r.start_page)
                    existing.end_page = int(r.end_page)
                    existing.page_count = int(r.page_count)
                    if cloud_url:
                        existing.cloudinary_url = cloud_url
                    chapters_db.append(existing)
                else:
                    ch = Chapter(
                        textbook_id=textbook_id,
                        subject_id=subjectId,
                        chapter_number=ch_num,
                        chapter_title=str(r.chapter_title)[:300],
                        chapter_key=key,
                        start_page=int(r.start_page),
                        end_page=int(r.end_page),
                        page_count=int(r.page_count),
                        cloudinary_url=cloud_url,
                    )
                    db.add(ch)
                    chapters_db.append(ch)

            db.flush()

            # STEP 5: Chapter-level ingestion (page-range text only) + embeddings.
            from app.services.chunker import Chunk

            chunks = []
            original_texts: List[str] = []
            for ch in chapters_db:
                try:
                    pages = _extract_text_by_page_range(out_pdf, ch.start_page, ch.end_page)
                except RuntimeError as e:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=str(e),
                    )

                window = 1
                for i in range(0, len(pages), window):
                    group = pages[i : i + window]
                    if not group:
                        continue
                    p_start = group[0][0]
                    p_end = group[-1][0]
                    text_original = "\n\n".join([t for _, t in group if (t or "").strip()]).strip()
                    if not text_original:
                        continue

                    text_en = await translate_chunk_to_english(text=text_original)
                    text = (text_en or "").strip() or text_original
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
                    original_texts.append(text_original)

            if not chunks:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No extractable text found in chapter page ranges",
                )

            logger.info(
                "Ingest chunks built",
                extra={
                    "extra": {
                        "textbook_id": textbook_id,
                        "chunks": len(chunks),
                        "elapsed_s": round(time.monotonic() - t0, 2),
                    }
                },
            )

            chunks_file = write_chunks(textbook_id, chunks, original_texts=original_texts)
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

        # Build vectors + add to FAISS (outside the DB transaction).
        texts = [c.text for c in chunks]
        logger.info(
            "Ingest embedding started",
            extra={"extra": {"textbook_id": textbook_id, "chunks": len(texts), "elapsed_s": round(time.monotonic() - t0, 2)}},
        )
        vectors = embed_texts(texts)
        logger.info(
            "Ingest embedding complete",
            extra={"extra": {"textbook_id": textbook_id, "vectors": int(getattr(vectors, "shape", [0])[0]), "elapsed_s": round(time.monotonic() - t0, 2)}},
        )

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
                raw = raw[:20000].strip()
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
                comp = await chat_text(model=settings.model_small, messages=messages, temperature=0.0)
                if comp.text.strip():
                    await r.set(chapter_compressed_key(ch_key), comp.text.strip())
        except Exception:
            pass

        # Response: chapters list for SubjectPage.
        chapters_payload: List[dict] = []
        structure = build_structure(chunks)
        for ch in structure.get("chapters", []):
            key = ch.get("key")
            ch_num: Optional[int] = None
            try:
                if isinstance(key, str) and "_ch" in key:
                    ch_num = int(key.split("_ch", 1)[1])
            except Exception:
                ch_num = None

            cloudinary_url: Optional[str] = None
            if ch_num is not None:
                for item in chapter_pdf_metadata:
                    if int(item.get("chapter_number") or -1) == ch_num:
                        cloudinary_url = str(item.get("cloudinary_url") or "") or None
                        break

            chapters_payload.append(
                {
                    "id": key,
                    "name": ch.get("title"),
                    "start_page": ch.get("page_start"),
                    "end_page": ch.get("page_end"),
                    "pageRange": {"start": ch.get("page_start"), "end": ch.get("page_end")},
                    "pdfUrl": f"/api/textbooks/{textbook_id}/chapters/{key}/pdf" if key else None,
                    "cloudinary_url": cloudinary_url,
                }
            )

        logger.info(
            "Ingest completed",
            extra={"extra": {"textbook_id": textbook_id, "elapsed_s": round(time.monotonic() - t0, 2)}},
        )

        return {
            "textbook_id": str(textbook_id),
            "documentId": str(textbook_id),
            "subjectId": subjectId,
            "totalPages": total_pages,
            "chapters": chapters_payload,
            "chapter_pdfs": chapter_pdf_metadata,
            "structure": structure,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            "Ingest failed",
            extra={
                "extra": {
                    "user_id": int(user.id),
                    "subject_id": str(subjectId or ""),
                    "filename": str(file.filename or ""),
                    "err": str(e),
                }
            },
        )
        raise


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
