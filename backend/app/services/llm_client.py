"""OpenAI client wrapper.

Centralizes model calls and enforces consistent, low-bandwidth prompts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI

from app.config import settings
from app.services.groq_client import groq_chat_text


@dataclass(frozen=True)
class LlmUsage:
    prompt_tokens: int
    completion_tokens: int


@dataclass(frozen=True)
class LlmResult:
    text: str
    model: str
    usage: Optional[LlmUsage]


_client: Optional[AsyncOpenAI] = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        if not settings.openai_api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not configured. Set it or switch LLM_PROVIDER=groq."
            )
        _client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _client


async def chat_text(
    model: str,
    messages: List[Dict[str, str]],
    temperature: float = 0.2,
    max_tokens: int | None = None,
) -> LlmResult:
    if settings.llm_provider == "groq":
        groq_res = await groq_chat_text(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return LlmResult(text=groq_res.text, model=groq_res.model, usage=None)

    client = _get_client()
    resp = await client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    choice = resp.choices[0]
    text = (choice.message.content or "").strip()

    usage = None
    if getattr(resp, "usage", None):
        usage = LlmUsage(
            prompt_tokens=int(resp.usage.prompt_tokens),
            completion_tokens=int(resp.usage.completion_tokens),
        )

    return LlmResult(text=text, model=model, usage=usage)


async def translate_to_english(text: str, lang_name: str, model: str) -> LlmResult:
    messages = [
        {
            "role": "system",
            "content": "You translate student questions to English for internal processing. Keep meaning, keep numbers/formulas. Output only the English translation.",
        },
        {"role": "user", "content": f"Language: {lang_name}\nText: {text}"},
    ]
    return await chat_text(model=model, messages=messages, temperature=0.0)


async def translate_from_english(text_en: str, target_lang_name: str, model: str) -> LlmResult:
    messages = [
        {
            "role": "system",
            "content": "You translate an English tutoring answer to the target language. Keep it simple, student-friendly, and preserve formulas. Output only the translated answer.",
        },
        {"role": "user", "content": f"Target language: {target_lang_name}\nAnswer (English): {text_en}"},
    ]
    return await chat_text(model=model, messages=messages, temperature=0.1)
