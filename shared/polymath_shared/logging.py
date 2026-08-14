"""Structured JSON logging. See AGENTS.md for the field contract."""
from __future__ import annotations

import datetime as dt
import json
import logging
import sys
from typing import Any


CONTEXT_FIELDS = (
    "trace_id",
    "run_id",
    "stage",
    "attempt_id",
    "provider",
    "model_release",
    "device",
    "duration_ms",
    "error_code",
)


class JsonFormatter(logging.Formatter):
    def __init__(self, service: str) -> None:
        super().__init__()
        self.service = service

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
            "level": record.levelname,
            "service": getattr(record, "service", self.service),
            "event": getattr(record, "event", record.name),
            "message": record.getMessage(),
        }
        payload.update({field: getattr(record, field, None) for field in CONTEXT_FIELDS})
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_logging(service: str, level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter(service))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)


def with_context(logger: logging.Logger, **context: Any) -> logging.LoggerAdapter:
    unknown = set(context) - set(CONTEXT_FIELDS) - {"event", "service"}
    if unknown:
        raise ValueError(f"unknown log fields: {sorted(unknown)}")
    return logging.LoggerAdapter(logger, context)
