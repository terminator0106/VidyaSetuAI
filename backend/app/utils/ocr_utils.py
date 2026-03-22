"""OCR helpers for multilingual/scanned PDFs.

This module is intentionally optional: if OCR dependencies are missing,
callers will get a descriptive RuntimeError.

Design goals:
- Keep the existing PyMuPDF extraction path intact
- Provide clean OCR building blocks for fallback scenarios
- Support multiple Indian languages via Tesseract language packs
"""

from __future__ import annotations

import os
import re
import shutil
import unicodedata
from pathlib import Path
from typing import Any, Optional


DEFAULT_OCR_LANGS = "hin+eng+mar+guj"


def _resolve_tesseract_cmd() -> Optional[str]:
    """Return a full path to tesseract executable if it can be found."""

    override = (os.environ.get("TESSERACT_CMD") or "").strip()
    if override and Path(override).exists():
        return override

    which = shutil.which("tesseract")
    if which:
        return which

    # Common Windows install locations.
    candidates = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate

    return None


def _has_traineddata(tessdata_dir: str, *, langs: str) -> bool:
    try:
        p = Path(tessdata_dir)
        if not p.exists() or not p.is_dir():
            return False

        required = [ln.strip() for ln in (langs or "").split("+") if ln.strip()]
        if not required:
            # At least one traineddata file should exist.
            return any(p.glob("*.traineddata"))

        for code in required:
            if not (p / f"{code}.traineddata").exists():
                return False
        return True
    except Exception:
        return False


def _resolve_tessdata_dir(*, tesseract_cmd: Optional[str], langs: str) -> Optional[str]:
    """Resolve a tessdata directory containing the requested traineddata files.

    Tesseract uses TESSDATA_PREFIX in a way that often trips up Windows installs:
    if it points to the *install root* instead of the *tessdata* folder, tesseract
    searches for e.g. `eng.traineddata` in the wrong place.
    """

    candidates: list[str] = []

    env_prefix = (os.environ.get("TESSDATA_PREFIX") or "").strip()
    if env_prefix:
        candidates.append(env_prefix)
        candidates.append(str(Path(env_prefix) / "tessdata"))

    if tesseract_cmd:
        base = Path(tesseract_cmd).parent
        candidates.append(str(base / "tessdata"))
        candidates.append(str(base))

    # First match wins.
    for c in candidates:
        if _has_traineddata(c, langs=langs):
            return c

    return None


def _normalize_text_utf8(text: str) -> str:
    """Normalize and clean extracted text.

    - NFKC normalization (stabilizes Indic glyph variants)
    - Remove most control characters
    - Collapse excessive whitespace while preserving newlines
    """

    t = unicodedata.normalize("NFKC", text or "")
    t = t.replace("\u00a0", " ")  # NBSP
    t = t.replace("\ufeff", "")  # BOM

    # Remove control chars except \n and \t
    t = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", t)

    # Collapse excessive spaces per line, keep newlines.
    lines = [" ".join(line.split()).strip() for line in t.splitlines()]
    return "\n".join([ln for ln in lines if ln]).strip()


def convert_pdf_page_to_image(page: Any, *, dpi: int = 300):
    """Convert a PDF page to a PIL Image.

    Supports:
    - fitz.Page (PyMuPDF): attempts pdf2image when a real pdf path is known,
      otherwise falls back to PyMuPDF rasterization.
    - tuple (pdf_path: str, page_number: int): uses pdf2image.

    Returns: PIL.Image.Image
    """

    try:
        from PIL import Image  # type: ignore
    except Exception as e:  # pragma: no cover
        raise RuntimeError("Pillow is required for OCR image conversion") from e

    # 1) Explicit (pdf_path, page_number) input.
    if isinstance(page, tuple) and len(page) == 2:
        pdf_path, page_number = page
        return _convert_from_path(str(pdf_path), int(page_number), dpi=int(dpi))

    # 2) fitz.Page input (avoid importing fitz at module import time).
    try:
        page_number = int(getattr(page, "number", 0)) + 1
        parent = getattr(page, "parent", None)
        pdf_path = None
        if parent is not None:
            name = getattr(parent, "name", None)
            if isinstance(name, str) and name and Path(name).exists():
                pdf_path = name

        if pdf_path:
            try:
                return _convert_from_path(str(pdf_path), int(page_number), dpi=int(dpi))
            except Exception:
                # Fall back to PyMuPDF rasterization below.
                pass

        # PyMuPDF rasterization fallback
        pix = page.get_pixmap(dpi=int(dpi))
        return Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    except Exception as e:
        raise RuntimeError("Failed to convert PDF page to image for OCR") from e


