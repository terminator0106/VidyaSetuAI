"""Compatibility entrypoint.

The real FastAPI app lives in `app.main:app`.
This shim allows running:
  uvicorn main:app --reload
from the backend project root.
"""

from app.main import app  # noqa: F401
