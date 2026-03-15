from __future__ import annotations

from app.services.langpacks.base import LanguagePack

PACK = LanguagePack(
    code="gu",
    name="Gujarati",
    index_keywords=(
        "વિષય સૂચિ",
        "વિષયસૂચિ",
        "સામગ્રી",
        "અનુક્રમણિકા",
    ),
    toc_markers=(
        "પ્રકરણ",
        "પાઠ",
    ),
    translate_hint="Source language is Gujarati.",
)
