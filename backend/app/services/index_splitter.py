"""Index-aware PDF chapter splitter.

This module implements strict, deterministic chapter splitting based ONLY on
the PDF's Index/Table of Contents pages (not outline metadata, not heuristics).

Pipeline:
1) Detect index page(s) in the first N pages using keywords + line structure.
2) Parse chapter titles + start pages using regex fast-path.
3) If regex parsing fails or is too dense, use Groq LLM to return strict JSON.
4) Validate + resolve printed-page to PDF-page offsets deterministically.
5) Compute exact chapter ranges (start..end) and return.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import fitz  # PyMuPDF

from app.config import settings
from app.services.groq_client import groq_chat_text


_INDEX_KEYWORDS = ["table of contents", "contents", "index"]


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


def extract_index_text(pdf_path: str, max_pages: int = 10) -> Tuple[List[int], str]:
    """Detect index page(s) from the first `max_pages` pages and return their text.

    Returns (page_numbers_1_based, combined_text).
    """

    doc = fitz.open(pdf_path)
    try:
        limit = min(int(max_pages), int(doc.page_count))
        if limit <= 0:
            raise IndexNotFoundError("PDF has no pages")

        page_texts: List[Tuple[int, str]] = []
        for i in range(limit):
            page = doc.load_page(i)
            txt = (page.get_text("text") or "").strip()
            page_texts.append((i + 1, txt))

        scores: List[Tuple[int, int, int]] = []  # (score, page_no, line_hits)
        for page_no, txt in page_texts:
            nt = _normalize(txt).lower()
            keyword_hits = sum(1 for k in _INDEX_KEYWORDS if k in nt)
            line_hits = _count_index_like_lines(txt)
            score = keyword_hits * 10 + min(line_hits, 50)
            scores.append((score, page_no, line_hits))

        best = sorted(scores, key=lambda x: (-x[0], x[1]))[0]
        best_score, best_page, best_line_hits = best
        if best_score <= 0 or best_line_hits < 4:
            raise IndexNotFoundError("Could not detect an index/table of contents page in the first pages")

        # Include subsequent pages if they still look like index pages (multi-page ToC).
        selected_pages = [best_page]
        for page_no, txt in page_texts:
            if page_no <= best_page:
                continue
            if len(selected_pages) >= 4:
                break
            if _count_index_like_lines(txt) >= 4:
                selected_pages.append(page_no)
            else:
                break

        combined = "\n\n".join([t for p, t in page_texts if p in set(selected_pages)]).strip()
        if not combined:
            raise IndexNotFoundError("Index pages detected but extracted text was empty")
        return selected_pages, combined
    finally:
        doc.close()


async def parse_index_chapters(
    index_text: str,
    pdf_page_count: int,
    pdf_path: str,
    index_pages: Sequence[int] | None = None,
) -> Tuple[List[ParsedIndexChapter], int]:
    """Parse index text into chapter list.

    Returns (chapters, page_offset) where page_offset maps printed page numbers
    to PDF page numbers: pdf_page = printed_page + page_offset.
    """

    fast = _parse_index_regex(index_text)
    chapters: List[ParsedIndexChapter]
    if _is_reasonable_chapter_list(fast):
        chapters = fast
    else:
        chapters = await await_groq_parse(index_text=index_text)

    if not chapters:
        raise IndexParseError("No chapters found in index")

    # Resolve printed->PDF page offset.
    page_offset = resolve_page_offset(
        chapters,
        pdf_path=pdf_path,
        pdf_page_count=pdf_page_count,
        skip_pages=set(index_pages or []),
    )

    adjusted = [c.start_page_printed + page_offset for c in chapters]
    if not _is_strictly_ascending(adjusted):
        raise IndexParseError("Parsed chapters have non-ascending start pages after offset resolution")
    if any(p < 1 or p > pdf_page_count for p in adjusted):
        raise IndexParseError("Parsed chapters have out-of-range start pages after offset resolution")

    return chapters, page_offset


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


def resolve_page_offset(
    chapters: Sequence[ParsedIndexChapter],
    pdf_path: str,
    pdf_page_count: int,
    skip_pages: set[int] | None = None,
) -> int:
    """Resolve printed-page to PDF-page offset deterministically.

    Strategy:
    1) Prefer offset 0 if valid.
    2) Try to align first chapter title by searching for the title text in PDF.
    3) Fall back to a bounded offset sweep [-50, 50] selecting the smallest
       absolute offset that makes all start pages valid & ascending.
    """

    starts_printed = [c.start_page_printed for c in chapters]

    def is_valid_offset(off: int) -> bool:
        starts = [p + off for p in starts_printed]
        return _is_strictly_ascending(starts) and all(1 <= p <= pdf_page_count for p in starts)

    skip_pages = skip_pages or set()

    # Title-based alignment (deterministic). Prefer it when it yields a valid offset,
    # even if offset=0 is in-range (covers cover/preface offset cases).
    try:
        first = chapters[0]
        hit_page = _find_title_page(
            pdf_path,
            title=first.chapter_title,
            max_pages=min(120, pdf_page_count),
            skip_pages=skip_pages,
        )
        if hit_page is not None:
            off = int(hit_page) - int(first.start_page_printed)
            if is_valid_offset(off):
                return off
    except Exception:
        # Ignore and continue to sweep.
        pass

    if is_valid_offset(0):
        return 0

    candidates: List[int] = []
    for off in range(-50, 51):
        if is_valid_offset(off):
            candidates.append(off)

    if not candidates:
        raise IndexParseError("Could not resolve printed-page to PDF-page offset")

    candidates.sort(key=lambda x: (abs(x), x))
    return candidates[0]


def _find_title_page(pdf_path: str, title: str, max_pages: int, skip_pages: set[int]) -> Optional[int]:
    needle = _normalize(title).lower()
    if len(needle) < 6:
        return None

    doc = fitz.open(pdf_path)
    try:
        limit = min(int(max_pages), int(doc.page_count))
        for i in range(limit):
            page_no = i + 1
            if page_no in skip_pages:
                continue
            txt = doc.load_page(i).get_text("text") or ""
            hay = _normalize(txt).lower()
            if needle in hay:
                return page_no
        return None
    finally:
        doc.close()


def _parse_index_regex(index_text: str) -> List[ParsedIndexChapter]:
    lines = [_normalize(ln) for ln in (index_text or "").splitlines()]
    lines = [ln for ln in lines if ln]
    merged: List[str] = []
    buf: str = ""
    for ln in lines:
        if _ends_with_page_number(ln):
            if buf:
                merged.append(_normalize(buf + " " + ln))
                buf = ""
            else:
                merged.append(ln)
        else:
            buf = _normalize((buf + " " + ln).strip()) if buf else ln

    # Extract entries.
    entries: List[ParsedIndexChapter] = []
    for ln in merged:
        title_part, page_part = _split_title_page(ln)
        if title_part is None or page_part is None:
            continue
        page_num = _parse_page_number(page_part)
        if page_num is None:
            continue

        chapter_number, title = _extract_chapter_number_and_title(title_part)
        if chapter_number is None:
            continue
        title = title.strip()
        if not title:
            continue
        entries.append(
            ParsedIndexChapter(
                chapter_number=int(chapter_number),
                chapter_title=title[:300],
                start_page_printed=int(page_num),
            )
        )
    # De-dupe by chapter_number keeping first occurrence.
    dedup: Dict[int, ParsedIndexChapter] = {}
    for e in entries:
        dedup.setdefault(int(e.chapter_number), e)
    out = list(dedup.values())
    out.sort(key=lambda x: x.chapter_number)
    return out


async def await_groq_parse(index_text: str) -> List[ParsedIndexChapter]:
    if not (settings.groq_api_key or "").strip():
        raise IndexParseError(
            "Index parsing is complex and GROQ_API_KEY is not configured. "
            "Provide GROQ_API_KEY in backend/.env and restart the backend. "
            "If you run uvicorn from the repo root, ensure the backend package is on PYTHONPATH, "
            "or run from the backend folder (e.g. `python -m uvicorn main:app --reload`)."
        )

    schema = (
        "Return ONLY valid JSON. No markdown, no comments. "
        "Return an array of objects with keys: chapter_number (int), chapter_title (string), start_page (int)."
    )
    system = (
        "You are a strict JSON-only parser for textbook table-of-contents text. "
        "Extract ONLY top-level chapters/units/lessons (not sub-sections). "
        "chapter_number must start at 1 and be integers. "
        "start_page must be a positive integer representing the printed page number."
    )

    messages = [
        {"role": "system", "content": system + " " + schema},
        {"role": "user", "content": index_text},
    ]

    # Groq model IDs can be deprecated; try a small fallback set deterministically.
    model_candidates = [
        (settings.groq_model_index_parser or "").strip(),
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
    ]
    model_candidates = [m for m in model_candidates if m]

    last_err: Exception | None = None
    raw: str | None = None
    for model in model_candidates:
        try:
            res = await groq_chat_text(model=model, messages=messages, temperature=0.0)
            raw = res.text.strip()
            if raw:
                break
        except Exception as e:
            last_err = e
            msg = str(e)
            # If a model is decommissioned, try the next candidate.
            if "model_decommissioned" in msg or "decommissioned" in msg:
                continue
            # Other errors (auth/quota/network) should surface immediately.
            raise

    if not raw:
        detail = f" Tried models: {', '.join(model_candidates)}."
        if last_err is not None:
            raise IndexParseError(f"Groq index parsing failed.{detail} Last error: {last_err}")
        raise IndexParseError(f"Groq index parsing failed.{detail}")

    # Hard validation: JSON only.
    try:
        data = json.loads(raw)
    except Exception as e:
        raise IndexParseError("Groq did not return valid JSON") from e

    if not isinstance(data, list):
        raise IndexParseError("Groq JSON must be a list")

    out: List[ParsedIndexChapter] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        try:
            cn = int(item.get("chapter_number"))
            title = str(item.get("chapter_title") or "").strip()
            sp = int(item.get("start_page"))
        except Exception:
            continue
        if cn < 1 or sp < 1 or not title:
            continue
        out.append(ParsedIndexChapter(chapter_number=cn, chapter_title=title[:300], start_page_printed=sp))

    out.sort(key=lambda x: x.chapter_number)
    return out


def _is_reasonable_chapter_list(chapters: List[ParsedIndexChapter]) -> bool:
    if len(chapters) < 2:
        return False
    if len(chapters) > 60:
        return False
    nums = [c.chapter_number for c in chapters]
    if nums[0] != 1:
        return False
    # Require monotonic increasing chapter numbers.
    if not _is_strictly_ascending(nums):
        return False
    # Require monotonic increasing printed pages.
    if not _is_strictly_ascending([c.start_page_printed for c in chapters]):
        return False
    return True


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
