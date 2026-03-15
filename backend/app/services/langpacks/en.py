from __future__ import annotations

from app.services.langpacks.base import LanguagePack

PACK = LanguagePack(
    code="en",
    name="English",
    index_keywords=(
        "table of contents",
        "contents",
        "index",
    ),
    toc_markers=(
        "chapter",
        "unit",
        "lesson",
    ),
    translate_hint="",
)
