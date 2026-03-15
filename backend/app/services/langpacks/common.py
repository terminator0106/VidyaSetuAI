from __future__ import annotations

# Tesseract language codes used for multilingual OCR.
OCR_LANGS_ALL = "eng+hin+mar+guj"

# Normalize common Indic digits to ASCII digits for int() parsing.
_DIGIT_TRANSLATION = str.maketrans(
    {
        # Devanagari ०-९ (Hindi/Marathi)
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


def ascii_digits(s: str) -> str:
    return (s or "").translate(_DIGIT_TRANSLATION)


def count_script_letters(text: str) -> int:
    """Count letters in Latin/Devanagari/Gujarati scripts."""

    t = text or ""
    n = 0
    for ch in t:
        o = ord(ch)
        if ch.isalpha() or (0x0900 <= o <= 0x097F) or (0x0A80 <= o <= 0x0AFF):
            n += 1
    return n
