"""Groq client (OpenAI-compatible).

Usage rules (enforced by call sites):
- This client must only be used for index parsing during ingestion.
- Responses must be strict JSON only.
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


async def groq_chat_text(model: str, messages: List[Dict[str, str]], temperature: float = 0.0) -> GroqResult:
    """Run a chat completion against Groq's OpenAI-compatible endpoint."""

    client = _get_client()
    resp = await client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
    )
    choice = resp.choices[0]
    text = (choice.message.content or "").strip()
    return GroqResult(text=text, model=model)
