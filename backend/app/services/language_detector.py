"""Lightweight language detection.

Primary: `langdetect` if installed (helps distinguish Hindi vs Marathi).
Fallback: script-range heuristics for Indian scripts.
Final fallback: Groq model classification if still uncertain.

If no signal is found, we treat as English.
"""

from __future__ import annotations

from dataclasses import dataclass

import logging

from app.config import settings
from app.services.llm_client import chat_text

logger = logging.getLogger(__name__)


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

    # 1) Try langdetect if installed.
    try:
        from langdetect import detect_langs  # type: ignore

        # langdetect expects some length.
        if len(text.strip()) >= 10:
            langs = detect_langs(text)
            if langs:
                top = langs[0]
                code = str(getattr(top, "lang", "")).lower()
                prob = float(getattr(top, "prob", 0.0))
                if code in {"en", "hi", "mr", "gu"} and prob >= 0.70:
                    name = {
                        "en": "English",
                        "hi": "Hindi",
                        "mr": "Marathi",
                        "gu": "Gujarati",
                    }[code]
                    return Language(code=code, name=name)
    except Exception:
        pass
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


async def detect_language_async(text: str) -> Language:
    """Async language detection with Groq fallback.

    Use this in API routes where we can afford an LLM call when needed.
    """

    base = detect_language(text)

    # Script heuristic can't separate Hindi vs Marathi (both Devanagari).
    if base.code != "hi":
        return base

    try:
        messages = [
            {
                "role": "system",
                "content": "Identify the language of the text. Output exactly one code: en, hi, mr, gu.",
            },
            {"role": "user", "content": (text or "").strip()[:2000]},
        ]
        res = await chat_text(model=settings.model_small, messages=messages, temperature=0.0, max_tokens=10)
        out = (res.text or "").strip().lower()
        if out in {"en", "hi", "mr", "gu"}:
            name2 = {
                "en": "English",
                "hi": "Hindi",
                "mr": "Marathi",
                "gu": "Gujarati",
            }[out]
            return Language(code=out, name=name2)
    except Exception as e:
        logger.debug("Groq language fallback failed", extra={"extra": {"err": str(e)}})

    return base
