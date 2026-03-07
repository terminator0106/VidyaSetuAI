from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class AnswerConstraints:
    marks: int | None
    question_type: str
    max_words: int
    max_tokens: int
    instruction: str


_MARKS_RE = re.compile(r"\b(\d{1,2})\s*(?:marks?|mark)\b", re.IGNORECASE)


def infer_answer_constraints(question_en: str, mode: str = "default") -> AnswerConstraints:
    """Infer answer-length constraints.

    We keep this heuristic-based so the API doesn't require new fields.
    """

    q_raw = question_en or ""
    q = q_raw.lower()

    marks: int | None = None
    m = _MARKS_RE.search(q)
    if m:
        try:
            marks = int(m.group(1))
        except Exception:
            marks = None

    is_mcq = "mcq" in q or "choose the correct" in q or bool(
        re.search(r"\b(a\)|b\)|c\)|d\))", q_raw, flags=re.IGNORECASE)
    )

    # Default: keep it short but still helpful.
    max_words = 180
    question_type = "general"

    # Phrase-based type hints (common exam patterns).
    if "one word" in q or "in one word" in q:
        question_type = "very_short"
        max_words = 20
    elif "one sentence" in q or "in one sentence" in q or "one line" in q or "in one line" in q:
        question_type = "very_short"
        max_words = 35
    elif re.search(r"\b\d+\s*-\s*\d+\s*lines?\b", q):
        question_type = "very_short"
        max_words = 80
    elif "very short answer" in q:
        question_type = "very_short"
        max_words = 70
    elif "short answer" in q or "short note" in q or "in brief" in q:
        question_type = "short"
        max_words = 150
    elif "long answer" in q or "detailed" in q:
        question_type = "long"
        max_words = 520

    if is_mcq:
        question_type = "mcq"
        max_words = 80
    elif marks is not None:
        question_type = "marks"
        if marks <= 1:
            max_words = 60
        elif marks <= 2:
            max_words = 110
        elif marks <= 4:
            max_words = 180
        elif marks <= 5:
            max_words = 240
        elif marks <= 10:
            max_words = 450
        else:
            max_words = 600

    # Mode adjustments.
    if mode == "step_by_step":
        max_words = int(max_words * 1.25)

    # Convert to token cap. Roughly 1 token ~= 0.75 words (varies), so allow slack.
    max_tokens = max(128, min(1200, int(max_words / 0.7)))

    if question_type == "mcq":
        instruction = (
            f"Keep it concise (<= ~{max_words} words). "
            "If it's an MCQ, first state the correct option (A/B/C/D) then give a 1-2 sentence reason."
        )
    elif marks is not None:
        instruction = (
            f"Answer to match a {marks}-mark question. Keep it within ~{max_words} words; "
            "include only the necessary steps/points."
        )
    else:
        instruction = f"Keep the answer concise (<= ~{max_words} words) while staying accurate."

    return AnswerConstraints(
        marks=marks,
        question_type=question_type,
        max_words=max_words,
        max_tokens=max_tokens,
        instruction=instruction,
    )
