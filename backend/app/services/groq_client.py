"""Groq client (OpenAI-compatible).

This is a thin wrapper around Groq's OpenAI-compatible chat completions endpoint.
Call sites are responsible for prompt discipline (e.g., strict JSON when needed).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI

from app.config import settings


@dataclass(frozen=True)
class GroqResult:
    text: str
    model: str


_client: Optional[AsyncOpenAI] = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        if not settings.groq_api_key:
            raise RuntimeError("GROQ_API_KEY is not configured")
        _client = AsyncOpenAI(api_key=settings.groq_api_key, base_url=settings.groq_base_url)
    return _client


async def groq_chat_text(
    model: str,
    messages: List[Dict[str, str]],
    temperature: float = 0.0,
    max_tokens: int | None = None,
) -> GroqResult:
    """Run a chat completion against Groq's OpenAI-compatible endpoint."""

    client = _get_client()
    resp = await client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    choice = resp.choices[0]
    text = (choice.message.content or "").strip()
    return GroqResult(text=text, model=model)
