"""Cloudinary-backed storage for chapter PDFs.

This module provides a minimal storage layer that can be wired into API routes
without changing ingestion, DB schema, or frontend contracts.

Cloudinary is configured via environment variables:
- CLOUDINARY_CLOUD_NAME
- CLOUDINARY_API_KEY
- CLOUDINARY_API_SECRET

All uploads are stored as raw resources under the "textbooks" folder.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse
from typing import Any, Dict, Optional

import cloudinary
import cloudinary.uploader
import cloudinary.utils

from app.config import settings


class CloudinaryStorageError(RuntimeError):
    """Raised when Cloudinary storage operations fail."""


_CONFIGURED: bool = False


def _ensure_configured() -> None:
    """Configure Cloudinary SDK once.

    Raises:
        CloudinaryStorageError: If required Cloudinary credentials are missing.
    """

    global _CONFIGURED
    if _CONFIGURED:
        return

    def _dequote(v: str) -> str:
        v = (v or "").strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in {'"', "'"}:
            v = v[1:-1].strip()
        return v

    cloud_name = _dequote(settings.CLOUDINARY_CLOUD_NAME or "")
    api_key = _dequote(settings.CLOUDINARY_API_KEY or "")
    api_secret = _dequote(settings.CLOUDINARY_API_SECRET or "")

    # Common local-dev footgun: committing a masked secret (e.g. **********) or
    # leaving a placeholder. Cloudinary will then return "Invalid Signature".
    if api_secret and set(api_secret) == {"*"}:
        api_secret = ""

    if not cloud_name or not api_key or not api_secret:
        raise CloudinaryStorageError(
            "Cloudinary credentials are not configured. Set CLOUDINARY_CLOUD_NAME, "
            "CLOUDINARY_API_KEY, and CLOUDINARY_API_SECRET in backend/.env."
        )

    cloudinary.config(
        cloud_name=cloud_name,
        api_key=api_key,
        api_secret=api_secret,
        secure=True,
    )
    _CONFIGURED = True


def _full_public_id(public_id: str) -> str:
    """Return the full Cloudinary public ID including the textbooks folder."""

    pid = (public_id or "").strip().lstrip("/")
    if not pid:
        raise CloudinaryStorageError("public_id must be a non-empty string")

    if pid.startswith("textbooks/"):
        return pid
    return f"textbooks/{pid}"


def upload_pdf(file_path: str, public_id: str) -> str:
    """Upload a PDF file to Cloudinary.

    Args:
        file_path: Local path to the PDF.
        public_id: Desired public id within the Cloudinary "textbooks" folder.

    Returns:
        The secure URL for the uploaded file.

    Raises:
        CloudinaryStorageError: If upload fails or the response lacks a URL.
    """

    _ensure_configured()

    path = Path(file_path)
    if not path.exists() or not path.is_file():
        raise CloudinaryStorageError(f"File not found: {file_path}")

    pid = (public_id or "").strip()
    if not pid:
        raise CloudinaryStorageError("public_id must be a non-empty string")

    try:
        resp: Dict[str, Any] = cloudinary.uploader.upload(
            str(path),
            resource_type="raw",
            folder="textbooks",
            public_id=pid,
            overwrite=True,
        )
    except Exception as e:  # pragma: no cover
        raise CloudinaryStorageError(f"Cloudinary upload failed: {e}") from e

    url = (resp.get("secure_url") or resp.get("url") or "").strip()
    if not url:
        raise CloudinaryStorageError("Cloudinary upload succeeded but no URL was returned")
    return url


def delete_file(public_id: str) -> None:
    """Delete a stored file from Cloudinary.

    Args:
        public_id: Public id of the file (with or without the textbooks/ prefix).

    Raises:
        CloudinaryStorageError: If Cloudinary reports a failure.
    """

    _ensure_configured()

    pid = _full_public_id(public_id)

    try:
        resp: Dict[str, Any] = cloudinary.uploader.destroy(pid, resource_type="raw")
    except Exception as e:  # pragma: no cover
        raise CloudinaryStorageError(f"Cloudinary delete failed: {e}") from e

    result = str(resp.get("result") or "").lower()
    if result in {"ok", "not found"}:
        return

    # Cloudinary sometimes returns {'result': 'error', 'error': {'message': '...'}}
    err_msg: Optional[str] = None
    err = resp.get("error")
    if isinstance(err, dict):
        err_msg = str(err.get("message") or "").strip() or None

    raise CloudinaryStorageError(f"Cloudinary delete failed (result={result}). {err_msg or ''}".strip())


def get_file_url(public_id: str) -> str:
    """Return a public URL for a stored raw file.

    Args:
        public_id: Public id of the file (with or without the textbooks/ prefix).

    Returns:
        A secure URL that can be used to retrieve the file.

    Notes:
        This does not verify existence. It only constructs a URL.

    Raises:
        CloudinaryStorageError: If Cloudinary is not configured.
    """

    _ensure_configured()

    pid = _full_public_id(public_id)
    url, _opts = cloudinary.utils.cloudinary_url(pid, resource_type="raw", secure=True)
    return str(url)


def public_id_from_url(url: str) -> str | None:
    """Best-effort extraction of Cloudinary public_id from a Cloudinary URL.

    Supports URLs that include the `textbooks/` folder, for example:
      https://res.cloudinary.com/<cloud>/raw/upload/v123/textbooks/<path>.pdf

    Returns:
        The public_id *within* the textbooks folder (e.g. "subject/book/chapter1"),
        or None if it cannot be derived.
    """

    raw = (url or "").strip()
    if not raw:
        return None

    try:
        parsed = urlparse(raw)
        path = parsed.path or ""
    except Exception:
        return None

    marker = "/textbooks/"
    idx = path.find(marker)
    if idx < 0:
        return None

    remainder = path[idx + len(marker) :].lstrip("/")
    if not remainder:
        return None

    # Strip file extension if present.
    if "." in remainder:
        remainder = remainder.rsplit(".", 1)[0]

    remainder = remainder.strip("/")
    return remainder or None
