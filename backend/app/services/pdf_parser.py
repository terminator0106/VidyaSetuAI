"""PDF parsing utilities using PyMuPDF (fitz).

Goals:
- Extract text page-wise
- Extract basic typography signals (font size) to help detect headings

We intentionally keep the parsing robust for scanned/uneven PDFs by falling back
on plain text extraction when rich text spans are unavailable.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Tuple

import fitz  # PyMuPDF

from app.services.pdf_extraction import DEFAULT_OCR_LANGS, extract_page_text


@dataclass(frozen=True)
class PageText:
    page_number: int
    text: str
    # Approximate "headline" candidates for this page.
    heading_candidates: List[str]


def _normalize_line(line: str) -> str:
    return " ".join(line.replace("\u00a0", " ").split()).strip()


def extract_pages(pdf_path: str) -> List[PageText]:
    """Extract text and heading candidates for each page."""

    doc = fitz.open(pdf_path)
    pages: List[PageText] = []

    for i in range(doc.page_count):
        page = doc.load_page(i)

        # Try to use rich dict extraction for headings.
        heading_candidates: List[str] = []
        try:
            blocks = page.get_text("dict").get("blocks", [])
            spans: List[Tuple[float, str]] = []
            for b in blocks:
                for ln in b.get("lines", []):
                    for sp in ln.get("spans", []):
                        text = _normalize_line(str(sp.get("text", "")))
                        if not text:
                            continue
                        size = float(sp.get("size", 0.0))
                        spans.append((size, text))

            if spans:
                sizes = sorted([s for s, _ in spans])
                median = sizes[len(sizes) // 2]
                # Heading-like spans: larger than median and short.
                for size, text in spans:
                    if size >= median + 2 and 3 <= len(text) <= 80:
                        # Common junk filter
                        if text.lower().startswith("page "):
                            continue
                        heading_candidates.append(text)
        except Exception:
            heading_candidates = []

        # Always extract full text. Use OCR fallback for multilingual/scanned pages.
        extracted = extract_page_text(page, min_chars=40, ocr_langs=DEFAULT_OCR_LANGS)
        raw_text = extracted.text
        text_lines = [_normalize_line(x) for x in (raw_text or "").splitlines()]
        text = "\n".join([ln for ln in text_lines if ln])

        pages.append(PageText(page_number=i + 1, text=text, heading_candidates=_dedupe(heading_candidates)))

    doc.close()
    return pages


def extract_pdf_page_count(pdf_path: str) -> int:
    doc = fitz.open(pdf_path)
    try:
        return int(doc.page_count)
    finally:
        doc.close()


def extract_toc_chapters(pdf_path: str) -> List[Tuple[str, int, int]]:
    """Extract chapter ranges from PDF outline / table of contents.

    Returns: list of (title, start_page, end_page) where page numbers are 1-based.
    Uses the embedded outline (doc.get_toc) when available.

    If the PDF has a very dense outline (lots of sub-entries), we pick the
    shallowest level that yields a reasonable number of entries.
    """

    doc = fitz.open(pdf_path)
    try:
        page_count = int(doc.page_count)
        toc = doc.get_toc() or []
    finally:
        doc.close()

    if not toc or page_count <= 0:
        return []

    # toc items: [level, title, page]
    cleaned: List[Tuple[int, str, int]] = []
    for item in toc:
        try:
            level, title, page = int(item[0]), str(item[1] or "").strip(), int(item[2])
        except Exception:
            continue
        title = _normalize_line(title)
        if not title:
            continue
        if page < 1 or page > page_count:
            continue
        cleaned.append((level, title, page))

    if len(cleaned) < 2:
        return []

    # Pick the shallowest level that gives a usable number of entries.
    levels = sorted({lvl for (lvl, _, _) in cleaned})
    chosen_level = levels[0]
    for lvl in levels:
        entries = [(t, p) for (l, t, p) in cleaned if l == lvl]
        if 2 <= len(entries) <= 80:
            chosen_level = lvl
            break

    entries = [(t, p) for (l, t, p) in cleaned if l == chosen_level]
    if len(entries) < 2:
        # Fall back: take the first 30 entries regardless of level.
        entries = [(t, p) for (_, t, p) in cleaned[:30]]

    # Deduplicate + sort by page.
    dedup: List[Tuple[str, int]] = []
    seen = set()
    for title, start in sorted(entries, key=lambda x: (x[1], x[0].lower())):
        key = (title.lower(), int(start))
        if key in seen:
            continue
        seen.add(key)
        dedup.append((title, int(start)))

    # Drop entries that start on the same page (keep the first title).
    pruned: List[Tuple[str, int]] = []
    last_page = None
    for title, start in dedup:
        if last_page == start:
            continue
        pruned.append((title, start))
        last_page = start

    if len(pruned) < 2:
        return []

    chapters: List[Tuple[str, int, int]] = []
    for i, (title, start_page) in enumerate(pruned):
        next_start = pruned[i + 1][1] if i + 1 < len(pruned) else page_count + 1
        end_page = min(page_count, max(start_page, next_start - 1))
        chapters.append((title, start_page, end_page))

    # Remove micro-ranges that are almost certainly outline noise.
    chapters = [c for c in chapters if (c[2] - c[1] + 1) >= 2]
    return chapters


def _dedupe(items: Iterable[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for it in items:
        key = it.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(it.strip())
    return out
