"""FAISS vector store persisted on disk.

Stores embeddings for chapter/topic chunks. Metadata is persisted separately in
JSON so we can map FAISS ids -> chunk metadata.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple

import faiss
import numpy as np

from app.config import settings


@dataclass
class VectorMeta:
    textbook_id: int
    chapter_key: str
    chapter_title: str
    topic_key: str
    topic_title: str
    chunk_id: str
    page_start: int | None = None
    page_end: int | None = None

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "VectorMeta":
        """Backwards-compatible loader for persisted metadata."""

        return VectorMeta(
            textbook_id=int(data.get("textbook_id")),
            chapter_key=str(data.get("chapter_key")),
            chapter_title=str(data.get("chapter_title")),
            topic_key=str(data.get("topic_key")),
            topic_title=str(data.get("topic_title")),
            chunk_id=str(data.get("chunk_id")),
            page_start=int(data["page_start"]) if data.get("page_start") is not None else None,
            page_end=int(data["page_end"]) if data.get("page_end") is not None else None,
        )


class FaissVectorStore:
    """A simple local FAISS store with disk persistence."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._index: Optional[faiss.Index] = None
        self._dim: Optional[int] = None
        self._meta: List[VectorMeta] = []

        self._root = Path(settings.data_dir)
        self._index_path = self._root / settings.faiss_index_path
        self._meta_path = self._root / settings.faiss_meta_path

        self._root.mkdir(parents=True, exist_ok=True)
        self._index_path.parent.mkdir(parents=True, exist_ok=True)

        self._load_if_exists()

    def _load_if_exists(self) -> None:
        if self._index_path.exists() and self._meta_path.exists():
            self._index = faiss.read_index(str(self._index_path))
            with self._meta_path.open("r", encoding="utf-8") as f:
                raw = json.load(f)
            self._meta = [VectorMeta.from_dict(m) for m in raw.get("meta", [])]
            self._dim = self._index.d

    def _ensure_index(self, dim: int) -> None:
        if self._index is None:
            # Cosine similarity: use inner product with normalized vectors.
            self._index = faiss.IndexFlatIP(dim)
            self._dim = dim

    def add(self, vectors: np.ndarray, metas: List[VectorMeta]) -> None:
        """Add vectors + metadata and persist."""

        if vectors.ndim != 2:
            raise ValueError("vectors must be 2D")
        if len(metas) != vectors.shape[0]:
            raise ValueError("metas length must match vectors rows")

        with self._lock:
            self._ensure_index(vectors.shape[1])
            assert self._index is not None
            assert self._dim is not None
            if vectors.shape[1] != self._dim:
                raise ValueError(f"Embedding dim mismatch: got {vectors.shape[1]}, expected {self._dim}")

            self._index.add(vectors)
            self._meta.extend(metas)
            self.persist()

    def search(self, vector: np.ndarray, top_k: int = 8) -> List[Tuple[float, VectorMeta]]:
        """Search for nearest neighbors."""

        if vector.ndim != 1:
            raise ValueError("query vector must be 1D")

        with self._lock:
            if self._index is None or self._index.ntotal == 0:
                return []

            q = np.expand_dims(vector.astype("float32"), axis=0)
            scores, ids = self._index.search(q, top_k)

            results: List[Tuple[float, VectorMeta]] = []
            for score, idx in zip(scores[0].tolist(), ids[0].tolist()):
                if idx < 0 or idx >= len(self._meta):
                    continue
                results.append((float(score), self._meta[idx]))
            return results

    def has_chapter(self, chapter_key: str) -> bool:
        chapter_key = (chapter_key or "").strip()
        if not chapter_key:
            return False
        with self._lock:
            return any((m.chapter_key == chapter_key) for m in self._meta)

    def chunk_ids_for_textbook(self, textbook_id: int) -> List[str]:
        """Return all chunk_ids belonging to a given textbook (from metadata)."""

        tid = int(textbook_id)
        with self._lock:
            if not self._meta:
                return []
            return [m.chunk_id for m in self._meta if int(m.textbook_id) == tid and str(m.chunk_id or "").strip()]

    def search_chapter(self, vector: np.ndarray, chapter_key: str, top_k: int = 8) -> List[Tuple[float, VectorMeta]]:
        """Search only within a single chapter.

        This does NOT run a global FAISS search and then prune; it computes
        similarities only against vectors whose metadata matches `chapter_key`.
        """

        if vector.ndim != 1:
            raise ValueError("query vector must be 1D")

        chapter_key = (chapter_key or "").strip()
        if not chapter_key:
            raise ValueError("chapter_key is required")

        with self._lock:
            if self._index is None or self._index.ntotal == 0 or not self._meta:
                return []

            indices = [i for i, m in enumerate(self._meta) if m.chapter_key == chapter_key]
            if not indices:
                return []

            dim = int(self._index.d)
            q = vector.astype("float32")
            if q.shape[0] != dim:
                raise ValueError(f"Embedding dim mismatch: got {q.shape[0]}, expected {dim}")

            # Reconstruct only the chapter's vectors, then score via dot product.
            mat = np.zeros((len(indices), dim), dtype="float32")
            for row_i, vec_i in enumerate(indices):
                mat[row_i, :] = self._index.reconstruct(int(vec_i))

            scores = mat @ q
            k = int(min(max(top_k, 1), scores.shape[0]))

            # Partial sort for top-k, then order.
            top_rows = np.argpartition(-scores, k - 1)[:k]
            top_rows = top_rows[np.argsort(-scores[top_rows])]

            results: List[Tuple[float, VectorMeta]] = []
            for row_i in top_rows.tolist():
                meta_idx = indices[int(row_i)]
                results.append((float(scores[int(row_i)]), self._meta[int(meta_idx)]))

            return results

    def persist(self) -> None:
        """Persist index + metadata to disk."""

        assert self._index is not None
        tmp_index = str(self._index_path) + ".tmp"
        tmp_meta = str(self._meta_path) + ".tmp"

        faiss.write_index(self._index, tmp_index)
        with open(tmp_meta, "w", encoding="utf-8") as f:
            json.dump({"meta": [asdict(m) for m in self._meta]}, f, ensure_ascii=False)

        os.replace(tmp_index, self._index_path)
        os.replace(tmp_meta, self._meta_path)

    def delete_textbook(self, textbook_id: int) -> int:
        """Remove all vectors/metadata belonging to a textbook.

        This rebuilds the FAISS index by reconstructing stored vectors.
        Returns number of removed vectors.
        """

        with self._lock:
            if self._index is None or self._index.ntotal == 0 or not self._meta:
                return 0

            keep_indices: List[int] = []
            removed = 0
            for i, m in enumerate(self._meta):
                if int(m.textbook_id) == int(textbook_id):
                    removed += 1
                else:
                    keep_indices.append(i)

            if removed == 0:
                return 0

            dim = int(self._index.d)

            # If everything is removed, reset store to empty.
            if not keep_indices:
                self._index = faiss.IndexFlatIP(dim)
                self._dim = dim
                self._meta = []
                self.persist()
                return removed

            # Reconstruct all vectors (IndexFlatIP supports this) and keep only desired rows.
            try:
                all_vecs = self._index.reconstruct_n(0, self._index.ntotal)
                vecs = np.asarray(all_vecs, dtype="float32")
            except Exception:
                # Fallback: reconstruct one-by-one (slower but robust).
                vecs = np.zeros((int(self._index.ntotal), dim), dtype="float32")
                for i in range(int(self._index.ntotal)):
                    vecs[i, :] = self._index.reconstruct(i)

            kept_vecs = vecs[keep_indices]
            kept_meta = [self._meta[i] for i in keep_indices]

            new_index = faiss.IndexFlatIP(dim)
            new_index.add(kept_vecs)

            self._index = new_index
            self._dim = dim
            self._meta = kept_meta
            self.persist()
            return removed


_store: Optional[FaissVectorStore] = None


def get_store() -> FaissVectorStore:
    global _store
    if _store is None:
        _store = FaissVectorStore()
    return _store
