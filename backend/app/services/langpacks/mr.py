from __future__ import annotations

from app.services.langpacks.base import LanguagePack

PACK = LanguagePack(
    code="mr",
    name="Marathi",
    index_keywords=(
        "अनुक्रमणिका",
        "अनुक्रम",
        "सामग्री",
    ),
    toc_markers=(
        "अध्याय",
        "इकाई",
        "पाठ",
        "प्रकरण",
    ),
    translate_hint="Source language is Marathi (Devanagari).",
)