def _convert_from_path(pdf_path: str, page_number: int, *, dpi: int):
    try:
        from pdf2image import convert_from_path  # type: ignore
    except Exception as e:
        raise RuntimeError(
            "pdf2image is required for OCR PDF->image conversion. "
            "Install pdf2image (and Poppler on Windows) or rely on the PyMuPDF rasterization fallback."
        ) from e

    images = convert_from_path(
        pdf_path,
        dpi=int(dpi),
        first_page=int(page_number),
        last_page=int(page_number),
        fmt="png",
        thread_count=1,
    )
    if not images:
        raise RuntimeError("pdf2image returned no images")
    return images[0]


def preprocess_image_for_ocr(image: Any):
    """Preprocess a PIL image for OCR using OpenCV.

    Steps:
    - grayscale
    - denoise
    - thresholding

    Returns: PIL.Image.Image
    """

    try:
        import numpy as np  # type: ignore
        import cv2  # type: ignore
        from PIL import Image  # type: ignore
    except Exception:
        # If OpenCV/Numpy aren't available, keep it simple.
        try:
            return image.convert("L")
        except Exception:
            return image

    if not hasattr(image, "convert"):
        raise RuntimeError("preprocess_image_for_ocr expects a PIL image")

    img = image.convert("RGB")
    arr = np.array(img)

    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)

    # Denoise (fast + effective)
    gray = cv2.medianBlur(gray, 3)

    # Adaptive thresholding works well for uneven lighting
    thr = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        35,
        11,
    )

    # Morphological opening to remove tiny noise
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    opened = cv2.morphologyEx(thr, cv2.MORPH_OPEN, kernel, iterations=1)

    return Image.fromarray(opened)


def extract_text_from_image(image: Any, *, lang: str = DEFAULT_OCR_LANGS, config: str = "") -> str:
    """Extract text from a preprocessed PIL image using Tesseract."""

    try:
        import pytesseract  # type: ignore
    except Exception as e:
        raise RuntimeError("pytesseract is required for OCR") from e

    cmd = _resolve_tesseract_cmd()
    if cmd:
        try:
            pytesseract.pytesseract.tesseract_cmd = cmd
        except Exception:
            pass

    tessdata_dir = _resolve_tessdata_dir(tesseract_cmd=cmd, langs=str(lang))
    if tessdata_dir:
        # Override even if set incorrectly (common cause of "Error opening data file").
        os.environ["TESSDATA_PREFIX"] = tessdata_dir

    # Tesseract defaults are OK; keep config override for callers.
    raw = pytesseract.image_to_string(image, lang=lang, config=(config or ""))
    return _normalize_text_utf8(raw)


def detect_language(text: str) -> str:
    """Very lightweight script-based language detection.

    Returns one of: "hindi", "marathi", "gujarati", "english"

    Note: Hindi and Marathi share Devanagari. Without a dictionary-based model,
    we treat Devanagari as "marathi" only when explicitly requested by callers.
    For ingestion/ocr we usually OCR with all langs anyway.
    """

    t = text or ""

    has_gujarati = any(0x0A80 <= ord(ch) <= 0x0AFF for ch in t)
    if has_gujarati:
        return "gujarati"

    has_devanagari = any(0x0900 <= ord(ch) <= 0x097F for ch in t)
    if has_devanagari:
        # Heuristic: Marathi often contains the "ळ" character.
        if "ळ" in t or "ऱ" in t:
            return "marathi"
        return "hindi"

    return "english"


def is_text_valid(text: str, *, min_length: int = 50, max_bad_ratio: float = 0.06) -> bool:
    """Heuristic validity check for PyMuPDF-extracted text.

    Invalid if:
    - too short
    - too many replacement/control characters
    """

    t = _normalize_text_utf8(text)
    if len(t) < int(min_length):
        return False

    total = 0
    bad = 0
    for ch in t:
        if ch.isspace():
            continue
        total += 1
        o = ord(ch)
        if ch == "\ufffd" or (o < 32 and ch not in "\n\t"):
            bad += 1

    if total <= 0:
        return False

    return (bad / total) <= float(max_bad_ratio)
