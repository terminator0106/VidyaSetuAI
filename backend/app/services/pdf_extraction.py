"""Multilingual PDF text extraction with OCR fallback.

Primary extractor: PyMuPDF (fitz) `page.get_text()`.
Fallback extractor: Tesseract OCR via `pytesseract`.

This module is designed to be used by ingestion (index detection + chunk text)
where multilingual/scanned PDFs are common.

Notes:
- OCR requires the system Tesseract binary + language packs installed.
- We keep OCR optional and fail with descriptive errors when required.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import math
import re
import unicodedata

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)

from app.services.langpacks.common import OCR_LANGS_ALL


DEFAULT_OCR_LANGS = OCR_LANGS_ALL


def _ocr_quality_score(text: str) -> float:
    """Score OCR output for usefulness.

    Prefers longer text with a higher ratio of letters/digits in expected scripts.
    """

    t = (text or "").strip()
    if not t:
        return 0.0

    total = 0
    useful = 0
    devanagari = 0
    gujarati = 0
    latin = 0
    other_alnum = 0
    punct = 0

    for ch in t:
        if ch.isspace():
            continue
        total += 1
        o = ord(ch)

        is_dev = 0x0900 <= o <= 0x097F
        is_guj = 0x0A80 <= o <= 0x0AFF
        is_latin = ch.isalnum() and o < 128

        if is_dev:
            devanagari += 1
            useful += 1
        elif is_guj:
            gujarati += 1
            useful += 1
        elif is_latin:
            latin += 1
            useful += 1
        elif ch.isalnum():
            other_alnum += 1
            # Count as "somewhat" useful but penalize later.
            useful += 1
        else:
            punct += 1

    if total <= 0:
        return 0.0

    ratio = useful / total
    score = (ratio * 100.0) + min(200.0, len(t) / 4.0)

    # Penalize outputs that look like the wrong script/noisy segmentation.
    if total:
        alnum_total = devanagari + gujarati + latin + other_alnum
        if alnum_total:
            # Determine dominant script among Devanagari/Gujarati/Latin.
            dominant = "latin"
            dominant_count = latin
            if devanagari > dominant_count:
                dominant = "devanagari"
                dominant_count = devanagari
            if gujarati > dominant_count:
                dominant = "gujarati"
                dominant_count = gujarati

            non_dominant = 0
            if dominant == "devanagari":
                non_dominant = gujarati + latin
            elif dominant == "gujarati":
                non_dominant = devanagari + latin
            else:
                non_dominant = devanagari + gujarati

            # If OCR mixes scripts heavily, it's usually worse for downstream parsing.
            non_dom_r = non_dominant / alnum_total
            score -= non_dom_r * 120.0

            # If there's no clear dominant script, treat it as noisy.
            dom_r = dominant_count / alnum_total
            if dom_r < 0.6:
                score -= (0.6 - dom_r) * 200.0

            # Penalize unknown alnum (often junk symbols).
            score -= (other_alnum / alnum_total) * 80.0

            # Penalize high mixing across script buckets.
            # Clean pages typically have one dominant bucket; garbled OCR spreads across many.
            ps: list[float] = []
            for c in (devanagari, gujarati, latin, other_alnum):
                if c:
                    ps.append(c / alnum_total)
            if len(ps) > 1:
                entropy = -sum(p * math.log(p) for p in ps)
                max_entropy = math.log(4.0)
                if max_entropy:
                    score -= (entropy / max_entropy) * 180.0

        score -= (punct / total) * 40.0

    return score


@dataclass(frozen=True)
class ExtractedPage:
    page_number: int  # 1-based
    text: str
    used_ocr: bool


def _normalize_text(text: str) -> str:
    t = unicodedata.normalize("NFKC", text or "")
    t = t.replace("\u00a0", " ")
    t = t.replace("\ufeff", "")
    # Remove control chars except newlines/tabs.
    t = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", t)
    # Collapse excessive whitespace but preserve line breaks.
    t = "\n".join([" ".join(ln.split()).strip() for ln in t.splitlines()])
    return "\n".join([ln for ln in t.splitlines() if ln]).strip()


def _looks_unreadable(text: str) -> bool:
    """Heuristic to detect garbled extraction.

    Triggers OCR when:
    - text is very short
    - high ratio of replacement characters (\ufffd) or non-word noise
    """

    t = (text or "").strip()
    # Hard minimum: OCR is cheaper than indexing garbage.
    if len(t) < 50:
        return True

    # Replacement chars are a strong signal of broken extraction.
    repl = t.count("\ufffd")
    if repl >= 3:
        return True

    # Ratio-based check for "unknown" symbols.
    non_space = [ch for ch in t if not ch.isspace()]
    if non_space:
        bad = sum(1 for ch in non_space if ch == "\ufffd" or ch == "�")
        if (bad / len(non_space)) > 0.06:
            return True

    # If almost nothing is alphanumeric or in common scripts, it's likely junk.
    # Keep Devanagari/Gujarati ranges.
    useful = 0
    total = 0
    for ch in t:
        if ch.isspace():
            continue
        total += 1
        o = ord(ch)
        if ch.isalnum() or (0x0900 <= o <= 0x097F) or (0x0A80 <= o <= 0x0AFF):
            useful += 1

    if total <= 0:
        return True

    return (useful / total) < 0.35


def _ocr_page(page: fitz.Page, *, ocr_langs: str, dpi: int, config: str) -> str:
    try:
        from app.utils.ocr_utils import (
            convert_pdf_page_to_image,
            preprocess_image_for_ocr,
            extract_text_from_image,
        )

        img = convert_pdf_page_to_image(page, dpi=int(dpi))
        img = preprocess_image_for_ocr(img)
        text = extract_text_from_image(img, lang=str(ocr_langs), config=(config or ""))
        return _normalize_text(text)
    except Exception as e:
        raise RuntimeError(
            "OCR fallback failed. Ensure system Tesseract OCR is installed with language packs: eng, hin, mar, guj. "
            "Also install Python deps: pytesseract, Pillow, opencv-python, pdf2image."
        ) from e


def ocr_page_region_text(
    page: fitz.Page,
    *,
    clip: fitz.Rect,
    ocr_langs: str = DEFAULT_OCR_LANGS,
    dpi: int = 300,
    config: str = "",
) -> str:
    """OCR a rectangular region of a page.

    Used for header/footer page-number detection on scanned PDFs.
    Returns normalized text (may be empty).
    """

    try:
        from PIL import Image  # type: ignore
        from app.utils.ocr_utils import preprocess_image_for_ocr, extract_text_from_image
    except Exception as e:
        raise RuntimeError(
            "OCR fallback requested but OCR dependencies are missing. "
            "Install pytesseract and Pillow (and system Tesseract + language packs)."
        ) from e

    attempts = [
        (int(dpi), config or ""),
        (int(dpi), (config + " --psm 7") if config and "--psm" not in config else (config or "--oem 1 --psm 7")),
        (int(dpi), "--oem 1 --psm 7"),
        (int(dpi), "--oem 1 --psm 8"),
    ]

    best = ""
    best_score = float("-inf")
    last_err: Exception | None = None

    for d, cfg in attempts:
        try:
            pix = page.get_pixmap(dpi=int(d), clip=clip)
            if pix.width <= 0 or pix.height <= 0:
                continue
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            img = preprocess_image_for_ocr(img)
            norm = extract_text_from_image(img, lang=ocr_langs, config=(cfg or ""))
            sc = _ocr_quality_score(norm)
            if sc > best_score:
                best_score = sc
                best = norm
        except Exception as e:
            last_err = e
            continue

    if best:
        return best

    if last_err:
        logger.debug(
            "Region OCR failed",
            extra={"extra": {"page": int(page.number) + 1, "err": str(last_err)}},
        )

    return ""


def extract_page_text(
    page: fitz.Page,
    *,
    min_chars: int = 50,
    ocr_langs: str = DEFAULT_OCR_LANGS,
    force_ocr: bool = False,
) -> ExtractedPage:
    """Extract text for a single page with OCR fallback."""

    page_no = int(page.number) + 1

    raw = ""
    if not force_ocr:
        try:
            raw = page.get_text("text") or ""
        except Exception:
            raw = ""

    norm = _normalize_text(raw)

    needs_ocr = force_ocr or len(norm) < min_chars or _looks_unreadable(norm)
    if not needs_ocr:
        return ExtractedPage(page_number=page_no, text=norm, used_ocr=False)

    # OCR: try a few configurations. This improves multilingual ToC extraction
    # where default OCR may return too little or noisy text.
    ocr_attempts = [
        (220, ""),
        (300, "--oem 1 --psm 6"),
        (300, "--oem 1 --psm 4"),
    ]

    best_text = ""
    best_score = float("-inf")
    last_err: Exception | None = None
    for dpi, cfg in ocr_attempts:
        try:
            candidate = _ocr_page(page, ocr_langs=ocr_langs, dpi=int(dpi), config=str(cfg))
            sc = _ocr_quality_score(candidate)
            if sc > best_score:
                best_score = sc
                best_text = candidate
        except Exception as e:
            last_err = e
            continue

    try:
        if best_text:
            return ExtractedPage(page_number=page_no, text=best_text, used_ocr=True)
    except Exception:
        pass

    # If OCR executed but produced no text (e.g., decorative cover pages), treat
    # it as best-effort and continue without failing ingestion.
    if last_err is None:
        return ExtractedPage(page_number=page_no, text=norm, used_ocr=True)

    e = last_err
    try:
        raise e
    except Exception as e:
        # If PyMuPDF text was already unreadable/empty and OCR can't run, surface a useful error.
        if not norm or _looks_unreadable(norm):
            raise RuntimeError(
                "PDF text extraction appears unreadable and OCR fallback failed. "
                "Install system Tesseract OCR + language packs (eng, hin, mar, guj) and ensure pytesseract can find it. "
                f"(page={page_no})"
            ) from e

        # Otherwise OCR is best-effort: log and fall back to whatever we had.
        logger.warning(
            "OCR extraction failed; using PyMuPDF text",
            extra={"extra": {"page": page_no, "err": str(e)}},
        )

    # If OCR failed and base text is empty/short, return it anyway; caller decides if this is fatal.
    return ExtractedPage(page_number=page_no, text=norm, used_ocr=needs_ocr)


def extract_text_by_page_range(
    pdf_path: str,
    *,
    start_page: int,
    end_page: int,
    min_chars: int = 50,
    ocr_langs: str = DEFAULT_OCR_LANGS,
) -> list[tuple[int, str]]:
    """Extract (page_number, text) for a page range (inclusive), with OCR fallback."""

    doc = fitz.open(pdf_path)
    try:
        total = int(doc.page_count)
        start = max(1, min(total, int(start_page)))
        end = max(start, min(total, int(end_page)))

        out: list[tuple[int, str]] = []
        for p in range(start, end + 1):
            page = doc.load_page(p - 1)
            ep = extract_page_text(page, min_chars=min_chars, ocr_langs=ocr_langs)
            out.append((p, ep.text))
        return out
    finally:
        doc.close()
