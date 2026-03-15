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
import re
import os
import shutil
from pathlib import Path
from typing import Optional

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
        return 0.0

    ratio = useful / total
    # Small weight on length; big weight on ratio.
    return (ratio * 100.0) + min(200.0, len(t) / 4.0)


@dataclass(frozen=True)
class ExtractedPage:
    page_number: int  # 1-based
    text: str
    used_ocr: bool


def _normalize_text(text: str) -> str:
    text = text or ""
    text = text.replace("\u00a0", " ")
    # Collapse excessive whitespace but preserve line breaks.
    text = "\n".join([" ".join(ln.split()).strip() for ln in text.splitlines()])
    return "\n".join([ln for ln in text.splitlines() if ln]).strip()


def _looks_unreadable(text: str) -> bool:
    """Heuristic to detect garbled extraction.

    Triggers OCR when:
    - text is very short
    - high ratio of replacement characters (\ufffd) or non-word noise
    """

    t = (text or "").strip()
    if len(t) < 40:
        return True

    bad = t.count("\ufffd")
    if bad >= 3:
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
        import pytesseract  # type: ignore
        from PIL import Image  # type: ignore
    except Exception as e:
        raise RuntimeError(
            "OCR fallback requested but pytesseract/Pillow are not installed. "
            "Install pytesseract and Pillow (and system Tesseract + language packs)."
        ) from e

    # Ensure pytesseract can find the Tesseract binary even when PATH changes
    # haven't propagated to the current Python process yet (common on Windows).
    cmd = _resolve_tesseract_cmd()
    if cmd:
        try:
            pytesseract.pytesseract.tesseract_cmd = cmd
        except Exception:
            pass

    pix = page.get_pixmap(dpi=int(dpi))
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

    # Light pre-processing helps OCR on scans.
    try:
        img = img.convert("L")  # grayscale
    except Exception:
        pass

    # Tesseract config: try tuned page segmentation; OCR quality is driven by dpi + PSM.
    text = pytesseract.image_to_string(img, lang=ocr_langs, config=(config or ""))
    return _normalize_text(text)


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
        import pytesseract  # type: ignore
        from PIL import Image  # type: ignore
    except Exception as e:
        raise RuntimeError(
            "OCR fallback requested but pytesseract/Pillow are not installed. "
            "Install pytesseract and Pillow (and system Tesseract + language packs)."
        ) from e

    cmd = _resolve_tesseract_cmd()
    if cmd:
        try:
            pytesseract.pytesseract.tesseract_cmd = cmd
        except Exception:
            pass

    attempts = [
        (int(dpi), config or ""),
        (int(dpi), (config + " --psm 7") if config and "--psm" not in config else (config or "--oem 1 --psm 7")),
        (int(dpi), "--oem 1 --psm 7"),
        (int(dpi), "--oem 1 --psm 8"),
    ]

    best = ""
    best_score = 0.0
    last_err: Exception | None = None

    for d, cfg in attempts:
        try:
            pix = page.get_pixmap(dpi=int(d), clip=clip)
            if pix.width <= 0 or pix.height <= 0:
                continue
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            try:
                img = img.convert("L")
            except Exception:
                pass

            txt = pytesseract.image_to_string(img, lang=ocr_langs, config=(cfg or ""))
            norm = _normalize_text(txt)
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


def _resolve_tesseract_cmd() -> Optional[str]:
    """Return a full path to tesseract.exe if it can be found.

    pytesseract discovers the binary via PATH, but in long-running processes the
    PATH may not reflect recent installs. We also support an explicit override
    env var for reliability.
    """

    override = (os.environ.get("TESSERACT_CMD") or "").strip()
    if override and Path(override).exists():
        return override

    which = shutil.which("tesseract")
    if which:
        return which

    # Common Windows install locations.
    candidates = [
        r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe",
        r"C:\\Program Files (x86)\\Tesseract-OCR\\tesseract.exe",
    ]
    for c in candidates:
        if Path(c).exists():
            return c

    return None


def extract_page_text(
    page: fitz.Page,
    *,
    min_chars: int = 40,
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
    best_score = 0.0
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

    e = last_err or RuntimeError("OCR produced no usable text")
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
    min_chars: int = 40,
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
