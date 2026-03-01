"""Structured JSON logging.

We avoid external dependencies and emit logs as JSON objects suitable for
collection by typical log pipelines.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional


class JsonFormatter(logging.Formatter):
    """Formats LogRecord into a single-line JSON string."""

    def format(self, record: logging.LogRecord) -> str:  # noqa: D401
        base: Dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }

        if record.exc_info:
            base["exc_info"] = self.formatException(record.exc_info)

        # Attach extra structured fields if provided.
        extras = getattr(record, "extra", None)
        if isinstance(extras, dict):
            for k, v in extras.items():
                if k not in base:
                    base[k] = v

        return json.dumps(base, ensure_ascii=False)


def configure_logging(level: str = "INFO") -> None:
    """Configure root logger to output structured JSON logs."""

    root = logging.getLogger()
    root.setLevel(level.upper())

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    # Replace existing handlers for deterministic output.
    root.handlers = [handler]


def log_event(logger: logging.Logger, message: str, **fields: Any) -> None:
    """Helper to log a message with structured fields."""

    logger.info(message, extra={"extra": fields})


def log_error(logger: logging.Logger, message: str, err: Optional[BaseException] = None, **fields: Any) -> None:
    """Helper to log an error with structured fields and exception."""

    if err is not None:
        logger.error(message, exc_info=err, extra={"extra": fields})
    else:
        logger.error(message, extra={"extra": fields})
