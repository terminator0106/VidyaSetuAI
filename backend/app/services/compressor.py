"""Context compression.

Takes large textbook chunks and compresses them into a small, question-targeted
context suitable for final answering.

This is mandatory and runs before final answer generation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from app.config import settings
from app.services.llm_client import chat_text
from app.utils.token_utils import count_tokens


@dataclass(frozen=True)
class CompressedContext:
    text: str
    input_tokens_est: int


async def compress_chunks(
    question_en: str,
    chunks: List[str],
    difficulty: str,
    target_tokens: int = 900,
) -> CompressedContext:
    """Compress chunks into a focused study note.

    Strategy:
    - Summarize each chunk into key facts relevant to the question
    - Merge and trim to target token budget
    """

    # Limit number of chunks passed to the compressor to control cost.
    chunks = [c for c in chunks if c.strip()][:8]

    per_chunk_notes: List[str] = []
    for chunk in chunks:
        messages = [
            {
                "role": "system",
                "content": (
                    "You compress textbook content for a rural student tutoring system. "
                    "Extract only the facts needed to answer the student's question. "
                    "Use simple language. Output short bullet points."
                ),
            },
            {
                "role": "user",
                "content": f"Question: {question_en}\nDifficulty: {difficulty}\n\nTextbook chunk:\n{chunk}",
            },
        ]
        res = await chat_text(model=settings.model_small, messages=messages, temperature=0.0)
        note = res.text.strip()
        if note:
            per_chunk_notes.append(note)

    merged = "\n\n".join(per_chunk_notes).strip()

    # Final trim pass if needed.
    token_est = count_tokens(merged, model=settings.model_small)
    if token_est > target_tokens:
        messages = [
            {
                "role": "system",
                "content": "Shorten the notes while keeping only what is needed to answer. Output bullet points only.",
            },
            {
                "role": "user",
                "content": f"Target token budget: {target_tokens}\n\nNotes:\n{merged}",
            },
        ]
        res2 = await chat_text(model=settings.model_small, messages=messages, temperature=0.0)
        merged = res2.text.strip()
        token_est = count_tokens(merged, model=settings.model_small)

    return CompressedContext(text=merged, input_tokens_est=token_est)
