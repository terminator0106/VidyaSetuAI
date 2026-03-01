"""Chapter-aware chunking.

We do NOT blindly chunk by tokens.
Instead we:
- Detect chapter boundaries using heading/page signals
- Within chapters, detect sub-topic headings when possible
- Fall back to paragraph grouping when headings are weak

Output chunks are sized to be retrieval-friendly and compressible.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Tuple

from app.services.pdf_parser import PageText


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    chapter_key: str
    chapter_title: str
    topic_key: str
    topic_title: str
    page_start: int
    page_end: int
    text: str


_CHAPTER_PATTERNS = [
    re.compile(r"^chapter\s+\d+\b", re.IGNORECASE),
    re.compile(r"^unit\s+\d+\b", re.IGNORECASE),
]


def detect_chapters(pages: List[PageText]) -> List[Tuple[str, int, int]]:
    """Return (chapter_title, start_page, end_page) using heading candidates + text.

    Heuristics:
    - Look for lines/candidates with 'Chapter N' or 'Unit N'
    - If absent, use large heading candidates and spacing
    """

    chapter_starts: List[Tuple[int, str]] = []

    for p in pages:
        candidates = list(p.heading_candidates)
        # also scan first ~20 lines
        head_lines = [ln for ln in p.text.splitlines()[:20] if ln]
        candidates.extend(head_lines)

        best = _pick_chapter_heading(candidates)
        if best:
            chapter_starts.append((p.page_number, best))

    # Dedupe close starts (some PDFs repeat chapter title on multiple pages)
    chapter_starts.sort(key=lambda x: x[0])
    filtered: List[Tuple[int, str]] = []
    for page_no, title in chapter_starts:
        if filtered and page_no - filtered[-1][0] <= 1:
            continue
        filtered.append((page_no, title))

    if not filtered:
        # Fallback: single "chapter" is entire document.
        return [("Textbook", 1, pages[-1].page_number if pages else 1)]

    chapters: List[Tuple[str, int, int]] = []
    for i, (start, title) in enumerate(filtered):
        end = (filtered[i + 1][0] - 1) if i + 1 < len(filtered) else pages[-1].page_number
        chapters.append((title, start, max(start, end)))

    return chapters


def chunk_by_topics(
    pages: List[PageText],
    chapters: List[Tuple[str, int, int]] | None = None,
) -> List[Chunk]:
    """Build chunks from pages using chapter boundaries and topic headings.

    If `chapters` is provided, it must be a list of (title, start_page, end_page)
    with 1-based page numbers.
    """

    chapters = chapters or detect_chapters(pages)
    chunks: List[Chunk] = []

    for chapter_index, (chapter_title, start_page, end_page) in enumerate(chapters, start=1):
        chapter_key = f"ch{chapter_index}"
        chapter_pages = [p for p in pages if start_page <= p.page_number <= end_page]

        topic_segments = _detect_topics_within(chapter_pages)
        if not topic_segments:
            # Paragraph fallback: group pages into 1-2 page chunks.
            topic_segments = [("Topic", chapter_pages[0].page_number, chapter_pages[-1].page_number)]

        for topic_index, (topic_title, t_start, t_end) in enumerate(topic_segments, start=1):
            topic_key = f"{chapter_key}_t{topic_index}"
            segment_pages = [p for p in chapter_pages if t_start <= p.page_number <= t_end]
            text = _merge_pages(segment_pages)
            if not text.strip():
                continue

            # If huge, split by paragraphs but keep boundaries meaningful.
            for split_i, split_text in enumerate(_split_paragraphwise(text, max_chars=7000), start=1):
                chunk_id = f"{topic_key}_{split_i}"
                chunks.append(
                    Chunk(
                        chunk_id=chunk_id,
                        chapter_key=chapter_key,
                        chapter_title=chapter_title,
                        topic_key=topic_key,
                        topic_title=topic_title,
                        page_start=t_start,
                        page_end=t_end,
                        text=split_text,
                    )
                )

    return chunks


def _pick_chapter_heading(candidates: List[str]) -> str | None:
    for c in candidates:
        cc = c.strip()
        if not cc:
            continue
        if any(p.match(cc) for p in _CHAPTER_PATTERNS):
            return _titlecase_preserve(cc)

    # If no explicit "chapter" markers, pick a short title-like heading.
    for c in candidates:
        cc = c.strip()
        if 8 <= len(cc) <= 60 and _looks_like_heading(cc):
            return _titlecase_preserve(cc)

    return None


def _looks_like_heading(line: str) -> bool:
    # Avoid sentences.
    if line.endswith("."):
        return False
    if sum(ch.isalpha() for ch in line) < 4:
        return False
    # Many headings are Title Case or ALL CAPS.
    alpha = "".join(ch for ch in line if ch.isalpha() or ch.isspace()).strip()
    if not alpha:
        return False
    words = alpha.split()
    if len(words) > 10:
        return False
    all_caps = alpha.upper() == alpha and len(alpha) >= 6
    titleish = sum(w[:1].isupper() for w in words) >= max(2, len(words) // 2)
    return all_caps or titleish


def _titlecase_preserve(text: str) -> str:
    # Keep existing casing if it is already a heading.
    return re.sub(r"\s+", " ", text).strip()


def _detect_topics_within(chapter_pages: List[PageText]) -> List[Tuple[str, int, int]]:
    """Detect topic boundaries using heading candidates inside a chapter."""

    # Collect candidate headings per page.
    candidates: List[Tuple[int, str]] = []
    for p in chapter_pages:
        for h in p.heading_candidates[:6]:
            hh = h.strip()
            if 6 <= len(hh) <= 80 and _looks_like_heading(hh):
                candidates.append((p.page_number, _titlecase_preserve(hh)))

    candidates.sort(key=lambda x: x[0])

    # Drop first candidate if it equals chapter title repeated.
    pruned: List[Tuple[int, str]] = []
    for page_no, title in candidates:
        if pruned and page_no == pruned[-1][0] and title.lower() == pruned[-1][1].lower():
            continue
        if pruned and page_no - pruned[-1][0] <= 0:
            continue
        pruned.append((page_no, title))

    # If topics are too dense, treat as noise.
    if len(pruned) >= max(8, len(chapter_pages) // 2):
        return []

    if not pruned:
        return []

    segments: List[Tuple[str, int, int]] = []
    for i, (start, title) in enumerate(pruned):
        end = (pruned[i + 1][0] - 1) if i + 1 < len(pruned) else chapter_pages[-1].page_number
        segments.append((title, start, max(start, end)))

    # Ensure coverage of early pages
    first_page = chapter_pages[0].page_number
    if segments and segments[0][1] > first_page:
        segments.insert(0, ("Overview", first_page, segments[0][1] - 1))

    return segments


def _merge_pages(pages: List[PageText]) -> str:
    parts: List[str] = []
    for p in pages:
        if p.text.strip():
            parts.append(p.text.strip())
    return "\n\n".join(parts)


def _split_paragraphwise(text: str, max_chars: int) -> List[str]:
    paras = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    if not paras:
        return [text]

    out: List[str] = []
    buf: List[str] = []
    size = 0
    for para in paras:
        if size + len(para) + 2 > max_chars and buf:
            out.append("\n\n".join(buf).strip())
            buf = []
            size = 0
        buf.append(para)
        size += len(para) + 2

    if buf:
        out.append("\n\n".join(buf).strip())

    return out
