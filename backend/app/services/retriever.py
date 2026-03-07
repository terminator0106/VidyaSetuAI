"""Retrieval + pruning.

Uses FAISS to retrieve top-K relevant chunks then aggregates relevance at a
chapter level.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from app.services.embedder import embed_query
from app.services.vector_store import VectorMeta, get_store


@dataclass(frozen=True)
class RetrievedChunk:
    score: float
    meta: VectorMeta


def retrieve_top_k(question_en: str, top_k: int = 12) -> List[RetrievedChunk]:
    store = get_store()
    qv = embed_query(question_en)
    hits = store.search(qv, top_k=top_k)
    return [RetrievedChunk(score=s, meta=m) for s, m in hits]


def retrieve_top_k_for_chapter(question_en: str, chapter_key: str, top_k: int = 12) -> List[RetrievedChunk]:
    """Retrieve top-K chunks restricted to a single chapter."""

    store = get_store()
    qv = embed_query(question_en)
    hits = store.search_chapter(qv, chapter_key=chapter_key, top_k=top_k)
    return [RetrievedChunk(score=s, meta=m) for s, m in hits]


def top_chapters(chunks: List[RetrievedChunk], max_chapters: int = 3, min_score: float = 0.15) -> List[Tuple[str, float]]:
    """Aggregate chunk scores into chapter-level relevance."""

    by_chapter: Dict[str, float] = defaultdict(float)
    for c in chunks:
        if c.score < min_score:
            continue
        by_chapter[c.meta.chapter_key] += c.score

    ranked = sorted(by_chapter.items(), key=lambda x: x[1], reverse=True)
    return ranked[:max_chapters]


def prune_chunks_to_chapters(chunks: List[RetrievedChunk], allowed_chapter_keys: List[str]) -> List[RetrievedChunk]:
    allow = set(allowed_chapter_keys)
    return [c for c in chunks if c.meta.chapter_key in allow]
