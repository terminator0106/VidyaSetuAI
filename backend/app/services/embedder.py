"""Embeddings via sentence-transformers.

We use a small, fast model by default and normalize embeddings for cosine
similarity search in FAISS.
"""

from __future__ import annotations

from functools import lru_cache
from typing import List

import numpy as np
from sentence_transformers import SentenceTransformer

from app.config import settings


@lru_cache(maxsize=1)
def _model() -> SentenceTransformer:
    return SentenceTransformer(settings.embedding_model)


def embed_texts(texts: List[str]) -> np.ndarray:
    """Embed a list of texts into a 2D numpy array (float32, normalized)."""

    model = _model()
    emb = model.encode(texts, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False)
    return emb.astype("float32")


def embed_query(text: str) -> np.ndarray:
    """Embed a query string into a 1D numpy array (float32, normalized)."""

    arr = embed_texts([text])
    return arr[0]
