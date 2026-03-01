"""Persistence helpers for ingested textbooks.

We persist:
- raw uploaded PDF under data/textbooks/<id>/source.pdf
- chunk texts + metadata under data/textbooks/<id>/chunks.json

Chunk texts are also cached in Redis for faster reads.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Tuple

import fitz  # PyMuPDF

from app.config import settings
from app.services.chunker import Chunk


def textbook_dir(textbook_id: int) -> Path:
    root = Path(settings.data_dir)
    d = root / "textbooks" / str(textbook_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def pdf_path(textbook_id: int) -> Path:
    return textbook_dir(textbook_id) / "source.pdf"


def chunks_path(textbook_id: int) -> Path:
    return textbook_dir(textbook_id) / "chunks.json"


def chapters_dir(textbook_id: int) -> Path:
    d = textbook_dir(textbook_id) / "chapters"
    d.mkdir(parents=True, exist_ok=True)
    return d


def chapter_pdf_path(textbook_id: int, chapter_key: str) -> Path:
    safe = "".join(ch for ch in chapter_key if ch.isalnum() or ch in {"_", "-"}).strip("._-")
    if not safe:
        safe = "chapter"
    return chapters_dir(textbook_id) / f"{safe}.pdf"


def split_pdf_by_chapters(
    textbook_id: int,
    source_pdf: Path,
    chapters: List[dict],
) -> Dict[str, str]:
    """Split a source PDF into per-chapter PDFs.

    chapters items must have: {"key": str, "page_start": int, "page_end": int}
    Returns mapping chapter_key -> absolute pdf path as string.
    """

    if not source_pdf.exists():
        return {}

    doc = fitz.open(str(source_pdf))
    try:
        total = int(doc.page_count)
        out: Dict[str, str] = {}
        for ch in chapters:
            key = str(ch.get("key") or "")
            if not key:
                continue
            start = int(ch.get("page_start") or 1)
            end = int(ch.get("page_end") or start)
            start = max(1, min(total, start))
            end = max(start, min(total, end))

            out_path = chapter_pdf_path(textbook_id, key)
            # Write a fresh PDF containing only the chapter pages.
            new_doc = fitz.open()
            try:
                new_doc.insert_pdf(doc, from_page=start - 1, to_page=end - 1)
                new_doc.save(str(out_path), deflate=True)
                out[key] = str(out_path)
            finally:
                new_doc.close()
        return out
    finally:
        doc.close()


def write_chunks(textbook_id: int, chunks: List[Chunk]) -> Path:
    path = chunks_path(textbook_id)
    payload = {
        "textbook_id": textbook_id,
        "chunks": [
            {
                "chunk_id": c.chunk_id,
                "chapter_key": c.chapter_key,
                "chapter_title": c.chapter_title,
                "topic_key": c.topic_key,
                "topic_title": c.topic_title,
                "page_start": c.page_start,
                "page_end": c.page_end,
                "text": c.text,
            }
            for c in chunks
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    _chunk_map.cache_clear()
    return path


@lru_cache(maxsize=64)
def _chunk_map(textbook_id: int) -> Dict[str, str]:
    path = chunks_path(textbook_id)
    raw = json.loads(path.read_text(encoding="utf-8"))
    out: Dict[str, str] = {}
    for c in raw.get("chunks", []):
        cid = str(c.get("chunk_id"))
        text = str(c.get("text") or "")
        if cid:
            out[cid] = text
    return out


def load_chunk_text(textbook_id: int, chunk_id: str) -> str:
    return _chunk_map(textbook_id).get(chunk_id, "")


def build_structure(chunks: List[Chunk]) -> dict:
    """Create chapter/topic structure for frontend and backend usage."""

    chapters: Dict[str, dict] = {}
    for c in chunks:
        ch = chapters.setdefault(
            c.chapter_key,
            {
                "key": c.chapter_key,
                "title": c.chapter_title,
                "topics": {},
                "page_start": c.page_start,
                "page_end": c.page_end,
            },
        )
        ch["page_start"] = min(int(ch["page_start"]), c.page_start)
        ch["page_end"] = max(int(ch["page_end"]), c.page_end)

        topics: Dict[str, dict] = ch["topics"]
        t = topics.setdefault(
            c.topic_key,
            {
                "key": c.topic_key,
                "title": c.topic_title,
                "page_start": c.page_start,
                "page_end": c.page_end,
                "chunks": [],
            },
        )
        t["page_start"] = min(int(t["page_start"]), c.page_start)
        t["page_end"] = max(int(t["page_end"]), c.page_end)
        t["chunks"].append(c.chunk_id)

    chapter_list = []
    for key, ch in chapters.items():
        topics_map = ch.pop("topics")
        ch["topics"] = list(topics_map.values())
        chapter_list.append(ch)

    # stable-ish ordering
    chapter_list.sort(key=lambda x: (x.get("page_start", 0), x.get("title", "")))
    return {"chapters": chapter_list}
