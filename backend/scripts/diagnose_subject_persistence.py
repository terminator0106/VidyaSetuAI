"""Diagnose why subjects appear to disappear.

Prints:
- Active SQLAlchemy URL (redacted)
- Dialect name
- Whether subjects table exists
- Count of subjects
- Count of textbooks with subject_id

Run:
  python backend/scripts/diagnose_subject_persistence.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urlsplit

from sqlalchemy import text

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database import engine, init_db


def _redact_url(url: str) -> str:
    try:
        parts = urlsplit(url)
        netloc = parts.netloc
        if "@" in netloc:
            creds, host = netloc.split("@", 1)
            if ":" in creds:
                user, _pw = creds.split(":", 1)
                netloc = f"{user}:***@{host}"
            else:
                netloc = f"***@{host}"
        return parts._replace(netloc=netloc).geturl()
    except Exception:
        return "<unparseable>"


def main() -> None:
    init_db()

    url = str(engine.url)
    print("dialect:", engine.dialect.name)
    print("db_url:", _redact_url(url))

    with engine.begin() as conn:
        if engine.dialect.name.startswith("postgres"):
            subjects_reg = conn.execute(text("SELECT to_regclass('public.subjects')")).scalar()
            print("subjects_table:", "OK" if subjects_reg else "MISSING")
            if subjects_reg:
                subjects_count = conn.execute(text("SELECT COUNT(*) FROM public.subjects")).scalar()
                print("subjects_count:", int(subjects_count or 0))

            textbooks_reg = conn.execute(text("SELECT to_regclass('public.textbooks')")).scalar()
            if textbooks_reg:
                tb_count = conn.execute(text("SELECT COUNT(*) FROM public.textbooks WHERE subject_id IS NOT NULL")).scalar()
                print("textbooks_with_subject_id:", int(tb_count or 0))
        elif engine.dialect.name == "sqlite":
            subjects_reg = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name='subjects'")
            ).scalar()
            print("subjects_table:", "OK" if subjects_reg else "MISSING")
            if subjects_reg:
                subjects_count = conn.execute(text("SELECT COUNT(*) FROM subjects")).scalar()
                print("subjects_count:", int(subjects_count or 0))

            textbooks_reg = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name='textbooks'")
            ).scalar()
            if textbooks_reg:
                tb_count = conn.execute(text("SELECT COUNT(*) FROM textbooks WHERE subject_id IS NOT NULL")).scalar()
                print("textbooks_with_subject_id:", int(tb_count or 0))
        else:
            print("Unsupported dialect for this script")


if __name__ == "__main__":
    main()
