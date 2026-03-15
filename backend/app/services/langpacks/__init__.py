from __future__ import annotations

from typing import Dict, Iterable, Tuple

from app.services.langpacks.base import LanguagePack
from app.services.langpacks.en import PACK as EN
from app.services.langpacks.gu import PACK as GU
from app.services.langpacks.hi import PACK as HI
from app.services.langpacks.mr import PACK as MR


LANG_PACKS: Dict[str, LanguagePack] = {
    "en": EN,
    "hi": HI,
    "mr": MR,
    "gu": GU,
}


def get_pack(code: str) -> LanguagePack:
    return LANG_PACKS.get((code or "").lower(), EN)


def all_index_keywords(packs: Iterable[LanguagePack] | None = None) -> Tuple[str, ...]:
    ps = list(packs) if packs is not None else list(LANG_PACKS.values())
    out = []
    for p in ps:
        out.extend(list(p.index_keywords))
    # de-dupe, keep order
    seen = set()
    uniq = []
    for k in out:
        kk = (k or "").strip()
        if not kk or kk in seen:
            continue
        seen.add(kk)
        uniq.append(kk)
    return tuple(uniq)


def all_toc_markers(packs: Iterable[LanguagePack] | None = None) -> Tuple[str, ...]:
    ps = list(packs) if packs is not None else list(LANG_PACKS.values())
    out = []
    for p in ps:
        out.extend(list(p.toc_markers))
    # include english defaults even if pack list excludes them
    for k in ["chapter", "unit", "lesson"]:
        out.append(k)

    seen = set()
    uniq = []
    for k in out:
        kk = (k or "").strip()
        if not kk or kk.lower() in seen:
            continue
        seen.add(kk.lower())
        uniq.append(kk)
    return tuple(uniq)
