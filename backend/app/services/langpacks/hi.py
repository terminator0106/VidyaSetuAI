from __future__ import annotations

from app.services.langpacks.base import LanguagePack

PACK = LanguagePack(
    code="hi",
    name="Hindi",
    index_keywords=(
        "विषय सूची",
        "विषयसूची",
        "विषय-सूची",
        "सामग्री",
        "अनुक्रम",
        "अनुक्रमण",
        "अनुक्रमणिका",
        "अनुक्रमणिका",
        "अनुक्रमणिका",
        # Common ToC heading seen in textbooks
        "अनुक्रमणिका",
    ),
    toc_markers=(
        "अध्याय",
        "इकाई",
        "पाठ",
        "प्रकरण",
    ),
    translate_hint="Source language is Hindi (Devanagari).",
)
