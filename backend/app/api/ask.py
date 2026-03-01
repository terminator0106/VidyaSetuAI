"""Ask API.

POST /api/ask

Pipeline:
- Detect language; translate question to English if needed
- Detect difficulty
- Retrieve top-K via FAISS
- Chapter-level pruning
- Mandatory compression
- Route model (gpt-4o-mini vs gpt-4o)
- Answer generation
- Translate answer back
- Log token + INR savings
"""

from __future__ import annotations

import logging
import re
from dataclasses import asdict
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.config import settings
from app.database import db_session
from app.models.session import QueryLog, Session
from app.models.user import User
from app.redis_client import get_redis
from app.services.cache_keys import chunk_key
from app.services.compressor import compress_chunks
from app.services.cost_tracker import compute_savings
from app.services.language_detector import detect_language
from app.services.llm_client import chat_text, translate_from_english, translate_to_english
from app.services.retriever import prune_chunks_to_chapters, retrieve_top_k, top_chapters
from app.services.router import detect_difficulty, estimate_prompt_tokens, route_model
from app.services.session_memory import get_summary, update_summary
from app.services.textbook_store import load_chunk_text
from app.utils.security import get_current_user
from app.utils.token_utils import count_tokens

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ask"])


class AskContext(BaseModel):
    subjectId: Optional[str] = None
    subjectName: Optional[str] = None
    chapterId: Optional[str] = None
    chapterName: Optional[str] = None


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    sessionId: Optional[str] = None
    context: Optional[AskContext] = None
    mode: str = Field(default="default")  # default | simpler | step_by_step


def _parse_textbook_id_from_chapter_key(chapter_key: str | None) -> Optional[int]:
    if not chapter_key:
        return None
    m = re.match(r"^tb(\d+)_", chapter_key)
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None


async def _get_or_create_session(user: User, req: AskRequest) -> Session:
    session_id = None
    if req.sessionId:
        try:
            session_id = int(req.sessionId)
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid sessionId")

    chapter_key = req.context.chapterId if req.context and req.context.chapterId else None
    textbook_id = _parse_textbook_id_from_chapter_key(chapter_key)

    with db_session() as db:
        if session_id is not None:
            s = db.query(Session).filter(Session.id == session_id, Session.user_id == user.id).first()
            if not s:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
            return s

        s = Session(user_id=user.id, textbook_id=textbook_id, chapter_key=chapter_key)
        db.add(s)
        db.flush()
        return s


