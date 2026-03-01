"""Token counting utilities using tiktoken."""

from __future__ import annotations

from functools import lru_cache

import tiktoken


@lru_cache(maxsize=32)
def _encoding_for_model(model: str):
    try:
        return tiktoken.encoding_for_model(model)
    except KeyError:
        return tiktoken.get_encoding("o200k_base")


def count_tokens(text: str, model: str) -> int:
    """Count tokens for a string using the model's encoding."""

    enc = _encoding_for_model(model)
    return len(enc.encode(text or ""))
