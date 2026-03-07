"""Index-aware PDF chapter splitter.

This module implements chapter splitting based ONLY on the PDF's Index/Table of
Contents pages.

Requirements (strict):
- Detect the index page within the first N pages by keyword match.
- Parse chapter titles and page numbers using regex (no heading/outline guessing).
- Compute chapter page ranges: end = next_start - 1, last = total pages.
- Pages before the first chapter are implicitly ignored.

Note: This module intentionally does not use LLMs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

import fitz  # PyMuPDF


_INDEX_KEYWORDS = ("table of contents", "contents", "index")

# Example pattern:
#   Chapter 1 .......... 3
# Captures:
#   group(1) = chapter title text (including "Chapter 1" prefix)
#   group(2) = start page number
_CHAPTER_LINE_RE = re.compile(r"(chapter\s*\d+.*?)\s+(\d+)\s*$", re.IGNORECASE)
_CHAPTER_NUM_RE = re.compile(r"chapter\s*(\d+)", re.IGNORECASE)


@dataclass(frozen=True)
class ParsedIndexChapter:
    chapter_number: int
    chapter_title: str
    start_page_printed: int


@dataclass(frozen=True)
class ChapterRange:
    chapter_number: int
    chapter_title: str
    start_page: int  # 1-based PDF page
    end_page: int  # 1-based PDF page

    @property
    def page_count(self) -> int:
        return int(self.end_page) - int(self.start_page) + 1


class IndexNotFoundError(RuntimeError):
    """Raised when index/contents pages cannot be detected."""


class IndexParseError(RuntimeError):
    """Raised when index text cannot be parsed into chapters."""


def extract_index_text(pdf_path: str, max_pages: int = 60) -> Tuple[List[int], str]:
    """Detect the index page from the first `max_pages` pages.

    Detection rule (strict): choose the first page whose extracted text contains
    one of the index keywords: "contents", "table of contents", "index".

    Returns:
        (page_numbers_1_based, index_text)
    """

    doc = fitz.open(pdf_path)
    try:
        limit = min(int(max_pages), int(doc.page_count))
        if limit <= 0:
            raise IndexNotFoundError("PDF has no pages")

        # We avoid false positives by requiring a page to look like a ToC:
        # lots of lines ending in page numbers and dot-leaders/tabs.
        #
        # Heuristic:
        # - Prefer pages with an index keyword AND at least a few index-like lines.
        # - Only fall back to non-keyword pages if they look *very* index-like.
        min_hits_keyword = 3
        min_hits_no_keyword = 8

        best: tuple[int, int, int, str] | None = None  # (page_idx0, score, hits, text)

        for i in range(limit):
            page = doc.load_page(i)
            txt = (page.get_text("text") or "").strip()
            if not txt:
                continue

            nt = _normalize(txt).lower()
            hits = _count_index_like_lines(txt)

            has_kw = 1 if any(k in nt for k in _INDEX_KEYWORDS) else 0
            # Keyword presence is a strong signal.
            score = hits + (10 * has_kw)

            # Reject weak candidates early.
            if has_kw and hits < min_hits_keyword:
                continue
            if not has_kw and hits < min_hits_no_keyword:
                continue

            if best is None or score > best[1]:
                best = (i, score, hits, txt)

        if best is None:
            raise IndexNotFoundError(
                f"Could not detect an index/table of contents page in the first {limit} pages"
            )

        i, _score, _hits, txt = best

        # Best-effort: index/contents often spans multiple pages.
        pages_1b: List[int] = [i + 1]
        combined: List[str] = [txt.strip()]
        for j in range(i + 1, min(limit, i + 5)):
            nxt = (doc.load_page(j).get_text("text") or "").strip()
            if not nxt:
                break
            if _count_index_like_lines(nxt) < min_hits_keyword:
                break
            pages_1b.append(j + 1)
            combined.append(nxt)

        return pages_1b, "\n".join(combined).strip()
    finally:
        doc.close()


async def parse_index_chapters(
    index_text: str,
    pdf_page_count: int,
    pdf_path: str,
    index_pages: Sequence[int] | None = None,
) -> Tuple[List[ParsedIndexChapter], int]:
    """Parse index text into a chapter list using regex only.

    The index page numbers are treated as 1-based PDF page numbers.

    Returns:
        (chapters, page_offset)
        page_offset is always 0 in this strict mode.
    """

    chapters = _parse_index_regex(index_text)
    if not chapters:
        raise IndexParseError("No chapters found in index")

    # IMPORTANT: start_page_printed comes from the textbook's printed page
    # numbers in the ToC, which often do NOT match the PDF page index.
    # We estimate an offset by reading header/footer page numbers from the PDF.
    offset = _estimate_pdf_page_offset(
        pdf_path=pdf_path,
        pdf_page_count=int(pdf_page_count),
        chapter_start_pages_printed=[c.start_page_printed for c in chapters],
        index_pages=index_pages,
    )

    starts_pdf = [int(c.start_page_printed) + int(offset) for c in chapters]
    if any(p < 1 or p > int(pdf_page_count) for p in starts_pdf):
        raise IndexParseError(
            "Parsed chapters have out-of-range start pages after applying offset "
            f"(offset={offset})."
        )
    if not _is_strictly_ascending(starts_pdf):
        raise IndexParseError(
            "Parsed chapters have non-ascending start pages after applying offset "
            f"(offset={offset})."
        )

    return chapters, int(offset)


def compute_chapter_ranges(
    chapters: Sequence[ParsedIndexChapter],
    pdf_page_count: int,
    page_offset: int,
) -> List[ChapterRange]:
    """Compute (start,end) PDF page ranges from printed start pages."""

    out: List[ChapterRange] = []
    starts = [c.start_page_printed + page_offset for c in chapters]

    for i, c in enumerate(chapters):
        start_pdf = starts[i]
        next_start = starts[i + 1] if i + 1 < len(starts) else pdf_page_count + 1
        end_pdf = min(pdf_page_count, max(start_pdf, next_start - 1))
        out.append(
            ChapterRange(
                chapter_number=int(c.chapter_number),
                chapter_title=str(c.chapter_title),
                start_page=int(start_pdf),
                end_page=int(end_pdf),
            )
        )

    # Drop any degenerate ranges (should not happen after validation).
    out = [c for c in out if c.page_count >= 1]
    return out


def _parse_index_regex(index_text: str) -> List[ParsedIndexChapter]:
    """Parse chapter entries from index text using regex.

    Expected ToC line format (example):
        Chapter 1 .......... 3

    Returns:
        List of ParsedIndexChapter sorted by chapter_number.
    """

    lines = [_normalize(ln) for ln in (index_text or "").splitlines()]
    lines = [ln for ln in lines if ln]

    entries: List[ParsedIndexChapter] = []

    # Pass 1: strict "Chapter N ... 12" lines.
    for ln in lines:
        m = _CHAPTER_LINE_RE.search(ln)
        if not m:
            continue

        raw_title = _normalize(m.group(1))
        raw_page = m.group(2)
        try:
            start_page = int(raw_page)
        except Exception:
            continue

        num_match = _CHAPTER_NUM_RE.search(raw_title)
        if not num_match:
            continue
        chapter_number = int(num_match.group(1))

        title = re.sub(r"^chapter\s*\d+\s*[:\-\.]*\s*", "", raw_title, flags=re.IGNORECASE).strip()
        if not title:
            title = raw_title

        entries.append(
            ParsedIndexChapter(
                chapter_number=chapter_number,
                chapter_title=title[:300],
                start_page_printed=start_page,
            )
        )

    # Pass 2: flexible ToC lines (regex-only), supports:
    # - "Unit 1 ... 3"
    # - "1. Matter ... 10"
    # - roman numerals for pages
    if not entries:
        entries = _parse_index_flexible(lines)

    if not entries:
        return []

    dedup: dict[int, ParsedIndexChapter] = {}
    for e in entries:
        dedup.setdefault(int(e.chapter_number), e)
    out = list(dedup.values())
    out.sort(key=lambda x: x.chapter_number)
    return out


def _parse_index_flexible(lines: Sequence[str]) -> List[ParsedIndexChapter]:
    entries: List[ParsedIndexChapter] = []

    for ln in lines:
        if not ln:
            continue

        # Only consider lines that resemble ToC entries, otherwise we may
        # misinterpret syllabus codes like "08.72.10" as page numbers.
        if not (_ends_with_page_number(ln) and ("." in ln or "\t" in ln or "  " in ln)):
            continue

        title_part, page_part = _split_title_page(ln)
        if not title_part or not page_part:
            continue

        page_num = _parse_page_number(page_part)
        if page_num is None:
            continue

        chapter_num, title = _extract_chapter_number_and_title(title_part)
        if chapter_num is None:
            continue

        clean_title = (title or "").strip() or title_part
        entries.append(
            ParsedIndexChapter(
                chapter_number=int(chapter_num),
                chapter_title=str(clean_title)[:300],
                start_page_printed=int(page_num),
            )
        )

    if not entries:
        return []

    # De-dup and keep the first occurrence.
    dedup: dict[int, ParsedIndexChapter] = {}
    for e in entries:
        dedup.setdefault(int(e.chapter_number), e)
    out = list(dedup.values())
    out.sort(key=lambda x: x.chapter_number)
    return out


def _count_index_like_lines(text: str) -> int:
    lines = [_normalize(ln) for ln in (text or "").splitlines()]
    hits = 0
    for ln in lines:
        if not ln:
            continue
        if _ends_with_page_number(ln) and ("." in ln or "\t" in ln or "  " in ln):
            hits += 1
    return hits


def _ends_with_page_number(line: str) -> bool:
    return bool(re.search(r"(?:\s|\.)+([0-9]{1,4}|[ivxlcdmIVXLCDM]{1,8})\s*$", line))


def _extract_printed_page_number_from_page(page: fitz.Page) -> Optional[int]:
    """Try to read the printed page number from header/footer.

    We look at the top/bottom bands of the page and try to find a line whose
    content is just a page number (or contains an isolated page number token).
    """

    try:
        rect = page.rect
        w = float(rect.width)
        h = float(rect.height)
        if w <= 0 or h <= 0:
            return None

        # Header: top 15%, Footer: bottom 15%
        header = page.get_text(
            "text",
            clip=fitz.Rect(0, 0, w, h * 0.15),
            flags=fitz.TEXT_PRESERVE_LIGATURES,
        )
        footer = page.get_text(
            "text",
            clip=fitz.Rect(0, h * 0.85, w, h),
            flags=fitz.TEXT_PRESERVE_LIGATURES,
        )
        blob = "\n".join([header or "", footer or ""]).strip()
        if not blob:
            return None

        # Prefer lines that are only a number.
        for ln in [x.strip() for x in blob.splitlines() if x.strip()]:
            if re.fullmatch(r"\d{1,4}", ln):
                return int(ln)

        # Fallback: find isolated numeric tokens, but avoid syllabus-like codes
        # such as 08.72.10 by requiring token boundaries.
        m = re.search(r"(?<![0-9\.])(\d{1,4})(?![0-9\.])", blob)
        if m:
            return int(m.group(1))
    except Exception:
        return None

    return None


def _mode_int(values: Sequence[int]) -> Optional[int]:
    if not values:
        return None
    counts: dict[int, int] = {}
    for v in values:
        counts[int(v)] = counts.get(int(v), 0) + 1
    # Highest count; deterministic tie-break by smaller abs value.
    return max(counts.items(), key=lambda kv: (kv[1], -abs(kv[0]), -kv[0]))[0]


def _estimate_pdf_page_offset(
    *,
    pdf_path: str,
    pdf_page_count: int,
    chapter_start_pages_printed: Sequence[int],
    index_pages: Sequence[int] | None,
    max_scan_pages: int = 120,
) -> int:
    """Estimate offset mapping printed textbook page numbers -> PDF pages.

    We assume a mostly constant offset for the main content:
        pdf_page ~= printed_page + offset

    We compute offset by scanning header/footer printed page numbers in the PDF
    and taking the mode of (pdf_page_index - printed_page).

    If no reliable mapping is found, returns 0.
    """

    _ = index_pages  # reserved for future improvements

    total = int(pdf_page_count)
    limit = min(int(max_scan_pages), total)
    if limit <= 0:
        return 0

    # Only consider printed pages in a plausible range around chapter starts.
    # This avoids grabbing random numbers from the foreword/syllabus pages.
    printed = [int(p) for p in chapter_start_pages_printed if int(p) > 0]
    if printed:
        min_p = min(printed)
        max_p = max(printed)
    else:
        min_p, max_p = 1, total

    diffs: list[int] = []

    doc = fitz.open(pdf_path)
    try:
        for pdf_page in range(1, limit + 1):
            page = doc.load_page(pdf_page - 1)
            pnum = _extract_printed_page_number_from_page(page)
            if pnum is None:
                continue
            if pnum < max(1, min_p - 10) or pnum > (max_p + 10):
                continue
            diffs.append(int(pdf_page) - int(pnum))
    finally:
        doc.close()

    # If we couldn't detect any printed numbers, fall back.
    off = _mode_int(diffs)
    return int(off) if off is not None else 0


def _split_title_page(line: str) -> Tuple[Optional[str], Optional[str]]:
    # Remove dot leaders
    cleaned = re.sub(r"\.{2,}", " ", line).strip()
    m = re.search(r"([0-9]{1,4}|[ivxlcdmIVXLCDM]{1,8})\s*$", cleaned)
    if not m:
        return None, None
    page_part = m.group(1)
    title_part = cleaned[: m.start(1)].strip(" -:\t")
    if not title_part:
        return None, None
    return title_part, page_part


def _extract_chapter_number_and_title(title_part: str) -> Tuple[Optional[int], str]:
    t = title_part.strip()

    m = re.match(r"^(chapter|unit)\s+([0-9ivxlcdmIVXLCDM]+)\b\s*[:\-\.]?\s*(.*)$", t, re.IGNORECASE)
    if m:
        cn = _parse_chapter_number(m.group(2))
        rest = (m.group(3) or "").strip()
        return cn, rest if rest else t

    m = re.match(r"^([0-9]{1,3})\s*[\.|\-|\)|:]\s*(.*)$", t)
    if m:
        cn = int(m.group(1))
        rest = (m.group(2) or "").strip()
        return cn, rest if rest else t

    m = re.match(r"^([0-9]{1,3})\s+(.*)$", t)
    if m:
        cn = int(m.group(1))
        rest = (m.group(2) or "").strip()
        return cn, rest if rest else t

    # Not a chapter-like entry.
    return None, t


def _parse_chapter_number(raw: str) -> Optional[int]:
    raw = (raw or "").strip()
    if not raw:
        return None
    if raw.isdigit():
        return int(raw)
    v = _roman_to_int(raw)
    return v


def _parse_page_number(raw: str) -> Optional[int]:
    raw = (raw or "").strip()
    if not raw:
        return None
    if raw.isdigit():
        return int(raw)
    return _roman_to_int(raw)


def _roman_to_int(s: str) -> Optional[int]:
    s = re.sub(r"[^ivxlcdmIVXLCDM]", "", s or "")
    if not s:
        return None
    s = s.upper()
    values = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    total = 0
    prev = 0
    for ch in reversed(s):
        v = values.get(ch)
        if v is None:
            return None
        if v < prev:
            total -= v
        else:
            total += v
            prev = v
    if total <= 0:
        return None
    return total


def _normalize(s: str) -> str:
    return " ".join((s or "").replace("\u00a0", " ").split()).strip()


def _is_strictly_ascending(nums: Sequence[int]) -> bool:
    return all(int(nums[i]) < int(nums[i + 1]) for i in range(len(nums) - 1))
