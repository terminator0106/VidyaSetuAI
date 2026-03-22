"""OpenAI client wrapper.

Centralizes model calls and enforces consistent, low-bandwidth prompts.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI
from openai import RateLimitError

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


# Groq/OpenAI 429s can stall ingestion because the OpenAI SDK defaults to
# long internal retries (tens of seconds). We disable those retries and
# implement a small in-process cooldown so we can degrade gracefully
# (e.g., skip translation/compression) instead of timing out the request.
_RATE_LIMITED_UNTIL_MONO: float = 0.0


def _retry_after_seconds_from_error(err: BaseException) -> float | None:
    # Try HTTP headers (OpenAI SDK errors often expose `.response`).
    resp = getattr(err, "response", None)
    headers = getattr(resp, "headers", None)
    if headers is not None:
        try:
            ra = headers.get("retry-after") or headers.get("Retry-After")
            if ra is not None:
                return max(0.0, float(str(ra).strip()))
        except Exception:
            pass

    # Best-effort parse from message.
    try:
        msg = str(err)
        m = re.search(r"(?:retry(?:ing)?\s*in|try\s*again\s*in)\s*(\d+(?:\.\d+)?)\s*s", msg, re.IGNORECASE)
        if m:
            return max(0.0, float(m.group(1)))
    except Exception:
        pass
    return None


def _is_rate_limit_error(err: BaseException) -> bool:
    if isinstance(err, RateLimitError):
        return True
    sc = getattr(err, "status_code", None)
    return sc == 429


def _activate_rate_limit_cooldown(err: BaseException) -> None:
    global _RATE_LIMITED_UNTIL_MONO
    retry_after = _retry_after_seconds_from_error(err)

    # Keep cooldown short so we can keep making progress.
    # If server tells us a specific wait, honor it up to 60s.
    cooldown = 15.0
    if retry_after is not None:
        cooldown = min(60.0, max(5.0, float(retry_after)))

    _RATE_LIMITED_UNTIL_MONO = max(_RATE_LIMITED_UNTIL_MONO, time.monotonic() + cooldown)


def _rate_limit_seconds_left() -> float:
    return max(0.0, _RATE_LIMITED_UNTIL_MONO - time.monotonic())


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        if not settings.openai_api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not configured. Set it or switch LLM_PROVIDER=groq."
            )
        # Disable long internal retries; we degrade gracefully at call sites.
        _client = AsyncOpenAI(api_key=settings.openai_api_key, max_retries=0, timeout=30.0)
    return _client


async def chat_text(
    model: str,
    messages: List[Dict[str, str]],
    temperature: float = 0.2,
    max_tokens: int | None = None,
) -> LlmResult:
    # Fail fast when we know the provider is rate-limiting.
    left = _rate_limit_seconds_left()
    if left > 0:
        raise RuntimeError(f"LLM provider rate-limited; skipping call for ~{left:.0f}s")

    if settings.llm_provider == "groq":
        try:
            groq_res = await groq_chat_text(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return LlmResult(text=groq_res.text, model=groq_res.model, usage=None)
        except Exception as e:
            if _is_rate_limit_error(e):
                _activate_rate_limit_cooldown(e)
            raise

    client = _get_client()
    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except Exception as e:
        if _is_rate_limit_error(e):
            _activate_rate_limit_cooldown(e)
        raise

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
