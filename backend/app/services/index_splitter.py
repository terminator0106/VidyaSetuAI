"""Index-aware PDF chapter splitter.

This module implements chapter splitting based ONLY on the PDF's Index/Table of
Contents pages.

Requirements (strict):
- Detect the index page within the first N pages by keyword match.
- Parse chapter titles and page numbers using regex (no heading/outline guessing).
- Compute chapter page ranges: end = next_start - 1, last = total pages.
- Pages before the first chapter are implicitly ignored.

Note:
- Primary path is regex parsing.
- LLM is used only as a fallback for complex/multilingual ToC formatting.
- If present, the PDF outline/bookmarks may also be used as a last-resort fallback.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
import json
import logging
from typing import Any, List, Optional, Sequence, Tuple

import fitz  # PyMuPDF

from app.config import settings
from app.services.langpacks import all_index_keywords, all_toc_markers
from app.services.llm_client import chat_text
from app.services.pdf_extraction import DEFAULT_OCR_LANGS, extract_page_text, ocr_page_region_text
from app.services.index_parsers.hindi_table import parse_hindi_toc_table_pages

logger = logging.getLogger(__name__)


def _normalize_parsed_chapters(entries: Sequence[ParsedIndexChapter]) -> List[ParsedIndexChapter]:
    """Normalize parsed ToC entries.

    Some textbooks restart numbering per unit (e.g., "पहली इकाई" and "दूसरी इकाई")
    while page numbers keep increasing. We therefore order and dedupe by
    start_page_printed, then renumber chapters sequentially.
    """

    cleaned: list[ParsedIndexChapter] = []

    # Sort by start page to match reading order.
    ordered = sorted(
        [e for e in entries if int(getattr(e, "start_page_printed", 0)) > 0],
        key=lambda x: (int(x.start_page_printed), str(x.chapter_title).lower()),
    )

    seen_pages: set[int] = set()
    last = 0
    for e in ordered:
        sp = int(e.start_page_printed)
        if sp in seen_pages:
            continue
        # Enforce strictly increasing to avoid sub-entries and OCR glitches.
        if cleaned and sp <= last:
            continue
        seen_pages.add(sp)
        cleaned.append(e)
        last = sp

    out: List[ParsedIndexChapter] = []
    for i, e in enumerate(cleaned, start=1):
        out.append(
            ParsedIndexChapter(
                chapter_number=int(i),
                chapter_title=str(e.chapter_title)[:300],
                start_page_printed=int(e.start_page_printed),
            )
        )
    return out


_DIGIT_TRANSLATION = str.maketrans(
    {
        # Devanagari ०-९
        "०": "0",
        "१": "1",
        "२": "2",
        "३": "3",
        "४": "4",
        "५": "5",
        "६": "6",
        "७": "7",
        "८": "8",
        "९": "9",
        # Gujarati ૦-૯
        "૦": "0",
        "૧": "1",
        "૨": "2",
        "૩": "3",
        "૪": "4",
        "૫": "5",
        "૬": "6",
        "૭": "7",
        "૮": "8",
        "૯": "9",
    }
)


def _ascii_digits(s: str) -> str:
    """Normalize common Indic digits to ASCII digits for int() parsing."""

    return (s or "").translate(_DIGIT_TRANSLATION)


def _index_debug_enabled() -> bool:
    try:
        return bool(getattr(settings, "index_debug", False))
    except Exception:
        return False


def _snippet(text: str, n: int = 220) -> str:
    t = (text or "").replace("\n", " ").strip()
    if len(t) <= n:
        return t
    return t[:n] + "…"


_INDEX_KEYWORDS = all_index_keywords()

_TOC_MARKERS = all_toc_markers()
_TOC_MARKERS_PAT = "|".join(re.escape(x) for x in _TOC_MARKERS)

# Example pattern:
#   Chapter 1 .......... 3
# Captures:
#   group(1) = chapter title text (including "Chapter 1" prefix)
#   group(2) = start page number
_CHAPTER_LINE_RE = re.compile(
    rf"((?:{_TOC_MARKERS_PAT})\s*\d+.*?)\s+(\d+(?:\s*[-–—]\s*\d+)?)\s*$",
    re.IGNORECASE,
)
_CHAPTER_NUM_RE = re.compile(rf"(?:{_TOC_MARKERS_PAT})\s*(\d+)", re.IGNORECASE)

# Some OCR outputs drop dot-leaders and collapse whitespace, yielding lines like
# "Chapter 1 1". Treat those as ToC-like if they match chapter markers.
_TOC_ENTRY_HINT_RE = re.compile(rf"\b(?:{_TOC_MARKERS_PAT})\s*\d+\b", re.IGNORECASE)


_BLOB_ENTRY_START_RE = re.compile(r"(?<!\d)(\d{1,3})\s*[\.|\)]\s+")
_PAGE_RANGE_RE = re.compile(r"(?<!\d)(\d{1,4})(?:\s*[-–—]\s*(\d{1,4}))?(?!\d)")


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


def _outline_chapters_from_pdf(pdf_path: str) -> List[ParsedIndexChapter]:
    """Fallback: extract chapters from PDF outline/bookmarks.

    This helps when OCR/regex cannot parse ToC text but the PDF contains a
    structured outline.

    Returns chapters with start_page_printed set to the PDF page number (1-based).
    In that case, offset should be treated as 0.
    """

    try:
        doc = fitz.open(pdf_path)
    except Exception:
        return []

    try:
        toc = doc.get_toc(simple=True) or []
        if not toc:
            return []

        # Prefer top-level entries.
        top = [(lvl, title, page) for (lvl, title, page) in toc if int(lvl) == 1]
        if not top:
            top = toc

        out: List[ParsedIndexChapter] = []
        last_page = 0
        chap_no = 1
        for _lvl, title, page in top:
            try:
                p = int(page)
            except Exception:
                continue
            if p <= 0 or p > int(doc.page_count):
                continue
            # Keep ascending pages; drop repeats.
            if p <= last_page:
                continue
            t = _normalize(str(title or "")).strip()
            if not t:
                continue
            # Require a non-trivial title.
            title_alpha = sum(
                1
                for ch in t
                if ch.isalpha() or ("\u0900" <= ch <= "\u097F") or ("\u0A80" <= ch <= "\u0AFF")
            )
            if title_alpha < 3:
                continue
            out.append(
                ParsedIndexChapter(
                    chapter_number=int(chap_no),
                    chapter_title=t[:300],
                    start_page_printed=int(p),
                )
            )
            chap_no += 1
            last_page = p

        return out
    finally:
        try:
            doc.close()
        except Exception:
            pass


async def _parse_index_llm(index_text: str) -> List[ParsedIndexChapter]:
    """Parse index text via Groq (OpenAI-compatible) as a fallback.

    Expected output: strict JSON array of objects:
    [{"chapter_number": 1, "chapter_title": "...", "start_page": 3}, ...]
    """

    cleaned = (index_text or "").strip()
    if not cleaned:
        return []

    # Normalize Indic digits to ASCII for more reliable numeric extraction.
    cleaned_for_llm = _ascii_digits(cleaned)

    messages = [
        {
            "role": "system",
            "content": (
                "You extract chapter structure from a textbook Table of Contents that may be in English, Hindi, Marathi, or Gujarati. "
                "Return ONLY valid JSON (no markdown). Output an array of objects with keys: "
                "chapter_number (int), chapter_title (string), start_page (int). "
                "start_page must be the printed start page number shown in the index. "
                "Do not invent chapters."
            ),
        },
        {"role": "user", "content": cleaned_for_llm[:45000]},
    ]

    if getattr(settings, "llm_provider", "groq") == "groq":
        model = getattr(settings, "groq_model_index_parser", None) or getattr(settings, "model_large", "llama-3.3-70b-versatile")
    else:
        # Use the normal large model for the configured provider (e.g., gpt-4o).
        model = getattr(settings, "model_large", "gpt-4o")
    try:
        res = await chat_text(
            model=str(model),
            messages=messages,
            temperature=0.0,
            max_tokens=2000,
        )
    except Exception as e:
        payload = {"err": str(e), "model": str(model)}
        if _index_debug_enabled():
            payload["index_snippet"] = _snippet(cleaned)
        logger.warning("Index LLM parsing failed", extra={"extra": payload})
        return []

    raw = (res.text or "").strip()
    if not raw:
        return []

    # Best-effort: strip accidental leading/trailing text.
    start = raw.find("[")
    end = raw.rfind("]")
    if start >= 0 and end >= 0 and end > start:
        raw_json = raw[start : end + 1]
    else:
        raw_json = raw

    try:
        data = json.loads(raw_json)
    except Exception as e:
        logger.warning("Index LLM output was not valid JSON", extra={"extra": {"err": str(e), "raw": raw[:500]}})
        return []

    if not isinstance(data, list):
        return []

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
        if cn <= 0 or sp <= 0:
            continue
        if not title:
            title = f"Chapter {cn}"
        out.append(ParsedIndexChapter(chapter_number=cn, chapter_title=title[:300], start_page_printed=sp))

    if not out:
        return []

    return _normalize_parsed_chapters(out)


def extract_index_text(pdf_path: str, max_pages: int = 10) -> Tuple[List[int], str]:
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

        # Score candidate ToC pages.
        # OCR often collapses dot-leaders/spacing, so we primarily look for:
        # - presence of index keywords (strong signal)
        # - lines that end in a (possibly Indic) page number and look chapter-like
        min_hits_no_keyword = 2

        best: tuple[int, int, int, int, str, bool] | None = None  # (idx0, score, hits, has_kw, text, used_ocr)
        scored: list[tuple[int, int, int, int, bool, int, str]] = []  # (idx0, score, hits, has_kw, used_ocr, len, snippet)

        for i in range(limit):
            page = doc.load_page(i)
            # OCR fallback helps with scanned ToC pages.
            extracted = extract_page_text(page, min_chars=60, ocr_langs=DEFAULT_OCR_LANGS)
            txt = (extracted.text or "").strip()
            if not txt:
                continue

            nt = _normalize(txt).lower()
            hits = _count_index_like_lines(txt)

            has_kw = 1 if any(k in nt for k in _INDEX_KEYWORDS) else 0
            # Keyword presence is a strong signal.
            score = hits + (10 * has_kw)

            scored.append((i, score, hits, has_kw, bool(extracted.used_ocr), len(txt), _snippet(txt)))

            # Candidate acceptance:
            # - any keyword page (even if OCR mangled dot leaders)
            # - or a page with at least a couple ToC-like entries
            is_candidate = bool(has_kw) or (hits >= min_hits_no_keyword)
            if is_candidate:
                if best is None or score > best[1]:
                    best = (i, score, hits, has_kw, txt, bool(extracted.used_ocr))

            if _index_debug_enabled():
                logger.info(
                    "Index scan",
                    extra={
                        "extra": {
                            "page": i + 1,
                            "used_ocr": bool(extracted.used_ocr),
                            "len": len(txt),
                            "hits": hits,
                            "has_kw": has_kw,
                            "score": score,
                            "snippet": _snippet(txt),
                        }
                    },
                )

        if best is None:
            msg = f"Could not detect an index/table of contents page in the first {limit} pages"
            if scored:
                top = sorted(scored, key=lambda x: x[1], reverse=True)[:5]
                top_msg = "; ".join([f"p{t[0]+1}:score={t[1]},hits={t[2]},kw={t[3]},ocr={int(t[4])},len={t[5]}" for t in top])
                msg += f" (top candidates: {top_msg})"
            msg += ". If this is a scanned Hindi/Marathi/Gujarati PDF, set INDEX_DEBUG=true in backend/.env and retry to log OCR text samples."
            raise IndexNotFoundError(msg)

        i, _score, _hits, _has_kw, txt, _used_ocr = best

        # Best-effort: index/contents often spans multiple pages.
        pages_1b: List[int] = [i + 1]
        combined: List[str] = [txt.strip()]
        for j in range(i + 1, min(limit, i + 5)):
            nxt_page = doc.load_page(j)
            nxt = (extract_page_text(nxt_page, min_chars=60, ocr_langs=DEFAULT_OCR_LANGS).text or "").strip()
            if not nxt:
                break
            if _count_index_like_lines(nxt) < 1:
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

    if _index_debug_enabled():
        logger.info(
            "Index text received",
            extra={
                "extra": {
                    "len": len(index_text or ""),
                    "snippet": _snippet(index_text or "", 1200),
                }
            },
        )

    chapters = _parse_index_regex(index_text)

    # Hindi ToC often comes as a colored table; plain OCR text can be incomplete.
    # If we got too few chapters and the index looks Hindi, try a table-specific parser.
    try:
        looks_hindi = any(x in (index_text or "") for x in ["अनुक्रमणिका", "इकाई", "पाठ"])
    except Exception:
        looks_hindi = False
    if looks_hindi and (not chapters or len(chapters) < 4) and index_pages:
        try:
            # Fallback A: parse ToC entries directly from the extracted text blob.
            # This handles the common OCR failure mode where the entire table
            # is returned as a single wrapped line, so line-based regex misses
            # every entry except the last one.
            blob_chapters = _parse_index_numbered_entries_blob(index_text)
            if blob_chapters and len(blob_chapters) > (len(chapters) if chapters else 0):
                chapters = _normalize_parsed_chapters(blob_chapters)

            # Fallback B: table-specific OCR parser.
            rows = parse_hindi_toc_table_pages(
                pdf_path=str(pdf_path),
                index_pages_1b=list(index_pages),
                ocr_langs=DEFAULT_OCR_LANGS,
            )
            if rows and len(rows) > (len(chapters) if chapters else 0):
                chapters = [
                    ParsedIndexChapter(
                        chapter_number=i + 1,
                        chapter_title=title,
                        start_page_printed=sp,
                    )
                    for i, (title, sp) in enumerate(rows)
                ]
                chapters = _normalize_parsed_chapters(chapters)
        except Exception as e:
            if _index_debug_enabled():
                logger.warning("Hindi table ToC parsing failed", extra={"extra": {"err": str(e)}})
    used_outline_fallback = False
    if not chapters:
        # LLM fallback for complex/multilingual index formatting.
        chapters = await _parse_index_llm(index_text)
    if not chapters:
        # Outline/bookmarks fallback (PDF may have structure even if OCR ToC is messy).
        chapters = _outline_chapters_from_pdf(pdf_path)
        used_outline_fallback = bool(chapters)
    if not chapters:
        provider = getattr(settings, "llm_provider", "groq")
        has_groq = bool(getattr(settings, "groq_api_key", None))
        has_openai = bool(getattr(settings, "openai_api_key", None))
        hint = ""
        if provider == "groq" and not has_groq:
            hint = " GROQ_API_KEY is missing (LLM fallback cannot run)."
        if provider == "openai" and not has_openai:
            hint = " OPENAI_API_KEY is missing (LLM fallback cannot run)."
        hint += " Set INDEX_DEBUG=true in backend/.env and retry to log OCR/index text snippets."
        raise IndexParseError("No chapters found in index (regex + LLM + outline fallback failed)." + hint)

    if used_outline_fallback:
        # Outline pages are already PDF page numbers (1-based).
        offset = 0
    else:
        # IMPORTANT: start_page_printed comes from the textbook's printed page
        # numbers in the ToC, which often do NOT match the PDF page index.
        # We estimate an offset by reading header/footer page numbers from the PDF.
        offset = _estimate_pdf_page_offset(
            pdf_path=pdf_path,
            pdf_page_count=int(pdf_page_count),
            chapter_start_pages_printed=[c.start_page_printed for c in chapters],
            index_pages=index_pages,
        )

    if _index_debug_enabled():
        try:
            logger.info(
                "Index offset estimated",
                extra={
                    "extra": {
                        "offset": int(offset),
                        "used_outline_fallback": bool(used_outline_fallback),
                        "starts_printed_first": [int(c.start_page_printed) for c in chapters[:10]],
                        "starts_pdf_first": [int(c.start_page_printed) + int(offset) for c in chapters[:10]],
                    }
                },
            )
        except Exception:
            pass

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


def _parse_index_numbered_entries_blob(index_text: str) -> List[ParsedIndexChapter]:
    """Parse Hindi/Indic ToC when entries are collapsed into a single text blob.

    Many scanned/table ToCs are extracted as one long line, which defeats
    line-based parsing. This routine scans for numbered entries like:
        "1. Title ... 1-2 2. Next ... 3-9 ..."

    Returns ParsedIndexChapter entries in encounter order.
    """

    raw = (index_text or "").strip()
    if not raw:
        return []

    # Normalize digits early so we can match 1., 2., etc.
    text = _ascii_digits(_normalize(raw))
    if not text:
        return []

    starts = list(_BLOB_ENTRY_START_RE.finditer(text))
    if len(starts) < 2:
        return []

    out: List[ParsedIndexChapter] = []
    prev_page: Optional[int] = None

    for idx, m in enumerate(starts):
        try:
            serial = int(m.group(1))
        except Exception:
            serial = idx + 1

        entry_start = m.end()
        entry_end = starts[idx + 1].start() if idx + 1 < len(starts) else len(text)
        chunk = text[entry_start:entry_end].strip()
        if not chunk:
            continue

        # Extract all numeric candidates; ToC rows often contain both the
        # row number and the page range.
        matches = list(_PAGE_RANGE_RE.finditer(chunk))
        if not matches:
            continue

        # Choose a start page candidate that is monotonic w.r.t. previous.
        page_candidates: List[int] = []
        for pm in matches:
            try:
                page_candidates.append(int(pm.group(1)))
            except Exception:
                continue
        if not page_candidates:
            continue

        page_start = page_candidates[-1]
        if prev_page is not None:
            for cand in reversed(page_candidates):
                if cand >= int(prev_page):
                    page_start = int(cand)
                    break

        prev_page = int(page_start)

        # Title: remove trailing page tokens best-effort.
        last_match = None
        for pm in reversed(matches):
            try:
                if int(pm.group(1)) == int(page_start):
                    last_match = pm
                    break
            except Exception:
                continue
        if last_match is None:
            last_match = matches[-1]

        title_part = chunk[: last_match.start()].strip(" -:\t")
        title_part = _normalize(title_part)

        title_alpha = sum(
            1
            for ch in title_part
            if ch.isalpha() or ("\u0900" <= ch <= "\u097F") or ("\u0A80" <= ch <= "\u0AFF")
        )
        if title_alpha < 3:
            continue

        out.append(
            ParsedIndexChapter(
                chapter_number=int(serial) if serial > 0 else int(len(out) + 1),
                chapter_title=title_part[:300] or f"Chapter {len(out) + 1}",
                start_page_printed=int(page_start),
            )
        )

    return out


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
            page_token = _ascii_digits(raw_page)
            page_token = re.split(r"\s*[-–—]\s*", page_token, maxsplit=1)[0].strip()
            start_page = int(page_token)
        except Exception:
            continue

        num_match = _CHAPTER_NUM_RE.search(raw_title)
        if not num_match:
            continue
        try:
            chapter_number = int(_ascii_digits(num_match.group(1)))
        except Exception:
            continue

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

    return _normalize_parsed_chapters(entries)


def _parse_index_flexible(lines: Sequence[str]) -> List[ParsedIndexChapter]:
    raw_entries: List[Tuple[Optional[int], str, int]] = []

    for ln in lines:
        if not ln:
            continue

        # Only consider lines that resemble ToC entries, otherwise we may
        # misinterpret syllabus codes like "08.72.10" as page numbers.
        if not _ends_with_page_number(ln):
            continue

        has_layout_signal = ("." in ln or "\t" in ln or "  " in ln)
        has_chapter_hint = bool(_TOC_ENTRY_HINT_RE.search(ln))

        title_part, page_part = _split_title_page(ln)
        if not title_part or not page_part:
            continue

        # If we don't have classic ToC formatting, require a non-trivial title
        # to avoid capturing stray page footers like "10".
        if not (has_layout_signal or has_chapter_hint):
            title_alpha = sum(
                1
                for ch in title_part
                if ch.isalpha() or ("\u0900" <= ch <= "\u097F") or ("\u0A80" <= ch <= "\u0AFF")
            )
            if title_alpha < 3:
                continue

        page_num = _parse_page_number(page_part)
        if page_num is None:
            continue

        chapter_num, title = _extract_chapter_number_and_title(title_part)
        clean_title = (title or "").strip() or title_part
        raw_entries.append((chapter_num, str(clean_title)[:300], int(page_num)))

    if not raw_entries:
        return []

    # Guardrail: ToC page numbers should be mostly non-decreasing.
    pages = [p for _, _, p in raw_entries]
    nondec = sum(1 for i in range(len(pages) - 1) if pages[i] <= pages[i + 1])
    if len(pages) >= 4 and nondec < (len(pages) - 1) // 2:
        return []

    used_numbers = {int(n) for n, _, _ in raw_entries if n is not None}
    next_number = 1
    entries: List[ParsedIndexChapter] = []
    for n, title_txt, page_num in raw_entries:
        if n is None:
            while next_number in used_numbers:
                next_number += 1
            n = next_number
            used_numbers.add(int(n))
            next_number += 1
        entries.append(
            ParsedIndexChapter(
                chapter_number=int(n),
                chapter_title=str(title_txt)[:300],
                start_page_printed=int(page_num),
            )
        )

    # Sort by page number; do not dedupe by chapter_number (units may restart numbering).
    entries.sort(key=lambda x: int(x.start_page_printed))
    seen_pages: set[int] = set()
    out: List[ParsedIndexChapter] = []
    for e in entries:
        sp = int(e.start_page_printed)
        if sp in seen_pages:
            continue
        seen_pages.add(sp)
        out.append(e)
    return out


def _count_index_like_lines(text: str) -> int:
    lines = [_normalize(ln) for ln in (text or "").splitlines()]
    hits = 0
    for ln in lines:
        if not ln:
            continue
        if not _ends_with_page_number(ln):
            continue

        # Strong signal: dot-leaders/tabs (typical for ToC layout).
        if "." in ln or "\t" in ln or "  " in ln:
            hits += 1
            continue

        # OCR-friendly signal: chapter-like lines ending in a page number.
        if _TOC_ENTRY_HINT_RE.search(ln):
            hits += 1
            continue

        # Generic ToC entry: title + terminal page number (no dot leaders).
        title_part, page_part = _split_title_page(ln)
        if title_part and page_part:
            title_alpha = sum(
                1
                for ch in title_part
                if ch.isalpha() or ("\u0900" <= ch <= "\u097F") or ("\u0A80" <= ch <= "\u0AFF")
            )
            if title_alpha >= 3:
                hits += 1
    return hits


def _ends_with_page_number(line: str) -> bool:
    # Use \d to support Indic digits; we normalize to ASCII later for int().
    return bool(
        re.search(
            r"(?:\s|\.|[-–—])+(\d{1,4}(?:\s*[-–—]\s*\d{1,4})?|[ivxlcdmIVXLCDM]{1,8})\s*$",
            line,
        )
    )


def _extract_printed_page_number_from_page(page: fitz.Page, *, use_ocr: bool = False) -> Optional[int]:
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
            if not use_ocr:
                return None

            # OCR fallback for scanned PDFs: read the header/footer bands.
            header_rect = fitz.Rect(0, 0, w, h * 0.15)
            footer_rect = fitz.Rect(0, h * 0.85, w, h)
            cfg = "--oem 1 --psm 7 -c tessedit_char_whitelist=0123456789०१२३४५६७८९૦૧૨૩૪૫૬૭૮૯-–—"
            header_ocr = ocr_page_region_text(page, clip=header_rect, ocr_langs=DEFAULT_OCR_LANGS, dpi=300, config=cfg)
            footer_ocr = ocr_page_region_text(page, clip=footer_rect, ocr_langs=DEFAULT_OCR_LANGS, dpi=300, config=cfg)
            blob = "\n".join([header_ocr or "", footer_ocr or ""]).strip()
            if not blob:
                return None

        # Prefer lines that are only a number.
        for ln in [x.strip() for x in blob.splitlines() if x.strip()]:
            ln_ascii = _ascii_digits(ln)
            if re.fullmatch(r"\d{1,4}", ln_ascii):
                return int(ln_ascii)

        # Fallback: find isolated numeric tokens, but avoid syllabus-like codes
        # such as 08.72.10 by requiring token boundaries.
        blob_ascii = _ascii_digits(blob)
        matches = list(re.finditer(r"(?<![0-9\.])(\d{1,4})(?![0-9\.])", blob_ascii))
        if matches:
            # Prefer the last token (footer numbers are often last).
            return int(matches[-1].group(1))
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
        # Pass 1: fast text-based extraction.
        for pdf_page in range(1, limit + 1):
            page = doc.load_page(pdf_page - 1)
            pnum = _extract_printed_page_number_from_page(page, use_ocr=False)
            if pnum is None:
                continue
            if pnum < max(1, min_p - 10) or pnum > (max_p + 10):
                continue
            diffs.append(int(pdf_page) - int(pnum))

        # Pass 2: OCR-based extraction for scanned PDFs (bounded sampling).
        # Avoid OCR'ing dozens of pages unless needed.
        if not diffs:
            max_ocr_pages = min(int(limit), 90)
            step = 3
            for pdf_page in range(1, max_ocr_pages + 1, step):
                page = doc.load_page(pdf_page - 1)
                pnum = _extract_printed_page_number_from_page(page, use_ocr=True)
                if pnum is None:
                    continue
                if pnum < max(1, min_p - 10) or pnum > (max_p + 10):
                    continue
                diffs.append(int(pdf_page) - int(pnum))
                if len(diffs) >= 10:
                    break
    finally:
        doc.close()

    # If we couldn't detect any printed numbers, fall back.
    off = _mode_int(diffs)
    return int(off) if off is not None else 0


def _split_title_page(line: str) -> Tuple[Optional[str], Optional[str]]:
    # Remove dot leaders
    cleaned = re.sub(r"\.{2,}", " ", line).strip()
    m = re.search(r"(\d{1,4}(?:\s*[-–—]\s*\d{1,4})?|[ivxlcdmIVXLCDM]{1,8})\s*$", cleaned)
    if not m:
        return None, None
    page_part = _ascii_digits(m.group(1))
    title_part = cleaned[: m.start(1)].strip(" -:\t")
    if not title_part:
        return None, None
    return title_part, page_part


def _extract_chapter_number_and_title(title_part: str) -> Tuple[Optional[int], str]:
    t = title_part.strip()

    m = re.match(
        rf"^({_TOC_MARKERS_PAT})\s+([\divxlcdmIVXLCDM]+)\b\s*[:\-\.]?\s*(.*)$",
        t,
        re.IGNORECASE,
    )
    if m:
        cn = _parse_chapter_number(m.group(2))
        rest = (m.group(3) or "").strip()
        return cn, rest if rest else t

    m = re.match(r"^(\d{1,3})\s*[\.|\-|\)|:]\s*(.*)$", t)
    if m:
        cn = int(_ascii_digits(m.group(1)))
        rest = (m.group(2) or "").strip()
        return cn, rest if rest else t

    m = re.match(r"^(\d{1,3})\s+(.*)$", t)
    if m:
        cn = int(_ascii_digits(m.group(1)))
        rest = (m.group(2) or "").strip()
        return cn, rest if rest else t

    # Not a chapter-like entry.
    return None, t


def _parse_chapter_number(raw: str) -> Optional[int]:
    raw = _ascii_digits((raw or "").strip())
    if not raw:
        return None
    if raw.isdigit():
        return int(raw)
    v = _roman_to_int(raw)
    return v


def _parse_page_number(raw: str) -> Optional[int]:
    raw = _ascii_digits((raw or "").strip())
    if not raw:
        return None
    raw = re.split(r"\s*[-–—]\s*", raw, maxsplit=1)[0].strip()
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
