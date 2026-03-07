"""Backfill Cloudinary URLs for existing chapters.

Use when chapters exist in the DB (with start/end page ranges) but
`chapters.cloudinary_url` is empty because earlier ingests failed before the DB
schema supported it.

This script:
- Loads the textbook's source.pdf from the standard data folder
- Generates per-chapter PDFs from the stored page ranges
- Uploads each chapter PDF to Cloudinary as a raw resource
- Persists the returned secure URL into `chapters.cloudinary_url`

Example:
  d:/HPE - AMD/.venv/Scripts/python.exe -m scripts.backfill_cloudinary_chapters --textbook-id 8

Notes:
- Requires Cloudinary env vars in backend/.env.
- Does not require the FastAPI server to be running.
"""

from __future__ import annotations

import argparse
import re
import sys
import tempfile
from pathlib import Path

# Allow running as a script from backend/scripts while importing `app.*`.
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from sqlalchemy import select

from app.database import db_session, init_db
from app.models.chapter import Chapter
from app.models.textbook import Textbook
from app.services.cloudinary_storage import CloudinaryStorageError, upload_pdf
from app.services.textbook_store import pdf_path


def _slugify_component(raw: str | None, *, default: str) -> str:
    value = (raw or "").strip().lower()
    if not value:
        return default
    # Keep it close to ingest.py semantics: alnum + [-_], collapse others to '-'
    value = re.sub(r"[^a-z0-9_-]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value or default


def _build_public_id(subject_id: str | None, textbook_title: str, chapter_number: int) -> str:
    subject_slug = _slugify_component(subject_id, default="subject")
    textbook_slug = _slugify_component(textbook_title, default="textbook")
    return f"{subject_slug}/{textbook_slug}/chapter{int(chapter_number)}"


def backfill_cloudinary_urls(
    *,
    textbook_id: int,
    subject_id: str | None,
    overwrite: bool,
    limit: int | None,
    dry_run: bool,
) -> int:
    """Backfill cloudinary_url for chapters of a textbook.

    Returns the number of chapters updated.
    """

    # Make sure DB schema is aligned (idempotent).
    init_db()

    src_pdf = pdf_path(int(textbook_id))
    if not src_pdf.exists():
        raise SystemExit(f"Source PDF not found at: {src_pdf}")

    import fitz  # PyMuPDF

    with db_session() as db:
        tb = db.scalar(select(Textbook).where(Textbook.id == int(textbook_id)))
        if tb is None:
            raise SystemExit(f"Textbook not found in DB: {textbook_id}")

        q = select(Chapter).where(Chapter.textbook_id == int(textbook_id)).order_by(Chapter.chapter_number.asc())
        chapters = list(db.scalars(q).all())

        if subject_id:
            # Best-effort: backfill subject_id where missing.
            for ch in chapters:
                if ch.subject_id is None:
                    ch.subject_id = subject_id

        updated = 0

        with fitz.open(str(src_pdf)) as doc, tempfile.TemporaryDirectory(prefix="chapters_") as tmp:
            tmp_dir = Path(tmp)

            for idx, ch in enumerate(chapters):
                if limit is not None and idx >= int(limit):
                    break

                if ch.cloudinary_url and not overwrite:
                    continue

                total = int(doc.page_count)
                start = max(1, min(total, int(ch.start_page)))
                end = max(start, min(total, int(ch.end_page)))

                out_path = tmp_dir / f"{ch.chapter_key}.pdf"
                out_doc = fitz.open()
                try:
                    out_doc.insert_pdf(doc, from_page=start - 1, to_page=end - 1)
                    out_path.write_bytes(out_doc.tobytes(deflate=True))
                finally:
                    out_doc.close()

                pid = _build_public_id(subject_id or ch.subject_id, tb.title, int(ch.chapter_number))

                if dry_run:
                    print(f"[dry-run] would upload {out_path.name} -> public_id={pid}")
                    continue

                try:
                    url = upload_pdf(file_path=str(out_path), public_id=pid)
                except CloudinaryStorageError as e:
                    raise SystemExit(f"Cloudinary upload failed for {ch.chapter_key}: {e}") from e

                ch.cloudinary_url = url
                updated += 1
                print(f"uploaded {ch.chapter_key} -> {url}")

        if not dry_run:
            db.commit()

        return updated


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backfill chapters.cloudinary_url for a textbook")
    parser.add_argument("--textbook-id", type=int, required=True)
    parser.add_argument("--subject-id", type=str, default=None, help="Optional subject id/slug to store and use in public_id")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing cloudinary_url values")
    parser.add_argument("--limit", type=int, default=None, help="Only process first N chapters")
    parser.add_argument("--dry-run", action="store_true", help="Do not upload or write DB; print planned uploads")

    args = parser.parse_args(argv)

    updated = backfill_cloudinary_urls(
        textbook_id=int(args.textbook_id),
        subject_id=(args.subject_id or None),
        overwrite=bool(args.overwrite),
        limit=(int(args.limit) if args.limit is not None else None),
        dry_run=bool(args.dry_run),
    )

    if args.dry_run:
        print("dry-run complete")
    else:
        print(f"done. chapters updated: {updated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
