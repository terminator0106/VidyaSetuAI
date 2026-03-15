from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class LanguagePack:
    code: str
    name: str
    index_keywords: Tuple[str, ...]
    toc_markers: Tuple[str, ...]

    # Optional hint to improve translation quality.
    translate_hint: str = ""
