"""Translation utilities for internal standardization.

We translate textbook chunk text to English before embedding so retrieval is
language-agnostic.

- Original extracted text remains stored alongside translated text.
- Uses the configured LLM provider; by default Groq.
"""

from __future__ import annotations

import asyncio
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

    # Fast path: don't spend tokens translating English to English.
    if lang.code == "en":
        return src

    # Keep prompts small to reduce TPM usage.
    max_chars = 12000
    src_for_llm = src[:max_chars]

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
                f"Text:\n{src_for_llm}"
            ),
        },
    ]

    try:
        res = await chat_text(model=settings.model_small, messages=messages, temperature=0.0, max_tokens=900)
        out = (res.text or "").strip()
        return out or src
    except Exception as e:
        msg = str(e)
        if "rate-limited" in msg.lower() and "skipping call" in msg.lower():
            logger.info("LLM rate-limited; skipping chunk translation", extra={"extra": {"err": msg}})

            # Wait out the cooldown once, then retry a single time.
            try:
                import re

                m = re.search(r"~(\d+)s", msg)
                wait_s = float(m.group(1)) if m else 10.0
                await asyncio.sleep(min(30.0, max(1.0, wait_s + 0.5)))
                res2 = await chat_text(model=settings.model_small, messages=messages, temperature=0.0, max_tokens=900)
                out2 = (res2.text or "").strip()
                return out2 or src
            except Exception:
                return src

        # Rate-limit from provider (429) or any other error: don't drop content.
        logger.warning("Chunk translation failed; using original text", extra={"extra": {"err": msg}})
        return src
