"""Lightweight language detection for Indian scripts.

We avoid heavy dependencies to keep deployments simple.
The detector identifies script families (Hindi/Marathi -> Devanagari, Bengali,
Tamil, Telugu, Kannada, Malayalam, Gujarati, Punjabi Gurmukhi, Odia).

If no non-Latin script is found, we treat as English.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Language:
    code: str
    name: str


_RANGES = [
    ("hi", "Hindi", 0x0900, 0x097F),  # Devanagari
    ("bn", "Bengali", 0x0980, 0x09FF),
    ("pa", "Punjabi", 0x0A00, 0x0A7F),  # Gurmukhi
    ("gu", "Gujarati", 0x0A80, 0x0AFF),
    ("or", "Odia", 0x0B00, 0x0B7F),
    ("ta", "Tamil", 0x0B80, 0x0BFF),
    ("te", "Telugu", 0x0C00, 0x0C7F),
    ("kn", "Kannada", 0x0C80, 0x0CFF),
    ("ml", "Malayalam", 0x0D00, 0x0D7F),
]


def detect_language(text: str) -> Language:
    text = text or ""
    counts = {code: 0 for code, _, _, _ in _RANGES}
    total = 0

    for ch in text:
        o = ord(ch)
        for code, _, lo, hi in _RANGES:
            if lo <= o <= hi:
                counts[code] += 1
                total += 1
                break

    if total == 0:
        return Language(code="en", name="English")

    code = max(counts.items(), key=lambda x: x[1])[0]
    name = next(n for c, n, _, _ in _RANGES if c == code)
    return Language(code=code, name=name)
