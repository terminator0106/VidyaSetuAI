from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


_RANGE_RE = re.compile(r"(?<!\d)(\d{1,4})(?:\s*[-–—]\s*(\d{1,4}))?(?!\d)")


@dataclass(frozen=True)
class TocRow:
    y: int
    text: str
    page_start: int


def _ascii_digits(s: str) -> str:
    # Local copy to avoid import cycles; Devanagari + Gujarati digits.
    trans = str.maketrans(
        {
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
    return (s or "").translate(trans)


def _tesseract_image_to_data(img, *, lang: str, config: str) -> dict:
    import pytesseract  # type: ignore

    try:
        from pytesseract import Output  # type: ignore

        return pytesseract.image_to_data(img, lang=lang, config=config, output_type=Output.DICT)
    except Exception:
        # Fallback shape (older pytesseract): return TSV then parse.
        tsv = pytesseract.image_to_data(img, lang=lang, config=config)
        lines = [ln for ln in (tsv or "").splitlines() if ln.strip()]
        if len(lines) < 2:
            return {"text": [], "conf": [], "left": [], "top": [], "width": [], "height": []}
        header = lines[0].split("\t")
        cols = {h: [] for h in header}
        for ln in lines[1:]:
            parts = ln.split("\t")
            if len(parts) != len(header):
                continue
            for h, v in zip(header, parts):
                cols[h].append(v)
        # Normalize to dict keys used below.
        def _get_ints(key: str) -> list[int]:
            out = []
            for v in cols.get(key, []):
                try:
                    out.append(int(float(v)))
                except Exception:
                    out.append(0)
            return out

        return {
            "text": cols.get("text", []),
            "conf": cols.get("conf", []),
            "left": _get_ints("left"),
            "top": _get_ints("top"),
            "width": _get_ints("width"),
            "height": _get_ints("height"),
        }


def _prep_image(pix: fitz.Pixmap):
    from PIL import Image, ImageEnhance, ImageOps  # type: ignore

    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    img = img.convert("L")

    # Remove light backgrounds; boost contrast.
    img = ImageOps.autocontrast(img)
    img = ImageEnhance.Contrast(img).enhance(2.0)

    # Simple thresholding.
    img = img.point(lambda p: 255 if p > 190 else 0)
    return img


def _group_rows(words: list[tuple[int, int, str]]) -> list[list[tuple[int, int, str]]]:
    """Group (x, y, word) into rows by y proximity."""

    if not words:
        return []

    words.sort(key=lambda t: (t[1], t[0]))
    rows: list[list[tuple[int, int, str]]] = []
    current: list[tuple[int, int, str]] = []
    last_y = None
    # y threshold depends on DPI; this works well at 300-400dpi.
    y_thresh = 14

    for x, y, w in words:
        if last_y is None:
            current = [(x, y, w)]
            last_y = y
            continue
        if abs(y - last_y) <= y_thresh:
            current.append((x, y, w))
            last_y = int((last_y + y) / 2)
        else:
            rows.append(current)
            current = [(x, y, w)]
            last_y = y

    if current:
        rows.append(current)
    return rows


def _extract_row_page_number(row_text: str) -> Optional[int]:
    t = _ascii_digits(row_text)
    matches = list(_RANGE_RE.finditer(t))
    if not matches:
        return None
    # Prefer the last match, which tends to be the page column.
    m = matches[-1]
    try:
        return int(m.group(1))
    except Exception:
        return None


def parse_hindi_toc_table_pages(
    *,
    pdf_path: str,
    index_pages_1b: Sequence[int],
    ocr_langs: str,
) -> List[Tuple[str, int]]:
    """Parse Hindi ToC that is laid out as a colored table.

    Returns list of (title, start_page_printed).
    Title is best-effort (often includes extra columns); splitting relies on pages.
    """

    try:
        import pytesseract  # type: ignore
    except Exception:
        return []

    # Ensure pytesseract binary is resolved via the main extractor (if configured).
    _ = pytesseract

    out_rows: list[TocRow] = []

    doc = fitz.open(pdf_path)
    try:
        for p1 in index_pages_1b:
            if p1 < 1 or p1 > int(doc.page_count):
                continue
            page = doc.load_page(int(p1) - 1)
            pix = page.get_pixmap(dpi=400)
            img = _prep_image(pix)

            config = "--oem 1 --psm 6"
            data = _tesseract_image_to_data(img, lang=ocr_langs, config=config)

            texts = data.get("text", []) or []
            confs = data.get("conf", []) or []
            lefts = data.get("left", []) or []
            tops = data.get("top", []) or []
            widths = data.get("width", []) or []

            words: list[tuple[int, int, str]] = []
            n = min(len(texts), len(confs), len(lefts), len(tops), len(widths))
            for i in range(n):
                w = str(texts[i] or "").strip()
                if not w:
                    continue
                try:
                    c = float(confs[i])
                except Exception:
                    c = 0.0
                if c < 25:
                    continue

                x = int(lefts[i])
                y = int(tops[i])
                words.append((x, y, w))

            rows = _group_rows(words)
            for r in rows:
                r.sort(key=lambda t: t[0])
                row_text = " ".join([w for _, _, w in r]).strip()
                if not row_text:
                    continue

                # Skip obvious headers.
                lowered = row_text.lower()
                if "अनुक्रमणिका" in row_text or "पाठ" in row_text and "पृष्ठ" in row_text:
                    continue

                sp = _extract_row_page_number(row_text)
                if sp is None:
                    continue

                # Require some letters to avoid picking random numbers.
                letters = sum(1 for ch in row_text if ch.isalpha() or ("\u0900" <= ch <= "\u097F"))
                if letters < 3:
                    continue

                out_rows.append(TocRow(y=int(r[0][1]), text=row_text, page_start=int(sp)))

    finally:
        try:
            doc.close()
        except Exception:
            pass

    if not out_rows:
        return []

    # Sort by printed page then by y to keep stable order.
    out_rows.sort(key=lambda r: (int(r.page_start), int(r.y)))

    # Dedup by printed start page.
    seen: set[int] = set()
    result: list[tuple[str, int]] = []
    for r in out_rows:
        if r.page_start in seen:
            continue
        seen.add(int(r.page_start))
        result.append((r.text[:300], int(r.page_start)))

    return result
