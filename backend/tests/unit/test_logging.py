from __future__ import annotations

import json
import logging
import sys

import pytest

from app.core.logging import JsonFormatter, RequestIdFilter, configure_logging, request_id_var


def _record(message: str = "hello", **extra: object) -> logging.LogRecord:
    record = logging.LogRecord("app.test", logging.INFO, __file__, 1, message, None, None)
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def test_json_formatter_emits_one_json_object() -> None:
    line = JsonFormatter().format(_record(user_count=3))

    payload = json.loads(line)
    assert payload["message"] == "hello"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "app.test"
    assert payload["user_count"] == 3
    assert payload["timestamp"].endswith("+00:00")
    assert "\n" not in line


def test_json_formatter_includes_exception() -> None:
    try:
        raise ValueError("boom")
    except ValueError:
        record = logging.LogRecord(
            "app.test", logging.ERROR, __file__, 1, "failed", None, sys.exc_info()
        )

    payload = json.loads(JsonFormatter().format(record))

    assert "ValueError: boom" in payload["exc_info"]


def test_request_id_filter_attaches_current_request_id() -> None:
    token = request_id_var.set("req-123")
    try:
        record = _record()
        RequestIdFilter().filter(record)
    finally:
        request_id_var.reset(token)

    assert json.loads(JsonFormatter().format(record))["request_id"] == "req-123"


def test_configure_logging_writes_json_to_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO", json_output=True)

    logging.getLogger("app.test").info("configured", extra={"answer": 42})

    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert payload["message"] == "configured"
    assert payload["answer"] == 42
    assert payload["request_id"] is None
