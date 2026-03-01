"""Session memory stored in Redis.

We keep a short running summary to provide continuity without sending full
history each time.
"""

from __future__ import annotations

from app.config import settings
from app.redis_client import get_redis
from app.services.cache_keys import session_summary_key
from app.services.llm_client import chat_text


async def get_summary(session_id: int) -> str:
    r = get_redis()
    return (await r.get(session_summary_key(session_id))) or ""


async def update_summary(session_id: int, question_en: str, answer_en: str) -> str:
    """Update the running summary with the latest Q/A."""

    r = get_redis()
    prev = (await r.get(session_summary_key(session_id))) or ""

    messages = [
        {
            "role": "system",
            "content": (
                "You maintain a short tutoring session memory. "
                "Write a concise summary of what the student is learning, key misconceptions, and what was answered. "
                "Keep it under 1200 characters."
            ),
        },
        {
            "role": "user",
            "content": f"Previous summary:\n{prev}\n\nNew exchange:\nQ: {question_en}\nA: {answer_en}",
        },
    ]

    res = await chat_text(model=settings.openai_model_small, messages=messages, temperature=0.0)
    summary = res.text.strip()
    if summary:
        await r.set(session_summary_key(session_id), summary)
    return summary
