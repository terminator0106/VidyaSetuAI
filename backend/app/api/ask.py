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
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.config import settings
from app.database import db_session
from app.models.session import QueryLog, Session
from app.models.user import User
from app.redis_client import get_redis
from app.services.cache_keys import chunk_key
from app.services.compressor import compress_chunks
from app.services.cost_tracker import compute_savings
from app.services.language_detector import detect_language_async
from app.services.llm_client import chat_text, translate_from_english, translate_to_english
from app.services.answer_constraints import infer_answer_constraints
from app.services.retriever import retrieve_top_k_for_chapter
from app.services.router import detect_difficulty, estimate_prompt_tokens, route_model
from app.services.session_memory import get_summary, update_summary
from app.services.textbook_store import load_chunk_text
from app.services.vector_store import get_store
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
    chapter_id: str = Field(min_length=1, max_length=128)
    sessionId: Optional[str] = None
    context: Optional[AskContext] = None
    mode: str = Field(default="default")  # default | simpler | step_by_step


class HistoryMessage(BaseModel):
    id: str
    role: str  # user | ai
    content: str
    created_at: str


class ChapterHistoryResponse(BaseModel):
    chapter_id: str
    sessionId: Optional[str] = None
    messages: List[HistoryMessage]


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


async def _get_or_create_session_id(user: User, req: AskRequest) -> int:
    session_id = None
    if req.sessionId:
        try:
            session_id = int(req.sessionId)
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid sessionId")

    chapter_key = (req.chapter_id or "").strip() or None
    textbook_id = _parse_textbook_id_from_chapter_key(chapter_key)

    with db_session() as db:
        if session_id is not None:
            s = db.query(Session).filter(Session.id == session_id, Session.user_id == user.id).first()
            if not s:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
            return int(s.id)

        # Reuse the most recent session for this chapter, if it exists.
        if chapter_key:
            existing = (
                db.query(Session)
                .filter(Session.user_id == user.id, Session.chapter_key == chapter_key)
                .order_by(Session.id.desc())
                .first()
            )
            if existing:
                return int(existing.id)

        s = Session(user_id=user.id, textbook_id=textbook_id, chapter_key=chapter_key)
        db.add(s)
        db.flush()
        return int(s.id)


@router.get("/ask/history", response_model=ChapterHistoryResponse)
async def ask_history(
    chapter_id: str = Query(min_length=1, max_length=128),
    limit: int = Query(default=60, ge=1, le=400),
    user: User = Depends(get_current_user),
) -> ChapterHistoryResponse:
    chapter_id = (chapter_id or "").strip()

    with db_session() as db:
        s = (
            db.query(Session)
            .filter(Session.user_id == user.id, Session.chapter_key == chapter_id)
            .order_by(Session.id.desc())
            .first()
        )
        if not s:
            return ChapterHistoryResponse(chapter_id=chapter_id, sessionId=None, messages=[])

        logs = (
            db.query(QueryLog)
            .filter(QueryLog.user_id == user.id, QueryLog.session_id == s.id)
            .order_by(QueryLog.created_at.asc())
            .limit(limit)
            .all()
        )

        messages: List[HistoryMessage] = []
        for ql in logs:
            created = ql.created_at.isoformat() if getattr(ql, "created_at", None) else ""
            messages.append(
                HistoryMessage(
                    id=f"{ql.id}_u",
                    role="user",
                    content=ql.question,
                    created_at=created,
                )
            )
            messages.append(
                HistoryMessage(
                    id=f"{ql.id}_a",
                    role="ai",
                    content=ql.answer,
                    created_at=created,
                )
            )

        return ChapterHistoryResponse(
            chapter_id=chapter_id,
            sessionId=str(s.id),
            messages=messages,
        )


@router.post("/ask")
async def ask(req: AskRequest, user: User = Depends(get_current_user)) -> dict:
    if req.mode not in {"default", "simpler", "step_by_step"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid mode")

    chapter_id = (req.chapter_id or "").strip()
    if not chapter_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="chapter_id is required")

    # Enforce chapter-scoped retrieval: chapter must exist in embeddings.
    if not get_store().has_chapter(chapter_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chapter not found in embeddings. Ingest the textbook/chapter first.",
        )

    session_id = await _get_or_create_session_id(user, req)

    lang = await detect_language_async(req.question)
    question_en = req.question
    translation_usage = None

    if lang.code != "en":
        try:
            tr = await translate_to_english(req.question, lang.name, model=settings.model_small)
            question_en = tr.text
        except Exception as e:
            logger.exception("translate_to_english failed")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Translation service failed ({e.__class__.__name__}). Check LLM credentials/network.",
            )

    try:
        difficulty = await detect_difficulty(question_en)
    except Exception:
        logger.exception("Difficulty detection failed; defaulting to medium")
        difficulty = "medium"

    try:
        retrieved = retrieve_top_k_for_chapter(question_en, chapter_key=chapter_id, top_k=12)
    except Exception as e:
        logger.exception("Retrieval failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Retrieval failed ({e.__class__.__name__}). Ensure vectors are built for this chapter.",
        )
    allowed_chapters = [chapter_id]
    pruned = retrieved

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
    baseline_input_tokens = count_tokens(baseline_context + "\n\n" + question_en, model=settings.model_large)

    try:
        compressed = await compress_chunks(question_en=question_en, chunks=chunk_texts, difficulty=difficulty)
        compressed_context = compressed.text
    except Exception:
        logger.exception("Compression failed; falling back to raw context")
        compressed_context = "\n\n".join([t for t in chunk_texts if t.strip()])

    # Session summary (English)
    summary = await get_summary(session_id)

    constraints = infer_answer_constraints(question_en, mode=req.mode)
    system_prompt = _system_prompt_for_mode(req.mode) + " " + constraints.instruction
    user_prompt = _user_prompt(question_en, compressed_context, summary)

    # Route model based on estimated prompt size
    est_tokens = estimate_prompt_tokens(system_prompt + "\n" + user_prompt, model=settings.model_small)
    model = route_model(estimated_input_tokens=est_tokens, difficulty=difficulty)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    try:
        res = await chat_text(model=model, messages=messages, temperature=0.2, max_tokens=constraints.max_tokens)
    except Exception as e:
        logger.exception("chat_text failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM request failed ({e.__class__.__name__}). Check LLM credentials/network.",
        )
    answer_en = res.text

    # Update session summary
    try:
        await update_summary(session_id, question_en=question_en, answer_en=answer_en)
    except Exception:
        logger.exception("Failed updating session summary")

    # Translate back if needed
    answer_final = answer_en
    if lang.code != "en":
        try:
            tr_back = await translate_from_english(
                answer_en, target_lang_name=lang.name, model=settings.model_small
            )
            answer_final = tr_back.text
        except Exception:
            logger.exception("translate_from_english failed; returning English answer")
            answer_final = answer_en

    # Actual token counts
    actual_input_tokens = count_tokens(system_prompt + "\n" + user_prompt, model=model)
    actual_output_tokens = 0
    if res.usage:
        actual_output_tokens = res.usage.completion_tokens
    else:
        actual_output_tokens = count_tokens(answer_en, model=model)

    baseline_model = settings.model_large
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
            session_id=session_id,
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
        "sessionId": str(session_id),
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
