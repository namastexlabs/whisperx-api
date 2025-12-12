"""Structured logging configuration with dual-mode support.

Supports two formats:
- text: Human-readable output (default, for local development)
- json: Structured JSON output (for production log aggregation)

Set via MURMURAI_LOG_FORMAT=json environment variable.
"""

import json
import logging
import sys
import uuid
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

# Context variable for request correlation
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


def get_request_id() -> str | None:
    """Get the current request ID from context."""
    return request_id_var.get()


def set_request_id(request_id: str | None = None) -> str:
    """Set request ID in context. Generates one if not provided."""
    if request_id is None:
        request_id = str(uuid.uuid4())[:8]
    request_id_var.set(request_id)
    return request_id


class JSONFormatter(logging.Formatter):
    """JSON log formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add request ID if available
        request_id = get_request_id()
        if request_id:
            log_data["request_id"] = request_id

        # Add extra fields from record
        if hasattr(record, "duration_ms"):
            log_data["duration_ms"] = record.duration_ms
        if hasattr(record, "audio_duration_ms"):
            log_data["audio_duration_ms"] = record.audio_duration_ms
        if hasattr(record, "transcript_id"):
            log_data["transcript_id"] = record.transcript_id
        if hasattr(record, "language"):
            log_data["language"] = record.language
        if hasattr(record, "segments"):
            log_data["segments"] = record.segments
        if hasattr(record, "words"):
            log_data["words"] = record.words

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


class TextFormatter(logging.Formatter):
    """Human-readable log formatter with optional request ID."""

    def format(self, record: logging.LogRecord) -> str:
        # Build prefix with request ID if available
        request_id = get_request_id()
        prefix = f"[{request_id}] " if request_id else ""

        # Format: [murmurai] [request_id] message
        timestamp = datetime.now().strftime("%H:%M:%S")
        base = f"[{timestamp}] [{record.levelname}] {prefix}{record.getMessage()}"

        # Add extra context inline if present
        extras = []
        if hasattr(record, "duration_ms"):
            extras.append(f"duration={record.duration_ms}ms")
        if hasattr(record, "audio_duration_ms"):
            extras.append(f"audio={record.audio_duration_ms}ms")
        if hasattr(record, "language"):
            extras.append(f"lang={record.language}")

        if extras:
            base += f" ({', '.join(extras)})"

        # Add exception if present
        if record.exc_info:
            base += f"\n{self.formatException(record.exc_info)}"

        return base


def setup_logging(log_format: str = "text", log_level: str = "INFO") -> logging.Logger:
    """Configure application logging.

    Args:
        log_format: "text" for human-readable, "json" for structured
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)

    Returns:
        Configured root logger for murmurai
    """
    logger = logging.getLogger("murmurai")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Remove existing handlers
    logger.handlers.clear()

    # Create console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Set formatter based on format option
    if log_format.lower() == "json":
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(TextFormatter())

    logger.addHandler(handler)

    # Prevent propagation to root logger (avoids duplicate logs)
    logger.propagate = False

    return logger


def get_logger() -> logging.Logger:
    """Get the murmurai logger instance."""
    return logging.getLogger("murmurai")
