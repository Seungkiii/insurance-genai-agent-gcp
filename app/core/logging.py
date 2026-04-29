"""Structured logging helpers."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone

from app.core.config import Settings


STANDARD_LOG_RECORD_FIELDS = {
    "args",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
}


class JsonFormatter(logging.Formatter):
    """Minimal JSON formatter suitable for Cloud Run log ingestion."""

    def format(self, record: logging.LogRecord) -> str:
        """Serialize the log record as a JSON string."""
        payload: dict[str, object] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "severity": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        service = getattr(record, "service", None)
        environment = getattr(record, "environment", None)
        version = getattr(record, "version", None)

        if service:
            payload["service"] = service
        if environment:
            payload["environment"] = environment
        if version:
            payload["version"] = version

        for key, value in record.__dict__.items():
            if key not in STANDARD_LOG_RECORD_FIELDS and key not in payload:
                payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=True)


def configure_logging(settings: Settings) -> None:
    """Configure root logging with JSON structured output."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(handler)

    app_logger = logging.getLogger("app")
    app_logger.propagate = True
    app_logger.info(
        "logging_configured",
        extra={
            "service": settings.app_name,
            "environment": settings.environment,
            "version": settings.app_version,
        },
    )


def get_logger(name: str) -> logging.Logger:
    """Return a named logger instance."""
    return logging.getLogger(name)
