"""Difficulty detection and model routing.

Rules:
- Simple / short / direct -> GPT-4o-mini
- Multi-step reasoning / long context -> GPT-4o
"""

from __future__ import annotations

from dataclasses import dataclass

from app.config import settings
from app.services.llm_client import chat_text
from app.utils.token_utils import count_tokens


@dataclass(frozen=True)
class RouteDecision:
    difficulty: str
    model: str


async def detect_difficulty(question_en: str) -> str:
    """Classify difficulty into: easy | medium | hard."""

    # Fast heuristic first.
    q = question_en.lower().strip()
    heuristic_hard = any(
        kw in q
        for kw in [
            "derive",
            "prove",
            "compare",
            "why",
            "explain why",
            "multi",
            "step-by-step",
            "step by step",
            "calculate",
            "numerical",
            "diagram",
        ]
    )

    if len(q) < 60 and not heuristic_hard:
        return "easy"

    # LLM classification using small model.
    messages = [
        {
            "role": "system",
            "content": "Classify a student question difficulty for tutoring. Output exactly one word: easy, medium, or hard.",
        },
        {"role": "user", "content": question_en},
    ]
    res = await chat_text(model=settings.openai_model_small, messages=messages, temperature=0.0)
    out = res.text.strip().lower()
    if out in {"easy", "medium", "hard"}:
        return out
    return "medium"


def route_model(estimated_input_tokens: int, difficulty: str) -> str:
    """Route to a model given estimated context size and difficulty."""

    if difficulty == "hard":
        return settings.openai_model_large

    if estimated_input_tokens <= 2400 and difficulty in {"easy", "medium"}:
        return settings.openai_model_small

    return settings.openai_model_large


def estimate_prompt_tokens(text: str, model: str) -> int:
    return count_tokens(text, model=model)
