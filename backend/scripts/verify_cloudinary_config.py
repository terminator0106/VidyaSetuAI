"""Verify Cloudinary credentials without uploading real data.

This script makes a lightweight authenticated request to Cloudinary (API ping).
It helps diagnose "Invalid Signature" problems, which are almost always caused
by a mismatched API secret/key or using the wrong Cloud name.

Run from backend/:
    & "d:/HPE - AMD/.venv/Scripts/python.exe" ./scripts/verify_cloudinary_config.py

Notes:
- Reads CLOUDINARY_* from backend/.env via app.config.Settings.
- Does not print the API secret.
"""

from __future__ import annotations

import sys
from pathlib import Path


# Allow running as a script from backend/scripts while importing `app.*`.
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

import cloudinary
import cloudinary.api

from app.config import settings


def _mask(s: str, keep_last: int = 4) -> str:
    s = (s or "").strip()
    if not s:
        return "(empty)"
    if len(s) <= keep_last:
        return "*" * len(s)
    return "*" * (len(s) - keep_last) + s[-keep_last:]


def main() -> int:
    cloud_name = (settings.CLOUDINARY_CLOUD_NAME or "").strip()
    api_key = (settings.CLOUDINARY_API_KEY or "").strip()
    api_secret = (settings.CLOUDINARY_API_SECRET or "").strip()

    print("cloud_name:", cloud_name or "(empty)")
    print("api_key:", _mask(api_key))
    print("api_secret:", "(set)" if api_secret else "(empty)")

    if api_secret and set(api_secret) == {"*"}:
        print("ERROR: CLOUDINARY_API_SECRET looks masked (all '*').")
        print("Set the real API secret from Cloudinary Console → Settings → Access Keys.")
        return 2

    if not cloud_name or not api_key or not api_secret:
        print("ERROR: Missing Cloudinary credentials in backend/.env")
        return 2

    cloudinary.config(cloud_name=cloud_name, api_key=api_key, api_secret=api_secret, secure=True)

    try:
        resp = cloudinary.api.ping()
    except Exception as e:
        print("Cloudinary ping failed:", str(e))
        return 1

    # ping response is typically {'status': 'ok'}
    print("Cloudinary ping ok:", resp)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
