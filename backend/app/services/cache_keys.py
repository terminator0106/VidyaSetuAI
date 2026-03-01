"""Redis cache key conventions."""

from __future__ import annotations


def chunk_key(textbook_id: int, chunk_id: str) -> str:
    return f"chunk:{textbook_id}:{chunk_id}"


def chapter_raw_key(chapter_key: str) -> str:
    return f"chapter_raw:{chapter_key}"


def chapter_compressed_key(chapter_key: str) -> str:
    return f"chapter_comp:{chapter_key}"


def session_summary_key(session_id: int) -> str:
    return f"session_summary:{session_id}"
