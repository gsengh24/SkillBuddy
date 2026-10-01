"""``python -m app.jobs.worker`` as a real process: it stops cleanly on SIGTERM and SIGINT.

The worker's registry is empty until ADR 0008 step 3, so it never touches the database and
needs no infrastructure. POSIX signals only; skipped on Windows.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2]
STARTUP_TIMEOUT_SECONDS = 30.0
SHUTDOWN_TIMEOUT_SECONDS = 15.0

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="POSIX signals only")


def _start_worker() -> subprocess.Popen[str]:
    env = os.environ | {"PYTHONUNBUFFERED": "1", "LOG_JSON": "true"}
    return subprocess.Popen(
        [sys.executable, "-m", "app.jobs.worker"],
        cwd=BACKEND_DIR,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def _wait_for_line(process: subprocess.Popen[str], needle: str, seen: list[str]) -> None:
    assert process.stdout is not None
    deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        line = process.stdout.readline()
        if not line:
            break  # the process exited
        seen.append(line)
        if needle in line:
            return
    pytest.fail(f"{needle!r} not logged; output: {''.join(seen)}")


@pytest.mark.parametrize("signum", [signal.SIGTERM, signal.SIGINT])
def test_worker_process_stops_cleanly_on_signal(signum: signal.Signals) -> None:
    process = _start_worker()
    seen: list[str] = []
    try:
        _wait_for_line(process, "job_runner_started", seen)

        process.send_signal(signum)
        output, _ = process.communicate(timeout=SHUTDOWN_TIMEOUT_SECONDS)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()

    assert process.returncode == 0, "".join(seen) + output
    assert "job_runner_stopped" in output
    assert "Traceback" not in "".join(seen) + output