@router.post("/ask")
async def ask(req: AskRequest, user: User = Depends(get_current_user)) -> dict:
    if req.mode not in {"default", "simpler", "step_by_step"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid mode")

    session = await _get_or_create_session(user, req)

    lang = detect_language(req.question)
    question_en = req.question
    translation_usage = None

    if lang.code != "en":
        tr = await translate_to_english(req.question, lang.name, model=settings.openai_model_small)
        question_en = tr.text

    difficulty = await detect_difficulty(question_en)

    retrieved = retrieve_top_k(question_en, top_k=12)

    # Chapter pruning
    chapter_id = req.context.chapterId if req.context and req.context.chapterId else None
    allowed_chapters: List[str]
    if chapter_id:
        allowed_chapters = [chapter_id]
    else:
        allowed = top_chapters(retrieved, max_chapters=3)
        allowed_chapters = [k for k, _ in allowed]

    pruned = prune_chunks_to_chapters(retrieved, allowed_chapter_keys=allowed_chapters) if allowed_chapters else retrieved

    # Load chunk texts (redis first, then disk by textbook).
    r = get_redis()
    chunk_texts: List[str] = []
    baseline_texts: List[str] = []

    for item in retrieved[:8]:
        baseline_texts.append(await _load_chunk_text(r, item.meta.textbook_id, item.meta.chunk_id))

    for item in pruned[:8]:
        chunk_texts.append(await _load_chunk_text(r, item.meta.textbook_id, item.meta.chunk_id))

    # Baseline token estimate: naive RAG, all raw chunks.
    baseline_context = "\n\n".join([t for t in baseline_texts if t.strip()])
    baseline_input_tokens = count_tokens(baseline_context + "\n\n" + question_en, model=settings.openai_model_large)

    compressed = await compress_chunks(question_en=question_en, chunks=chunk_texts, difficulty=difficulty)

    # Session summary (English)
    summary = await get_summary(session.id)

    system_prompt = _system_prompt_for_mode(req.mode)
    user_prompt = _user_prompt(question_en, compressed.text, summary)

    # Route model based on estimated prompt size
    est_tokens = estimate_prompt_tokens(system_prompt + "\n" + user_prompt, model=settings.openai_model_small)
    model = route_model(estimated_input_tokens=est_tokens, difficulty=difficulty)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    res = await chat_text(model=model, messages=messages, temperature=0.2)
    answer_en = res.text

    # Update session summary
    try:
        await update_summary(session.id, question_en=question_en, answer_en=answer_en)
    except Exception:
        logger.exception("Failed updating session summary")

    # Translate back if needed
    answer_final = answer_en
    if lang.code != "en":
        tr_back = await translate_from_english(answer_en, target_lang_name=lang.name, model=settings.openai_model_small)
        answer_final = tr_back.text

    # Actual token counts
    actual_input_tokens = count_tokens(system_prompt + "\n" + user_prompt, model=model)
    actual_output_tokens = 0
    if res.usage:
        actual_output_tokens = res.usage.completion_tokens
    else:
        actual_output_tokens = count_tokens(answer_en, model=model)

    baseline_model = settings.openai_model_large
    savings = compute_savings(
        baseline_input_tokens=baseline_input_tokens,
        actual_input_tokens=actual_input_tokens,
        actual_output_tokens=actual_output_tokens,
        actual_model=model,
        baseline_model=baseline_model,
    )

    # Persist query log
    with db_session() as db:
        ql = QueryLog(
            user_id=user.id,
            session_id=session.id,
            question=req.question,
            answer=answer_final,
            model_used=model,
            language=lang.code,
            baseline_input_tokens=savings.baseline_input_tokens,
            actual_input_tokens=savings.actual_input_tokens,
            actual_output_tokens=savings.actual_output_tokens,
            tokens_saved=savings.tokens_saved,
            baseline_cost_inr=savings.baseline_cost_inr,
            actual_cost_inr=savings.actual_cost_inr,
            inr_saved=savings.inr_saved,
            avg_cost_reduction_pct=savings.avg_cost_reduction_pct,
            extra={
                "difficulty": difficulty,
                "allowed_chapters": allowed_chapters,
                "mode": req.mode,
            },
        )
        db.add(ql)

    return {
        "answer": answer_final,
        "sessionId": str(session.id),
        "metrics": {
            "tokensSaved": savings.tokens_saved,
            "inrSaved": savings.inr_saved,
            "avgCostReductionPct": savings.avg_cost_reduction_pct,
        },
    }


async def _load_chunk_text(r, textbook_id: int, chunk_id: str) -> str:
    key = chunk_key(textbook_id, chunk_id)
    cached = await r.get(key)
    if cached:
        return cached

    text = load_chunk_text(textbook_id, chunk_id)
    if text:
        await r.set(key, text)
    return text


def _system_prompt_for_mode(mode: str) -> str:
    base = (
        "You are VidyaSetu, a calm AI tutor for rural students in India. "
        "Be respectful, simple, and accurate. "
        "Use short paragraphs. If math/science, show steps clearly. "
        "If uncertain, ask a clarifying question instead of guessing."
    )
    if mode == "simpler":
        return base + " Use very simple words and a relatable example."
    if mode == "step_by_step":
        return base + " Answer step-by-step with numbered steps."
    return base


def _user_prompt(question_en: str, compressed_context: str, session_summary: str) -> str:
    parts: List[str] = []
    if session_summary.strip():
        parts.append(f"Session summary (English):\n{session_summary.strip()}")
    if compressed_context.strip():
        parts.append(f"Relevant textbook notes (compressed):\n{compressed_context.strip()}")

    parts.append(f"Student question (English):\n{question_en.strip()}")
    parts.append("Now answer in a student-friendly way.")

    return "\n\n".join(parts)
