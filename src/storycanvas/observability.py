from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

request_id_context: ContextVar[str] = ContextVar("request_id", default="-")


class JsonLogFormatter(logging.Formatter):
    """Emit compact JSON logs without story text, credentials, or request bodies."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", request_id_context.get()),
        }
        for key in ("method", "path", "status_code", "duration_ms", "error_type"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_logging(level: str, log_file: Path | None = None) -> logging.Logger:
    logger = logging.getLogger("storycanvas")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.propagate = False
    if getattr(logger, "_storycanvas_configured", False):
        return logger

    formatter = JsonLogFormatter()
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    logger.addHandler(console)
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    logger._storycanvas_configured = True
    return logger
