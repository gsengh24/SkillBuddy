"""Structured logging.

All log output goes to stdout as one JSON object per line (or a readable single-line
format when ``LOG_JSON=false`` for local debugging). The current request id is attached
to every record emitted while a request is being handled, so logs from the API, the
database layer and third-party libraries can be correlated.
"""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any, Final

from app.core.config import LogLevel

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

# Attributes every LogRecord has; anything else was passed via ``extra=`` and is emitted.
_RESERVED_ATTRS: Final = frozenset(
    logging.LogRecord("", 0, "", 0, "", None, None).__dict__.keys()
    | {"message", "asctime", "taskName"}
)


class RequestIdFilter(logging.Filter):
    """Copy the current request id from the context onto each record."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = request_id_var.get()
        return True


class JsonFormatter(logging.Formatter):
    """Render a record as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED_ATTRS and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack_info"] = self.formatStack(record.stack_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


_TEXT_FORMAT: Final = "%(asctime)s %(levelname)-8s %(name)s [%(request_id)s] %(message)s"


def configure_logging(level: LogLevel, *, json_output: bool) -> None:
    """Route all logging (ours, uvicorn's, arq's) through one stdout handler."""
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RequestIdFilter())
    handler.setFormatter(JsonFormatter() if json_output else logging.Formatter(_TEXT_FORMAT))

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # Let library loggers propagate to the root handler instead of using their own.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "arq"):
        library_logger = logging.getLogger(name)
        library_logger.handlers.clear()
        library_logger.propagate = True
    # Access lines are emitted by our own middleware with the request id attached.
    logging.getLogger("uvicorn.access").disabled = True
