"""Translation utilities for internal standardization.

We translate textbook chunk text to English before embedding so retrieval is
language-agnostic.

- Original extracted text remains stored alongside translated text.
- Uses the configured LLM provider; by default Groq.
"""

from __future__ import annotations

import logging

from app.config import settings
from app.services.language_detector import detect_language
from app.services.langpacks import get_pack
from app.services.llm_client import chat_text

logger = logging.getLogger(__name__)


async def translate_chunk_to_english(*, text: str) -> str:
    """Translate a chunk to English for embedding.

    Returns English text only. If translation fails, returns the original text
    to avoid dropping content.
    """

    src = (text or "").strip()
    if not src:
        return ""

    lang = detect_language(src)
    pack = get_pack(lang.code)

    messages = [
        {
            "role": "system",
            "content": (
                "Translate the given textbook content to English for semantic search embeddings. "
                "Preserve meaning, numbers, units, and formulas. "
                "Output ONLY the English translation (no explanations)."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Source language: {pack.name} ({pack.code}). {pack.translate_hint}\n"
                f"Text:\n{src[:45000]}"
            ),
        },
    ]

    try:
        res = await chat_text(model=settings.model_small, messages=messages, temperature=0.0, max_tokens=1400)
        out = (res.text or "").strip()
        return out or src
    except Exception as e:
        logger.warning("Chunk translation failed; using original text", extra={"extra": {"err": str(e)}})
        return src
