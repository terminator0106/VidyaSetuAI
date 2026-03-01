"""Pre-compress cached study notes.

This script is optional; it can be run after ingestion to ensure chapter
compressed contexts are present in Redis.

Usage:
  python -m scripts.precompress_faqs --textbook-id 1

Despite the name, it precompresses chapter contexts (the critical cache for ask).
"""

from __future__ import annotations

import argparse
import asyncio
import json
from typing import Dict, List

from app.config import settings
from app.redis_client import get_redis
from app.services.cache_keys import chapter_compressed_key, chapter_raw_key
from app.services.llm_client import chat_text
from app.services.textbook_store import chunks_path


async def _run(textbook_id: int) -> None:
    raw = json.loads(chunks_path(textbook_id).read_text(encoding="utf-8"))
    chunks = raw.get("chunks", [])

    by_ch: Dict[str, List[str]] = {}
    for c in chunks:
        ch_key = str(c.get("chapter_key") or "")
        txt = str(c.get("text") or "")
        if not ch_key or not txt.strip():
            continue
        by_ch.setdefault(ch_key, []).append(txt.strip())

    r = get_redis()

    for ch_key, parts in by_ch.items():
        chapter_raw = "\n\n".join(parts)[:40000]
        if not chapter_raw.strip():
            continue

        await r.set(chapter_raw_key(ch_key), chapter_raw)

        messages = [
            {
                "role": "system",
                "content": (
                    "You compress a chapter into short study notes for retrieval. "
                    "Keep key definitions, formulas, and typical examples. "
                    "Use bullet points, very simple language."
                ),
            },
            {"role": "user", "content": chapter_raw},
        ]
        comp = await chat_text(model=settings.openai_model_small, messages=messages, temperature=0.0)
        if comp.text.strip():
            await r.set(chapter_compressed_key(ch_key), comp.text.strip())

        print(f"Precompressed: {ch_key}")

    print("Done.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--textbook-id", type=int, required=True)
    args = parser.parse_args()
    asyncio.run(_run(int(args.textbook_id)))


if __name__ == "__main__":
    main()
